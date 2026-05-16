"""StellaShelf FITS/XISF header scanner.

Recursively scans directories for FITS files, extracts metadata from headers,
and groups frames into sessions.

Supports:
- Standard FITS files
- Gzip-compressed FITS (SGP format) where headers live in HDU[1]
- Filename-based fallback parsing
- XISF files (skipped with warning — parser not yet implemented)
"""

import io
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
from astropy.io import fits
from rich.console import Console
from rich.progress import Progress

from stellashelf.catalog import normalize_object_name
from stellashelf.config import KNOWN_CAMERAS

console = Console()


# ---------------------------------------------------------------------------
# Coordinate Parsing
# ---------------------------------------------------------------------------


def _parse_hms_to_degrees(hms_str: str) -> float | None:
    """Parse HMS (HH MM SS.SS) string to degrees. 1h = 15deg."""
    try:
        parts = re.split(r"[\s:]+", hms_str.strip())
        if len(parts) >= 3:
            h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return (h + m / 60 + s / 3600) * 15
        elif len(parts) == 2:
            h, m = float(parts[0]), float(parts[1])
            return (h + m / 60) * 15
    except (ValueError, IndexError):
        pass
    return None


def _parse_dms_to_degrees(dms_str: str) -> float | None:
    """Parse DMS (+/-DD MM SS.SS) string to decimal degrees."""
    try:
        parts = re.split(r"[\s:]+", dms_str.strip())
        if len(parts) >= 3:
            sign = -1 if parts[0].startswith("-") else 1
            d, m, s = abs(float(parts[0])), float(parts[1]), float(parts[2])
            return sign * (d + m / 60 + s / 3600)
        elif len(parts) == 2:
            sign = -1 if parts[0].startswith("-") else 1
            d, m = abs(float(parts[0])), float(parts[1])
            return sign * (d + m / 60)
    except (ValueError, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# Path-based Equipment Extraction
# ---------------------------------------------------------------------------

# Known camera folder names under Astro/astro/
# Loaded from config (overridable via STELLASHELF_KNOWN_CAMERAS env var)
_CAMERA_PATH_RE = re.compile(
    r"(?:^|/)Astro/astro/(" + "|".join(re.escape(c) for c in sorted(KNOWN_CAMERAS)) + r")/",
    re.IGNORECASE,
)

# Regex: match Astro/astro/<CAMERA>/_<TELESCOPE>/ — capture telescope without leading underscore
_TELESCOPE_PATH_RE = re.compile(
    r"(?:^|/)Astro/astro/(?:[^/]+)/_([^/]+)/",
    re.IGNORECASE,
)


def _extract_camera_from_path(filepath: Path) -> str | None:
    """Extract camera name from filepath matching Astro/astro/{CAMERA}/ pattern.

    Args:
        filepath: Path to the FITS file.

    Returns:
        Camera name string if found, None otherwise.
    """
    if not filepath:
        return None
    path_str = str(filepath)
    match = _CAMERA_PATH_RE.search(path_str)
    if match:
        return match.group(1)
    return None


def _extract_telescope_from_path(filepath: Path) -> str | None:
    """Extract telescope name from filepath matching Astro/astro/{CAMERA}/_{TELESCOPE}/.

    Strips the leading underscore from telescope folder names.

    Args:
        filepath: Path to the FITS file.

    Returns:
        Telescope name string if found, None otherwise.
    """
    if not filepath:
        return None
    path_str = str(filepath)
    match = _TELESCOPE_PATH_RE.search(path_str)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Data classes for scanned metadata
# ---------------------------------------------------------------------------


@dataclass
class ScannedFrame:
    """Metadata extracted from a single FITS file."""

    filepath: Path
    filename: str
    file_size: int
    frame_type: str = ""  # LIGHT, DARK, FLAT, BIAS
    object_name: str = ""
    instrume: str = ""
    telescop: str = ""
    filter_name: str = ""
    exposure: float | None = None
    gain: int | None = None
    ccd_temp: float | None = None
    binning: int = 1
    date_obs: datetime | None = None
    date_local: datetime | None = None
    width: int | None = None
    height: int | None = None
    pixel_size_um: float | None = None
    focal_length_mm: float | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    site_name: str = ""
    observer: str = ""
    creator: str = ""
    file_sha256: str = ""
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# FITS header extraction
# ---------------------------------------------------------------------------

_HEADER_ALIASES = {
    "EXPOSURE": ["EXPTIME", "EXP_TIME"],
    "CCD-TEMP": ["CCDTEMP", "TEMPERAT"],
    "FILTER": ["FILTERS", "FILTNAME"],
    "GAIN": ["EGAIN", "EMGAIN"],
    "DATE-OBS": ["DATE_OBS", "DATEOBS"],
    "INSTRUME": ["CAMERA", "CAMNAME"],
}


def _get_header_value(header: fits.Header, key: str, default=None):
    """Get a value from a FITS header, handling alternate key names."""
    value = header.get(key)
    if value is not None:
        return value
    for alias in _HEADER_ALIASES.get(key, []):
        value = header.get(alias)
        if value is not None:
            return value
    return default


def _extract_header(hdu_list: fits.HDUList) -> dict:
    """Extract relevant headers from a FITS file."""
    primary = hdu_list[0].header
    extension = hdu_list[1].header if len(hdu_list) > 1 else primary

    result = {}
    keys_to_extract = [
        "OBJECT",
        "INSTRUME",
        "TELESCOP",
        "FILTER",
        "EXPOSURE",
        "GAIN",
        "CCD-TEMP",
        "DATE-OBS",
        "DATE-LOC",
        "XBINNING",
        "YBINNING",
        "NAXIS1",
        "NAXIS2",
        "IMAGETYP",
        "FOCALLEN",
        "XPIXSZ",
        "YPIXSZ",
        "RA",
        "DEC",
        "CRVAL1",
        "CRVAL2",
        "SITENAME",
        "OBSERVER",
        "CREATOR",
        "BAYERPAT",
    ]

    for key in keys_to_extract:
        value = _get_header_value(extension, key)
        if value is None and extension is not primary:
            value = _get_header_value(primary, key)
        if value is not None:
            result[key] = value

    return result


# Normalize IMAGETYP values from various capture software
_FRAME_TYPE_MAP = {
    "light": "LIGHT",
    "light frame": "LIGHT",
    "lightframe": "LIGHT",
    "dark": "DARK",
    "dark frame": "DARK",
    "darkframe": "DARK",
    "flat": "FLAT",
    "flat frame": "FLAT",
    "flatfield": "FLAT",
    "flat field": "FLAT",
    "bias": "BIAS",
    "bias frame": "BIAS",
    "biasframe": "BIAS",
    "offset": "BIAS",
    "skyflat": "FLAT",
}


def _normalize_frame_type(raw: str) -> str:
    """Normalize IMAGETYP to canonical LIGHT/DARK/FLAT/BIAS."""
    if not raw:
        return ""
    cleaned = raw.strip().lower()
    return _FRAME_TYPE_MAP.get(cleaned, cleaned.upper())


def _extract_object_from_filename(filename: str) -> str:
    """Try to extract object name from filename patterns like M42_Ha.fit, NGC7000_L_300s.fit."""
    stem = filename.split("_")[0] if "_" in filename else filename
    for ext in (".fit", ".fits", ".fit.gz", ".fits.gz", ".xisf"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break

    patterns = [
        r"^(M\s*\d+[a-zA-Z]?)$",
        r"^(NGC\s*\d+[a-zA-Z]?)$",
        r"^(IC\s*\d+[a-zA-Z]?)$",
        r"^(SH[A-Za-z]?[-_]?\d+)$",
        r"^(LDN\s*\d+)$",
        r"^(vdB\s*\d+)$",
        r"^(B\s*\d+)$",
        r"^(C\s*\d+)$",
    ]
    for pat in patterns:
        m = re.match(pat, stem, re.IGNORECASE)
        if m:
            return normalize_object_name(m.group(1))

    m = re.match(r"^([A-Z]{1,5}\s*\d+[a-zA-Z0-9-]*)", stem, re.IGNORECASE)
    if m:
        return normalize_object_name(m.group(1))

    return ""


def scan_fits_file(filepath: Path) -> ScannedFrame:
    """Scan a single FITS file and extract metadata."""
    frame = ScannedFrame(
        filepath=filepath,
        filename=filepath.name,
        file_size=filepath.stat().st_size,
    )

    try:
        with fits.open(str(filepath)) as hdul:
            header = _extract_header(hdul)

            # String fields — path extraction is PRIMARY, FITS header is fallback
            raw_object = str(header.get("OBJECT", "")).strip()
            frame.object_name = normalize_object_name(raw_object) if raw_object else ""
            path_camera = _extract_camera_from_path(filepath)
            instrume_val = path_camera if path_camera else str(header.get("INSTRUME", "")).strip()
            frame.instrume = instrume_val
            path_telescope = _extract_telescope_from_path(filepath)
            telescop_val = (
                path_telescope if path_telescope else str(header.get("TELESCOP", "")).strip()
            )
            frame.telescop = telescop_val
            frame.filter_name = str(header.get("FILTER", "")).strip()
            frame.site_name = str(header.get("SITENAME", "")).strip()
            frame.observer = str(header.get("OBSERVER", "")).strip()
            frame.creator = str(header.get("CREATOR", "")).strip()

            raw_type = str(header.get("IMAGETYP", "")).strip()
            frame.frame_type = _normalize_frame_type(raw_type)

            # Numeric fields with explicit validation
            exposure = header.get("EXPOSURE")
            if exposure is not None:
                try:
                    frame.exposure = float(exposure)
                except (ValueError, TypeError):
                    frame.errors.append(f"Invalid EXPOSURE value: {exposure}")

            # Fix: QHY8L stores long exposures in milliseconds
            if "QHY8L" in frame.instrume and frame.exposure is not None and frame.exposure >= 10000:
                frame.exposure /= 1000.0

            gain = header.get("GAIN")
            if gain is not None:
                try:
                    frame.gain = int(gain)
                except (ValueError, TypeError):
                    frame.errors.append(f"Invalid GAIN value: {gain}")

            ccd_temp = header.get("CCD-TEMP")
            if ccd_temp is not None:
                try:
                    frame.ccd_temp = float(ccd_temp)
                except (ValueError, TypeError):
                    frame.errors.append(f"Invalid CCD-TEMP value: {ccd_temp}")

            binning = header.get("XBINNING")
            if binning is not None:
                try:
                    frame.binning = int(binning)
                except (ValueError, TypeError):
                    frame.errors.append(f"Invalid XBINNING value: {binning}")

            frame.width = header.get("NAXIS1")
            frame.height = header.get("NAXIS2")

            pxsz = header.get("XPIXSZ")
            frame.pixel_size_um = float(pxsz) if pxsz is not None else None

            fl = header.get("FOCALLEN")
            frame.focal_length_mm = float(fl) if fl is not None else None

            # Coordinate parsing
            ra = header.get("RA") or header.get("CRVAL1")
            if ra is not None:
                try:
                    frame.ra_deg = float(ra)
                except (ValueError, TypeError):
                    frame.ra_deg = _parse_hms_to_degrees(str(ra))

            dec = header.get("DEC") or header.get("CRVAL2")
            if dec is not None:
                try:
                    frame.dec_deg = float(dec)
                except (ValueError, TypeError):
                    frame.dec_deg = _parse_dms_to_degrees(str(dec))

            # Date parsing
            date_obs = header.get("DATE-OBS")
            if date_obs:
                try:
                    frame.date_obs = datetime.fromisoformat(str(date_obs).strip())
                except (ValueError, TypeError):
                    frame.errors.append(f"Cannot parse DATE-OBS: {date_obs}")

            date_local = header.get("DATE-LOC")
            if date_local:
                try:
                    frame.date_local = datetime.fromisoformat(str(date_local).strip())
                except (ValueError, TypeError):
                    frame.errors.append(f"Cannot parse DATE-LOC: {date_local}")

    except Exception as e:
        frame.errors.append(f"FITS read error: {e}")

    return frame


# ---------------------------------------------------------------------------
# Filename-based fallback parser
# ---------------------------------------------------------------------------

LIGHT_PATTERN = re.compile(
    r"^(?P<object>\S+?)_"
    r"(?P<filter>\w+)_"
    r"(?P<exposure>\d+)sec_"
    r"(?P<binning>\d+)x\d+_"
    r"-?\d+C_"
    r"gain_(?P<gain>\d+)_"
    r"(?P<seq>\d+)",
    re.IGNORECASE,
)

CALIB_PATTERN = re.compile(
    r"^(?P<type>master(?:bias|dark|flat)|smasterdark)_"
    r"(?:(?P<exposure>\d+)s_)?"
    r"(?P<binning>\d+)x\d+_?"
    r"(?:\d+x_)?"
    r"gain_(?P<gain>\d+)_"
    r"-?\d+C",
    re.IGNORECASE,
)


def parse_filename(filepath: Path) -> dict | None:
    """Try to extract metadata from the filename as a fallback."""
    name = filepath.stem

    m = LIGHT_PATTERN.match(name)
    if m:
        return {
            "object_name": m.group("object"),
            "filter_name": m.group("filter"),
            "exposure": int(m.group("exposure")),
            "binning": int(m.group("binning")),
            "gain": int(m.group("gain")),
            "frame_type": "LIGHT",
            "seq": int(m.group("seq")),
        }

    m = CALIB_PATTERN.match(name)
    if m:
        result = {
            "frame_type": m.group("type").upper(),
            "binning": int(m.group("binning")),
            "gain": int(m.group("gain")),
        }
        if m.group("exposure"):
            result["exposure"] = int(m.group("exposure"))
        return result

    return None


# ---------------------------------------------------------------------------
# Directory scanner
# ---------------------------------------------------------------------------

FITS_EXTENSIONS = {".fit", ".fits", ".fit.gz", ".fits.gz", ".FIT", ".FITS"}
XISF_EXTENSIONS = {".xisf", ".XISF"}


def find_fits_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Find all FITS files in a directory tree. XISF files are skipped."""
    pattern = "**/*" if recursive else "*"
    for path in root.glob(pattern):
        suffixes = "".join(path.suffixes).lower()
        if any(suffixes.endswith(ext.lower()) for ext in FITS_EXTENSIONS):
            yield path


def generate_group_key(frame: ScannedFrame) -> str:
    """Generate a unique grouping key for a session."""
    date_str = frame.date_obs.strftime("%Y-%m-%d") if frame.date_obs else "unknown"
    obj = frame.object_name.strip().upper() or "UNKNOWN"
    inst = frame.instrume.strip() or "UNKNOWN"
    tel = frame.telescop.strip() or "UNKNOWN"
    filt = frame.filter_name.strip().upper() or "UNKNOWN"
    return f"{obj}|{date_str}|{inst}|{tel}|{filt}"


def generate_thumbnail(filepath: Path, size: int = 200) -> bytes | None:
    """Generate a JPEG thumbnail from a FITS file.

    Extracts 2D image data from the last HDU, normalizes using percentile
    stretching, and resizes to the requested dimensions.

    Args:
        filepath: Path to the FITS file.
        size: Maximum width/height of the thumbnail.

    Returns:
        JPEG bytes on success, None on failure.
    """
    try:
        with fits.open(str(filepath)) as hdul:
            # Get image data from the last HDU (usually has the data)
            data = None
            for hdu in reversed(hdul):
                if hdu.data is not None:
                    data = hdu.data
                    break

            if data is None:
                return None

            # Convert to 2D if multi-dimensional
            if data.ndim > 2:
                data = data[0] if data.shape[0] == 1 else np.mean(data, axis=0)

            # Handle NaN/Inf
            data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)

            # Normalize to 0-255 using percentiles for better contrast
            p_low, p_high = np.percentile(data, [5, 95])
            if p_high > p_low:
                data = np.clip((data - p_low) / (p_high - p_low) * 255, 0, 255)
            else:
                data = np.clip(data / (np.max(data) or 1) * 255, 0, 255)

            data = data.astype(np.uint8)

            # Resize
            from PIL import Image

            img = Image.fromarray(data, mode="L")
            img.thumbnail((size, size), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


def platesolve_frame(
    filepath: Path,
    astap_binary: str = "astap_cli",
    ra_hint: float | None = None,
    dec_hint: float | None = None,
    timeout: int = 120,
) -> dict | None:
    """Run ASTAP CLI on a FITS file to extract RA/Dec coordinates.

    Does NOT modify the original FITS file — all results go to temp files.

    Args:
        filepath: Path to the FITS file.
        astap_binary: Path to the ASTAP executable (CLI version).
        ra_hint: Approximate RA in degrees (or None for blind solve).
        dec_hint: Approximate Dec in degrees (or None for blind solve).
        timeout: Max seconds to wait for ASTAP.

    Returns:
        Dictionary with 'ra_deg' and 'dec_deg' on success, or None.
    """
    import subprocess
    import tempfile

    tmp_base = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wcs", delete=False) as tmp:
            tmp_base = str(Path(tmp.name).with_suffix(""))
            tmp_wcs = Path(tmp_base + ".wcs")
            tmp_ini = Path(tmp_base + ".ini")

        cmd = [astap_binary, "-f", str(filepath), "-o", tmp_base, "-r", "10"]
        if ra_hint is not None and dec_hint is not None:
            ra_hours = ra_hint / 15.0
            spd = 180.0 - dec_hint
            cmd.extend(["-ra", f"{ra_hours:.4f}", "-spd", f"{spd:.1f}"])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode != 0:
            return None

        if "No solution found" in result.stdout:
            return None

        # Read WCS file (FITS format WCS header with CRVAL1/CRVAL2)
        if tmp_wcs.exists():
            content = tmp_wcs.read_text()
            ra_match = re.search(r"CRVAL1\s*=\s*([\d.E+-]+)", content)
            dec_match = re.search(r"CRVAL2\s*=\s*([\d.E+-]+)", content)
            if ra_match and dec_match:
                return {
                    "ra_deg": float(ra_match.group(1)),
                    "dec_deg": float(dec_match.group(1)),
                }

        # Fallback: parse INI file
        if tmp_ini.exists():
            content = tmp_ini.read_text()
            ra_match = re.search(r"ra\s*=\s*([\d.]+)", content, re.IGNORECASE)
            dec_match = re.search(r"dec\s*=\s*([-\d.]+)", content, re.IGNORECASE)
            if ra_match and dec_match:
                return {
                    "ra_deg": float(ra_match.group(1)),
                    "dec_deg": float(dec_match.group(1)),
                }

        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        if tmp_base:
            for suffix in (".wcs", ".ini", ".txt"):
                p = Path(tmp_base + suffix)
                if p.exists():
                    p.unlink(missing_ok=True)


def scan_directory(
    root: Path,
    recursive: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    progress_callback: Callable[[int, int, Path], None] | None = None,
) -> list[ScannedFrame]:
    """Scan a directory for FITS files and extract metadata."""
    frames: list[ScannedFrame] = []
    errors: list[str] = []
    xisf_skipped = 0

    files = list(find_fits_files(root, recursive=recursive))
    total = len(files)

    # Count XISF files to report
    pattern = "**/*" if recursive else "*"
    for path in root.glob(pattern):
        suffixes = "".join(path.suffixes).lower()
        if any(suffixes.endswith(ext.lower()) for ext in XISF_EXTENSIONS):
            xisf_skipped += 1

    if not progress_callback:
        console.print(f"Found [cyan]{total}[/cyan] FITS files in {root}")
        if xisf_skipped:
            console.print(
                f"[dim]Skipping {xisf_skipped} XISF files (parser not yet implemented)[/dim]"
            )

    if progress_callback:
        progress_callback(0, total, Path())

    with Progress() as progress:
        task = progress.add_task("Scanning FITS headers...", total=total)

        for filepath in files:
            try:
                frame = scan_fits_file(filepath)

                # If header didn't provide key info, try filename fallback
                if not frame.object_name and not frame.frame_type:
                    parsed = parse_filename(filepath)
                    if parsed:
                        if not frame.object_name and "object_name" in parsed:
                            frame.object_name = parsed["object_name"]
                        if not frame.frame_type and "frame_type" in parsed:
                            frame.frame_type = parsed["frame_type"]
                        if frame.exposure is None and "exposure" in parsed:
                            frame.exposure = parsed["exposure"]
                        if frame.gain is None and "gain" in parsed:
                            frame.gain = parsed["gain"]
                        if frame.binning == 1 and "binning" in parsed:
                            frame.binning = parsed["binning"]
                        if not frame.filter_name and "filter_name" in parsed:
                            frame.filter_name = parsed["filter_name"]

                # If OBJECT is still empty, try to extract from filename
                if not frame.object_name:
                    extracted = _extract_object_from_filename(frame.filename)
                    if extracted:
                        frame.object_name = extracted

                if frame.errors:
                    errors.extend(frame.errors)

                frames.append(frame)

            except Exception as e:
                errors.append(f"Error scanning {filepath}: {e}")

            progress.advance(task)

            if progress_callback:
                progress_callback(len(frames), total, filepath)

    if errors:
        console.print(f"\n[yellow]{len(errors)} warnings/errors:[/yellow]")
        for err in errors[:10]:
            console.print(f"  [dim]{err}[/dim]")
        if len(errors) > 10:
            console.print(f"  [dim]... and {len(errors) - 10} more[/dim]")

    console.print(f"\n[green]Scanned {len(frames)} files successfully[/green]")
    return frames
