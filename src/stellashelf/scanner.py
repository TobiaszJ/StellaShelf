"""StellaShelf FITS/XISF header scanner.

Recursively scans directories for FITS files, extracts metadata from headers,
and groups frames into sessions.

Supports:
- Standard FITS files
- Gzip-compressed FITS (SGP format) where headers live in HDU[1]
- Filename-based fallback parsing
- XISF files (skipped with warning — parser not yet implemented)
"""

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np
from astropy.io import fits
from rich.console import Console
from rich.progress import Progress

console = Console()


# ---------------------------------------------------------------------------
# Coordinate Parsing
# ---------------------------------------------------------------------------

def _parse_hms_to_degrees(hms_str: str) -> Optional[float]:
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


def _parse_dms_to_degrees(dms_str: str) -> Optional[float]:
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
    exposure: Optional[float] = None
    gain: Optional[int] = None
    ccd_temp: Optional[float] = None
    binning: int = 1
    date_obs: Optional[datetime] = None
    date_local: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    pixel_size_um: Optional[float] = None
    focal_length_mm: Optional[float] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
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
        "OBJECT", "INSTRUME", "TELESCOP", "FILTER", "EXPOSURE",
        "GAIN", "CCD-TEMP", "DATE-OBS", "DATE-LOC", "XBINNING",
        "YBINNING", "NAXIS1", "NAXIS2", "IMAGETYP", "FOCALLEN",
        "XPIXSZ", "YPIXSZ", "RA", "DEC", "CRVAL1", "CRVAL2",
        "SITENAME", "OBSERVER", "CREATOR", "BAYERPAT",
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
    "light": "LIGHT", "light frame": "LIGHT", "lightframe": "LIGHT",
    "dark": "DARK", "dark frame": "DARK", "darkframe": "DARK",
    "flat": "FLAT", "flat frame": "FLAT", "flatfield": "FLAT", "flat field": "FLAT",
    "bias": "BIAS", "bias frame": "BIAS", "biasframe": "BIAS", "offset": "BIAS",
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
    for ext in (".fit", ".fits", ".fit.gz", ".xisf"):
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
            return m.group(1).strip().upper()

    m = re.match(r"^([A-Z]{1,5}\s*\d+[a-zA-Z0-9-]*)", stem, re.IGNORECASE)
    if m:
        return m.group(1).strip().upper()

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

            # String fields
            frame.object_name = str(header.get("OBJECT", "")).strip()
            frame.instrume = str(header.get("INSTRUME", "")).strip()
            frame.telescop = str(header.get("TELESCOP", "")).strip()
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
            if frame.instrume == "QHY8L" and frame.exposure is not None and frame.exposure >= 10000:
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


def parse_filename(filepath: Path) -> Optional[dict]:
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


def generate_thumbnail(filepath: Path, size: int = 200) -> Optional[bytes]:
    """Generate a JPEG thumbnail from a FITS file.
    
    Args:
        filepath: Path to the FITS file.
        size: Maximum dimension (width/height) in pixels.
    
    Returns:
        JPEG bytes, or None if thumbnail generation fails.
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
            img = Image.fromarray(data, mode='L')
            img.thumbnail((size, size), Image.LANCZOS)
            
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            return buf.getvalue()
    except Exception:
        return None


def scan_directory(
    root: Path,
    recursive: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    progress_callback: Optional[Callable[[int, int, Path], None]] = None,
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
            console.print(f"[dim]Skipping {xisf_skipped} XISF files (parser not yet implemented)[/dim]")

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