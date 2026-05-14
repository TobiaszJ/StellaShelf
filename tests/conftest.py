# Test fixtures and helpers for StellaShelf

import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")

# Sample FITS header values extracted from user data (SGP compressed format)
SAMPLE_SGP_HEADER = {
    "OBJECT": "M33",
    "INSTRUME": "ASI Camera (1)",
    "TELESCOP": "POTH Hub",
    "FILTER": "L",
    "EXPOSURE": 300,
    "GAIN": 120,
    "CCD-TEMP": -19.8,
    "DATE-OBS": "2020-11-23T19:54:29.9529674",
    "XBINNING": 1,
    "YBINNING": 1,
    "NAXIS1": 4144,
    "NAXIS2": 2822,
    "IMAGETYP": "LIGHT",
    "FOCALLEN": 676,
    "XPIXSZ": 4.63,
    "YPIXSZ": 4.63,
    "OBSERVER": "Tobiasz Keller",
    "SITENAME": "Wichtrach",
    "CREATOR": "Sequence Generator Pro v3.2.0.613",
}

# Directory structure observed in user data:
# /{Camera}/{Telescope}/{Object}/{Date}/{Lights}
SAMPLE_DIR_STRUCTURE = {
    "cameras": ["ASI183MMPro", "ASI2600MMPro", "ASI2600MMPro2", "ASI294MMPro", "ASI533MCPro"],
    "telescopes": ["_140PH", "_Askar135", "_RASA8"],
    "calibration_prefixes": ["masterbias", "masterdark", "smasterdark"],
}
