import csv
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

DEEP_SKY_TYPES = frozenset(
    {
        "G",
        "GPair",
        "GTrpl",
        "GGroup",
        "PN",
        "HII",
        "Neb",
        "EmN",
        "RfN",
        "SNR",
        "OCl",
        "GCl",
        "Cl+N",
        "DrkN",
        "*Ass",
        "Nova",
    }
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Load OpenNGC catalog from bundled CSVs.

    Returns cached dict with numpy arrays:
      ra_deg, dec_deg, majax, names, types, common_names, messier
    """
    rows = []
    for fn in ["NGC.csv", "addendum.csv"]:
        fp = DATA_DIR / fn
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                otype = row.get("Type", "")
                if not otype or not row.get("RA") or not row.get("Dec"):
                    continue
                if otype in ("*", "**", "Dup", "NonEx", "Other"):
                    continue
                ra_parts = row["RA"].split(":")
                ra_deg = (
                    float(ra_parts[0]) + float(ra_parts[1]) / 60 + float(ra_parts[2]) / 3600
                ) * 15
                dec_str = row["Dec"]
                sign = -1 if dec_str.startswith("-") else 1
                d_parts = dec_str.lstrip("+-").split(":")
                dec_deg = sign * (
                    float(d_parts[0]) + float(d_parts[1]) / 60 + float(d_parts[2]) / 3600
                )
                majax = float(row.get("MajAx", 0) or 0)
                rows.append(
                    {
                        "name": row["Name"].strip(),
                        "ra_deg": ra_deg,
                        "dec_deg": dec_deg,
                        "majax": majax,
                        "type": otype,
                        "common_names": row.get("Common names", "").strip(),
                        "messier": row.get("M", "").strip(),
                        "constellation": row.get("Const", "").strip(),
                    }
                )

    coords = np.array([[r["ra_deg"], r["dec_deg"]] for r in rows], dtype=np.float64)
    majax_arr = np.array([r["majax"] for r in rows], dtype=np.float64)
    return {
        "rows": rows,
        "coords": coords,
        "majax": majax_arr,
    }


def _angular_dist(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    dra = (ra1 - ra2) * math.cos(math.radians((dec1 + dec2) / 2))
    ddec = dec1 - dec2
    return math.sqrt(dra * dra + ddec * ddec)


def find_dominant_object(
    ra_deg: float,
    dec_deg: float,
    radius_deg: float = 0.5,
) -> dict | None:
    """Find the largest deep-sky object within radius of given coordinates.

    Returns dict with keys:
      name, common_name, target_name, messier, type,
      ra_deg, dec_deg, majax, dist_deg, constellation
    or None if nothing found.
    """
    cat = load_catalog()
    coords = cat["coords"]
    majax = cat["majax"]
    rows = cat["rows"]

    dra = (coords[:, 0] - ra_deg) * math.cos(math.radians(dec_deg))
    ddec = coords[:, 1] - dec_deg
    dists = np.sqrt(dra * dra + ddec * ddec)

    mask = dists <= radius_deg
    if not np.any(mask):
        return None

    candidates = np.where(mask)[0]
    best_idx = candidates[np.argmax(majax[mask])]
    best = rows[best_idx]
    return {
        "name": best["name"],
        "ra_deg": best["ra_deg"],
        "dec_deg": best["dec_deg"],
        "majax": best["majax"],
        "type": best["type"],
        "common_names": best["common_names"],
        "messier": best["messier"],
        "constellation": best["constellation"],
        "dist_deg": float(dists[best_idx]),
    }


def compute_search_radius(
    width_px: int | None,
    height_px: int | None,
    pixel_size_um: float | None,
    focal_length_mm: float | None,
    default_deg: float = 0.5,
) -> float:
    """Compute search radius from frame dimensions."""
    if not all([width_px, height_px, pixel_size_um, focal_length_mm]):
        return default_deg
    if focal_length_mm <= 0 or pixel_size_um <= 0:
        return default_deg
    fov_w = (width_px * pixel_size_um / 1000) / focal_length_mm * 57.296
    fov_h = (height_px * pixel_size_um / 1000) / focal_length_mm * 57.296
    return max(fov_w, fov_h) / 2


def resolve_target_name(obj: dict) -> str:
    """Resolve the canonical target name from an OpenNGC object.

    Priority: common_name → Messier → NGC/IC name.
    """
    common = obj.get("common_names", "").strip()
    if common:
        return common

    messier = obj.get("messier", "").strip()
    if messier:
        m_num = messier.lstrip("0")
        return f"M{m_num}"

    return obj.get("name", "").strip()
