"""Shared paths, CSV I/O, and configuration for the SPHEREx pipeline."""
from __future__ import annotations
import csv
import hashlib
import json
import math
import re
import shutil
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import astronomy as astro

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CAT = DATA / "catalogs"
RAW = DATA / "raw"
TEAM = ROOT / "TEAM_DATASET"
OBS = CAT / "observations.csv"
SEARCH_LOG = CAT / "search_status.csv"
QA = CAT / "quality_report.csv"
TARGETS = ROOT / "targets.csv"
NASA = [
    ("Barnards_Star", "Barnard's Star", "moving_nasa", None, None),
    ("Epsilon_Indi_B", "Epsilon Indi B", "moving_nasa", None, None),
    ("WISE_0855", "WISE 0855", "moving_nasa", 133.795129167, -7.245147222),
    ("RW_Aur", "RW Aur", "variable_nasa", None, None),
    ("R_Dra", "R Dra", "variable_nasa", None, None),
]
OBS_COLUMNS = ["name","class","ra","dec","mjd","band","release","image_url","cutout_url", "file", "source","identity_verified","note", "object_ra", "object_dec", "pair_id"]
QA_COLUMNS = ["name","class","band","release","mjd","file", "file_status","width","height","inside","finite_fraction","flagged_fraction","central_flagged_fraction","extensions","warnings"]
def csv_read(path: Path) -> list[dict]:
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))

def csv_write(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction="ignore");w.writeheader();w.writerows(rows)

def settings() -> dict:
    return json.loads((ROOT/"config.json").read_text(encoding="utf-8"))

def number(s) -> float|None:
    try:
        v=float(s)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError): return None

def canonical(s: str) -> str:
    return re.sub(r"[^a-z0-9]+","",s.lower())
