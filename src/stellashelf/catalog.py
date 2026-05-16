"""Astronomical object name normalization.

Normalizes catalog object names to canonical form without spaces:
M51, m51, M 51 → M51
NGC7000, ngc 7000 → NGC7000
IC434, ic 434 → IC434
Non-catalog names are uppercased with single spaces.
"""

import re

_CATALOG_PATTERNS = [
    (r"M\s*0*(\d+[a-zA-Z0-9-]*)", "M", ""),
    (r"NGC\s*0*(\d+[a-zA-Z0-9-]*)", "NGC", ""),
    (r"IC\s*0*(\d+[a-zA-Z0-9-]*)", "IC", ""),
    (r"SH\s*2\s*[-_]?\s*0*(\d+)", "SH2", "-"),
    (r"LDN\s*0*(\d+)", "LDN", " "),
    (r"vdB\s*0*(\d+)", "vdB", " "),
    (r"B\s*0*(\d+)", "B", " "),
    (r"C\s*0*(\d+)", "C", " "),
    (r"Mink\w+\s*0*(\d+)", "Mink", " "),
    (r"Pal\s*0*(\d+)", "Pal", " "),
    (r"Mel\s*0*(\d+)", "Mel", " "),
    (r"Cr\s*0*(\d+)", "Cr", " "),
    (r"Tr\s*0*(\d+)", "Tr", " "),
]


def normalize_object_name(name: str) -> str:
    if not name or not name.strip():
        return ""

    s = name.strip()

    for pattern, prefix, sep in _CATALOG_PATTERNS:
        m = re.match(pattern, s, re.IGNORECASE)
        if m:
            number = m.group(1)
            number = re.sub(r"^0+(\d)", r"\1", number)
            return f"{prefix}{sep}{number}"

    return re.sub(r"\s+", " ", s).strip().upper()
