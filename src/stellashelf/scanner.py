"""StellaShelf FITS/XISF header scanner.

Recursively scans directories for FITS files, extracts metadata from headers,
and groups frames into sessions.

Supports:
- Standard FITS files
- Gzip-compressed FITS (SGP format) where headers live in HDU[1]
- Filename-based fallback parsing
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

from astropy.io import fits
from rich.console import Console
from rich.progress import Progress

console = Console()

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


def _get_header_value(header: fits.Header, key: str, default=None):
    """Get a value from a FITS header, handling alternate key names."""
    # Try exact match first
    value = header.get(key)
    if value is not None:
        return value
    # Try common aliases
    aliases = {
        "EXPOSURE": ["EXPTIME", "EXP_TIME"],
        "CCD-TEMP": ["CCDTEMP", "TEMPERAT"],
        "FILTER": ["FILTERS", "FILTNAME"],
        "GAIN": ["EGAIN", "EMGAIN"],
        "DATE-OBS": ["DATE_OBS", "DATEOBS"],
        "INSTRUME": ["CAMERA", "CAMNAME"],
    }
    for alias in aliases.get(key, []):
        value = header.get(alias)
        if value is not None:
            return value
    return default


def _extract_header(hdu_list: fits.HDUList) -> dict:
    """Extract relevant headers from a FITS file.

    For compressed FITS files (SGP format), headers contain most
    metadata in the first extension HDU rather than the primary HDU.
    We check both and prefer the extension header values.
    """
    primary = hdu_list[0].header

    # For compressed FITS, the actual image header is in the first extension
    # Keywords are duplicated there with the actual values
    extension = hdu_list[1].header if len(hdu_list) > 1 else primary

    # Merge: use extension values where available, fall back to primary
    result = {}
    keys_to_extract = [
        "OBJECT", "INSTRUME", "TELESCOP", "FILTER", "EXPOSURE",
        "GAIN", "CCD-TEMP", "DATE-OBS", "DATE-LOC", "XBINNING",
        "YBINNING", "NAXIS1", "NAXIS2", "IMAGETYP", "FOCALLEN",
        "XPIXSZ", "YPIXSZ", "RA", "DEC", "CRVAL1", "CRVAL2",
        "SITENAME", "OBSERVER", "CREATOR", "BAYERPAT",
    ]

    for key in keys_to_extract:
        # Prefer extension header for compressed files
        value = _get_header_value(extension, key)
        if value is None and extension is not primary:
            value = _get_header_value(primary, key)
        if value is not None:
            result[key] = value

    return result


def scan_fits_file(filepath: Path) -> ScannedFrame:
    """Scan a single FITS file and extract metadata.

    Handles both standard and gzip-compressed FITS files.
    """
    frame = ScannedFrame(
        filepath=filepath,
        filename=filepath.name,
        file_size=filepath.stat().st_size,
    )

    try:
        with fits.open(str(filepath)) as hdul:
            header = _extract_header(hdul)

            # String fields - strip whitespace
            frame.object_name = str(header.get("OBJECT", "")).strip()
            frame.instrume = str(header.get("INSTRUME", "")).strip()
            frame.telescop = str(header.get("TELESCOP", "")).strip()
            frame.filter_name = str(header.get("FILTER", "")).strip()
            frame.site_name = str(header.get("SITENAME", "")).strip()
            frame.observer = str(header.get("OBSERVER", "")).strip()
            frame.creator = str(header.get("CREATOR", "")).strip()

            # Normalize IMAGETYP: "Light Frame" → LIGHT, "Dark Frame" → DARK, etc.
            raw_type = str(header.get("IMAGETYP", "")).strip()
            if "light" in raw_type.lower():
                frame.frame_type = "LIGHT"
            elif "dark" in raw_type.lower():
                frame.frame_type = "DARK"
            elif "flat" in raw_type.lower():
                frame.frame_type = "FLAT"
            elif "bias" in raw_type.lower():
                frame.frame_type = "BIAS"
            else:
                frame.frame_type = raw_type.upper() if raw_type else ""

            # Numeric fields
            exposure = header.get("EXPOSURE")
            frame.exposure = float(exposure) if exposure is not None else None

            gain = header.get("GAIN")
            frame.gain = int(gain) if gain is not None else None

            ccd_temp = header.get("CCD-TEMP")
            frame.ccd_temp = float(ccd_temp) if ccd_temp is not None else None

            binning = header.get("XBINNING")
            frame.binning = int(binning) if binning is not None else 1

            # Image dimensions
            frame.width = header.get("NAXIS1")
            frame.height = header.get("NAXIS2")

            # Pixel size
            pxsz = header.get("XPIXSZ")
            frame.pixel_size_um = float(pxsz) if pxsz is not None else None

            # Focal length
            fl = header.get("FOCALLEN")
            frame.focal_length_mm = float(fl) if fl is not None else None

            # Coordinates
            ra = header.get("RA") or header.get("CRVAL1")
            frame.ra_deg = float(ra) if ra is not None else None
            dec = header.get("DEC") or header.get("CRVAL2")
            frame.dec_deg = float(dec) if dec is not None else None

            # Date
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
                    pass  # Non-critical

    except Exception as e:
        frame.errors.append(f"FITS read error: {e}")

    # Compute file hash for deduplication (async-friendly: could be done later)
    # Skipping hash for now to keep scan fast; can be added in a post-processing step

    return frame


# ---------------------------------------------------------------------------
# Filename-based fallback parser
# ---------------------------------------------------------------------------

# Pattern: M33_L_300sec_1x1_-20C_gain_120_0001.fit
# Pattern: masterbias_1x1_100x_gain_0_-20C.fit
# Pattern: masterdark_300s_1x1_100x_gain_120_-20C.fit

LIGHT_PATTERN = re.compile(
    r"^(?P<object>\S+?)_"  # M33, NGC7000, etc.
    r"(?P<filter>\w+)_"  # L, Ha, OIII, SII, RGB
    r"(?P<exposure>\d+)sec_"  # 300
    r"(?P<binning>\d+)x\d+_"  # 1x1
    r"-?\d+C_"  # temperature
    r"gain_(?P<gain>\d+)_"  # gain value
    r"(?P<seq>\d+)",  # sequence number
    re.IGNORECASE,
)

CALIB_PATTERN = re.compile(
    r"^(?P<type>master(?:bias|dark|flat)|smasterdark)_"
    r"(?:(?P<exposure>\d+)s_)?"  # optional exposure (darks only)
    r"(?P<binning>\d+)x\d+_?"  # 1x1
    r"(?:\d+x_)?"  # 100x (subframe count)
    r"gain_(?P<gain>\d+)_"  # gain value
    r"-?\d+C",  # temperature
    re.IGNORECASE,
)


def parse_filename(filepath: Path) -> dict | None:
    """Try to extract metadata from the filename as a fallback.

    Returns None if the filename doesn't match known patterns.
    """
    name = filepath.stem

    # Try light frame pattern first
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

    # Try calibration file pattern
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

FITS_EXTENSIONS = {".fit", ".fits", ".fit.gz", ".fits.gz", ".FIT", ".FITS", ".xisf"}


def find_fits_files(root: Path, recursive: bool = True) -> Iterator[Path]:
    """Find all FITS/XISF files in a directory tree."""
    pattern = "**/*" if recursive else "*"
    for path in root.glob(pattern):
        suffixes = "".join(path.suffixes).lower()
        if any(suffixes.endswith(ext.lower()) for ext in FITS_EXTENSIONS):
            yield path


def generate_group_key(frame: ScannedFrame) -> str:
    """Generate a unique grouping key for a session.

    Group by: object + date (day) + instrument + telescope + filter
    """
    date_str = frame.date_obs.strftime("%Y-%m-%d") if frame.date_obs else "unknown"
    # Clean up component names for grouping
    obj = frame.object_name.strip().upper() or "UNKNOWN"
    inst = frame.instrume.strip() or "UNKNOWN"
    tel = frame.telescop.strip() or "UNKNOWN"
    filt = frame.filter_name.strip().upper() or "UNKNOWN"

    return f"{obj}|{date_str}|{inst}|{tel}|{filt}"


def scan_directory(
    root: Path,
    recursive: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[ScannedFrame]:
    """Scan a directory for FITS files and extract metadata.

    Args:
        root: Root directory to scan
        recursive: Whether to scan subdirectories
        dry_run: If True, don't write to database
        verbose: If True, print detailed progress

    Returns:
        List of ScannedFrame objects with extracted metadata
    """
    frames: list[ScannedFrame] = []
    errors: list[str] = []

    files = list(find_fits_files(root, recursive=recursive))
    console.print(f"Found [cyan]{len(files)}[/cyan] FITS files in {root}")

    with Progress() as progress:
        task = progress.add_task("Scanning FITS headers...", total=len(files))

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
                # Handles patterns like M42_Ha.fit, NGC7000_L_300s.fit, etc.
                if not frame.object_name:
                    # Try to extract object name from filename: M42, NGC7000, IC434, etc.
                    name_match = re.match(r"^([A-Z]{1,2}\d+[a-zA-Z]?)_", frame.filename)
                    if name_match:
                        frame.object_name = name_match.group(1)

                if frame.errors:
                    errors.extend(frame.errors)

                frames.append(frame)

            except Exception as e:
                errors.append(f"Error scanning {filepath}: {e}")

            progress.advance(task)

    if errors:
        console.print(f"\n[yellow]{len(errors)} warnings/errors:[/yellow]")
        for err in errors[:10]:
            console.print(f"  [dim]{err}[/dim]")
        if len(errors) > 10:
            console.print(f"  [dim]... and {len(errors) - 10} more[/dim]")

    console.print(f"\n[green]Scanned {len(frames)} files successfully[/green]")
    return frames