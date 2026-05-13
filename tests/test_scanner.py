"""StellaShelf scanner integration test against real FITS data.

Running this test requires access to the astro data directory.
It is marked as integration test and skipped in CI.
"""

import os
import pytest
from pathlib import Path

from stellashelf.scanner import (
    scan_fits_file,
    scan_directory,
    find_fits_files,
    parse_filename,
    generate_group_key,
)

# Real data path on the workstation (NFS-mounted)
ASTRO_DATA = Path("/mnt/data/Astro/astro")
WORKSTATION_DATA = None

# Check if we're running on the workstation or have NFS mounted
if ASTRO_DATA.exists():
    WORKSTATION_DATA = ASTRO_DATA
else:
    # Try SSH path
    pass


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
        assert result["object_name"] == "NGC7000"
        assert result["filter_name"] == "Ha"
        assert result["exposure"] == 600

    def test_master_bias_pattern(self):
        result = parse_filename(Path("masterbias_1x1_100x_gain_0_-20C.fit"))
        assert result is not None
        assert result["frame_type"] == "MASTERBIAS"
        assert result["binning"] == 1
        assert result["gain"] == 0

    def test_master_dark_pattern(self):
        result = parse_filename(Path("masterdark_300s_1x1_100x_gain_120_-20C.fit"))
        assert result is not None
        assert result["frame_type"] == "MASTERDARK"
        assert result["exposure"] == 300
        assert result["gain"] == 120

    def test_smasterdark_pattern(self):
        result = parse_filename(Path("smasterdark_60s_1x1_100x_gain_0_-20C.fit"))
        assert result is not None
        assert result["frame_type"] == "SMASTERDARK"

    def test_non_matching_filename(self):
        result = parse_filename(Path("random_image.jpg"))
        assert result is None

    def test_oiii_filter(self):
        result = parse_filename(Path("NGC6888_OIII_300sec_1x1_-20C_gain_120_0015.fit"))
        assert result is not None
        assert result["filter_name"] == "OIII"


# ---------------------------------------------------------------------------
# Grouping key tests
# ---------------------------------------------------------------------------


class TestGroupKey:
    """Tests for session group key generation."""

    def test_basic_grouping(self):
        from stellashelf.scanner import ScannedFrame
        from datetime import datetime

        frame = ScannedFrame(
            filepath=Path("/test/M33_L_300s.fit"),
            filename="M33_L_300s.fit",
            file_size=16000000,
            object_name="M33",
            instrume="ASI Camera (1)",
            telescop="POTH Hub",
            filter_name="L",
            date_obs=datetime(2020, 11, 23, 19, 54, 29),
        )
        key = generate_group_key(frame)
        assert "M33" in key
        assert "2020-11-23" in key