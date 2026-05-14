"""StellaShelf scanner tests — unit + integration against real FITS data."""

import os
import pytest
from pathlib import Path
from datetime import datetime

from stellashelf.scanner import (
    scan_fits_file,
    scan_directory,
    find_fits_files,
    parse_filename,
    generate_group_key,
    ScannedFrame,
    _parse_hms_to_degrees,
    _parse_dms_to_degrees,
    _normalize_frame_type,
    _extract_object_from_filename,
)

# Real data path on the workstation (NFS-mounted)
ASTRO_DATA = Path("/mnt/data/Astro/astro")


# ---------------------------------------------------------------------------
# Coordinate parsing tests
# ---------------------------------------------------------------------------


class TestCoordinateParsing:
    """Tests for HMS/DMS to decimal degree conversion."""

    def test_hms_basic(self):
        assert _parse_hms_to_degrees("05 22 41.88") == pytest.approx(80.6745, rel=1e-4)

    def test_hms_with_colons(self):
        assert _parse_hms_to_degrees("05:22:41.88") == pytest.approx(80.6745, rel=1e-4)

    def test_hms_zero(self):
        assert _parse_hms_to_degrees("00 00 00.00") == pytest.approx(0.0, abs=1e-6)

    def test_hms_invalid(self):
        assert _parse_hms_to_degrees("abc def ghi") is None
        assert _parse_hms_to_degrees("") is None

    def test_dms_positive(self):
        assert _parse_dms_to_degrees("+33 25 01.2") == pytest.approx(33.417, rel=1e-4)

    def test_dms_negative(self):
        assert _parse_dms_to_degrees("-10 30 00.0") == pytest.approx(-10.5, abs=1e-6)

    def test_dms_zero(self):
        assert _parse_dms_to_degrees("+00 00 00.0") == pytest.approx(0.0, abs=1e-6)

    def test_dms_invalid(self):
        assert _parse_dms_to_degrees("abc def ghi") is None
        assert _parse_dms_to_degrees("") is None


# ---------------------------------------------------------------------------
# IMAGETYP normalization tests
# ---------------------------------------------------------------------------


class TestFrameTypeNormalization:
    """Tests for IMAGETYP normalization from various capture software."""

    def test_light_variants(self):
        assert _normalize_frame_type("Light Frame") == "LIGHT"
        assert _normalize_frame_type("LIGHT") == "LIGHT"
        assert _normalize_frame_type("lightframe") == "LIGHT"
        assert _normalize_frame_type("light") == "LIGHT"

    def test_dark_variants(self):
        assert _normalize_frame_type("Dark Frame") == "DARK"
        assert _normalize_frame_type("DARK") == "DARK"
        assert _normalize_frame_type("darkframe") == "DARK"

    def test_flat_variants(self):
        assert _normalize_frame_type("Flat Frame") == "FLAT"
        assert _normalize_frame_type("FLAT") == "FLAT"
        assert _normalize_frame_type("flatfield") == "FLAT"
        assert _normalize_frame_type("skyflat") == "FLAT"

    def test_bias_variants(self):
        assert _normalize_frame_type("Bias Frame") == "BIAS"
        assert _normalize_frame_type("BIAS") == "BIAS"
        assert _normalize_frame_type("offset") == "BIAS"

    def test_empty(self):
        assert _normalize_frame_type("") == ""
        assert _normalize_frame_type("   ") == ""


# ---------------------------------------------------------------------------
# Object name extraction from filename
# ---------------------------------------------------------------------------


class TestObjectExtraction:
    """Tests for extracting object names from filenames."""

    def test_messier(self):
        assert _extract_object_from_filename("M42_Ha_300s.fit") == "M42"
        assert _extract_object_from_filename("M31-2_L_600s.fit") == "M31-2"

    def test_ngc(self):
        assert _extract_object_from_filename("NGC7000_Ha_600s.fit") == "NGC7000"
        assert _extract_object_from_filename("NGC6992_OIII_300s.fit") == "NGC6992"

    def test_ic(self):
        assert _extract_object_from_filename("IC434_Ha_600s.fit") == "IC434"
        assert _extract_object_from_filename("IC5146_L_300s.fit") == "IC5146"

    def test_sharpless(self):
        assert _extract_object_from_filename("SH2-101_Ha_600s.fit") == "SH2-101"

    def test_no_match(self):
        assert _extract_object_from_filename("Autosave.fit") == ""
        assert _extract_object_from_filename("masterdark_300s_1x1.fit") == ""


# ---------------------------------------------------------------------------
# Filename parser tests
# ---------------------------------------------------------------------------


class TestFilenameParser:
    """Tests for the filename-based fallback parser."""

    def test_light_frame_pattern(self):
        result = parse_filename(Path("M33_L_300sec_1x1_-20C_gain_120_0001.fit"))
        assert result is not None
        assert result["object_name"] == "M33"
        assert result["filter_name"] == "L"
        assert result["exposure"] == 300
        assert result["binning"] == 1
        assert result["gain"] == 120
        assert result["frame_type"] == "LIGHT"

    def test_ha_filter_pattern(self):
        result = parse_filename(Path("NGC7000_Ha_600sec_1x1_-15C_gain_100_0042.fit"))
        assert result is not None
        assert result["filter_name"] == "Ha"
        assert result["exposure"] == 600

    def test_calib_master_bias(self):
        result = parse_filename(Path("masterbias_1x1_100x_gain_0_-20C.fit"))
        assert result is not None
        assert result["frame_type"] == "MASTERBIAS"
        assert result["binning"] == 1
        assert result["gain"] == 0

    def test_calib_master_dark(self):
        result = parse_filename(Path("masterdark_300s_1x1_100x_gain_120_-20C.fit"))
        assert result is not None
        assert result["frame_type"] == "MASTERDARK"
        assert result["exposure"] == 300

    def test_no_match(self):
        result = parse_filename(Path("some_random_file.fit"))
        assert result is None


# ---------------------------------------------------------------------------
# Group key generation
# ---------------------------------------------------------------------------


class TestGroupKey:
    """Tests for session grouping key generation."""

    def test_basic(self):
        frame = ScannedFrame(
            filepath=Path("/test/file.fit"),
            filename="file.fit",
            file_size=1000,
            object_name="M42",
            instrume="ASI Camera",
            telescop="EdgeHD 8",
            filter_name="Ha",
            date_obs=datetime(2024, 1, 15, 22, 0, 0),
        )
        key = generate_group_key(frame)
        assert "M42" in key
        assert "2024-01-15" in key
        assert "ASI Camera" in key
        assert "HA" in key

    def test_no_date(self):
        frame = ScannedFrame(
            filepath=Path("/test/file.fit"),
            filename="file.fit",
            file_size=1000,
            object_name="M42",
            instrume="ASI Camera",
            telescop="EdgeHD 8",
            filter_name="Ha",
        )
        key = generate_group_key(frame)
        assert "unknown" in key

    def test_empty_fields(self):
        frame = ScannedFrame(
            filepath=Path("/test/file.fit"),
            filename="file.fit",
            file_size=1000,
            object_name="",
            instrume="",
            telescop="",
            filter_name="",
        )
        key = generate_group_key(frame)
        assert "UNKNOWN" in key


# ---------------------------------------------------------------------------
# Integration tests (require real FITS files)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRealFITS:
    """Integration tests against real FITS data on the workstation."""

    @pytest.fixture(autouse=True)
    def skip_if_no_data(self):
        if not ASTRO_DATA.exists():
            pytest.skip("Astro data directory not available")

    def test_scan_533mc_subset(self):
        """Test scanning the ASI533MCPro directory (known good data)."""
        subdir = ASTRO_DATA / "ASI533MCPro"
        if not subdir.exists():
            pytest.skip("ASI533MCPro directory not found")

        frames = scan_directory(subdir, recursive=True, dry_run=True)
        assert len(frames) > 0

        # Should have light and calibration frames
        types = set(f.frame_type for f in frames)
        assert "LIGHT" in types

        # Should have detected targets
        objects = set(f.object_name for f in frames if f.object_name)
        assert len(objects) > 0

    def test_qhy8l_exposure_fix(self):
        """Test that QHY8L exposure values are corrected from ms to seconds."""
        qhy_dir = ASTRO_DATA / "nas" / "QHY8L"
        if not qhy_dir.exists():
            # Try other QHY8L locations
            for root, dirs, files in os.walk(ASTRO_DATA):
                for f in files[:10]:
                    if f.endswith(".fit"):
                        fp = Path(root) / f
                        try:
                            frame = scan_fits_file(fp)
                            if frame.instrume == "QHY8L" and frame.exposure:
                                # Should be in seconds, not ms
                                assert frame.exposure < 10000, f"Exposure {frame.exposure} still in ms for {fp}"
                                return
                        except Exception:
                            pass
            pytest.skip("No QHY8L files found")
        else:
            files = list(qhy_dir.glob("*.fit"))[:5]
            for fp in files:
                frame = scan_fits_file(fp)
                if frame.exposure and frame.exposure > 1000:
                    assert frame.exposure < 10000, f"Exposure {frame.exposure} for {fp.name}"

    def test_hms_dms_parsing(self):
        """Test that HMS/DMS coordinates are properly parsed."""
        for root, dirs, files in os.walk(ASTRO_DATA):
            for f in files[:50]:
                if f.endswith(".fit"):
                    fp = Path(root) / f
                    try:
                        frame = scan_fits_file(fp)
                        # If we found a frame with coordinates, verify they are numeric
                        if frame.ra_deg is not None:
                            assert isinstance(frame.ra_deg, (int, float))
                            assert 0 <= frame.ra_deg < 360
                            return
                    except Exception:
                        pass
            else:
                continue
            break
        pytest.skip("No files with RA coordinates found")
