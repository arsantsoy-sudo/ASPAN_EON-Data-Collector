
from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import urlsplit
import numpy as np

BAND_UM = {"D1": (0.75, 1.09), "D2": (1.10, 1.62), "D3": (1.63, 2.41),
           "D4": (2.42, 3.82), "D5": (3.83, 4.41), "D6": (4.42, 5.00)}
REQUIRED = ("IMAGE", "FLAGS", "VARIANCE", "ZODI", "WCS-WAVE")


def release_from_url(url: str) -> str:
    """Report release from actual URL"""
    path = urlsplit(url).path.lower()
    for release in ("dr1", "qr3", "qr2", "qr1"):
        if f"/{release}/" in path:
            return release.upper()
    return "UNKNOWN"


def detector_from_filename(filename: str) -> str:
    import re
    hit = re.search(r"_[1-4]D([1-6])_spx", filename, re.I)
    return "D" + hit.group(1) if hit else "UNKNOWN"


def check_fits(path: Path, ra: float | None, dec: float | None) -> dict:
    from astropy.io import fits
    from astropy.wcs import WCS
    from astropy.coordinates import SkyCoord
    import astropy.units as u

    result = {"file_status": "error", "width": "", "height": "", "inside": "",
              "finite_fraction": "", "flagged_fraction": "", "central_flagged_fraction": "",
              "extensions": "", "warnings": ""}
    notes = []
    try:
        with fits.open(path, memmap=False, checksum=False) as hdul:
            names = {h.name for h in hdul}
            missing = [x for x in REQUIRED if x not in names]
            if "EPSF" not in names and "PSF" not in names:
                missing.append("PSF_or_EPSF")
            if missing:
                notes.append("missing_extensions:" + ",".join(missing))
            if "IMAGE" not in names:
                raise ValueError("IMAGE extension is missing")
            data = np.asarray(hdul["IMAGE"].data)
            if data.ndim != 2:
                raise ValueError(f"IMAGE is {data.ndim}D, expected 2D")
            h, w = data.shape
            result.update(width=w, height=h, extensions=",".join(h.name for h in hdul[1:]))
            finite = np.isfinite(data)
            result["finite_fraction"] = round(float(finite.mean()), 5)
            if w < 60 or h < 60:
                notes.append("small_or_partial_cutout")
            if "FLAGS" in names and hdul["FLAGS"].data.shape == data.shape:
                flags = np.asarray(hdul["FLAGS"].data, dtype=np.uint32)
                # SPHEREx SOURCE = bit 21, a source marker, not a blanket rejection.
                other_flags = (flags & np.uint32(0xFFDFFFFF)) != 0
                result["flagged_fraction"] = round(float(other_flags.mean()), 5)
                y0, x0 = h // 2, w // 2
                region = other_flags[max(0,y0-2):min(h,y0+3),max(0,x0-2):min(w,x0+3)]
                result["central_flagged_fraction"] = round(float(region.mean()), 5)
                if result["central_flagged_fraction"] >= 0.5:
                    notes.append("many_center_non_source_flags")
            if ra is not None and dec is not None:
                try:
                    wcs = WCS(hdul["IMAGE"].header, naxis=2)
                    x, y = wcs.world_to_pixel(SkyCoord(ra*u.deg, dec*u.deg, frame="icrs"))
                    result["inside"] = bool(np.isfinite(x+y) and 0 <= x < w and 0 <= y < h)
                    if not result["inside"]:
                        notes.append("reference_coordinate_outside_cutout")
                except Exception as exc:
                    notes.append("wcs_review:" + type(exc).__name__)
            result["file_status"] = "review_needed" if notes else "structurally_ok"
    except Exception as exc:
        notes.append(type(exc).__name__ + ": " + str(exc)[:200])
    result["warnings"] = ";".join(notes)
    return result


def make_png(fits_path: Path, png_path: Path, label: str) -> bool:
    from astropy.io import fits
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from astropy.visualization import ImageNormalize, AsinhStretch, PercentileInterval
    try:
        with fits.open(fits_path, memmap=False) as hdul:
            data = np.asarray(hdul["IMAGE"].data, dtype=float)
        good = np.isfinite(data)
        if not np.any(good):
            return False
        png_path.parent.mkdir(parents=True, exist_ok=True)
        interval = PercentileInterval(99.0)
        vmin, vmax = interval.get_limits(data[good])
        if vmin >= vmax:
            vmax = vmin + 1
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.imshow(data, cmap="magma", origin="lower", norm=ImageNormalize(vmin=vmin,vmax=vmax,stretch=AsinhStretch()))
        ax.set(title=label, xlabel="Pixel x", ylabel="Pixel y")
        fig.tight_layout(); fig.savefig(png_path, dpi=115); plt.close(fig)
        return True
    except Exception:
        return False


def choose_spaced(rows: list[dict], count: int) -> list[dict]:
    rows = sorted(rows, key=lambda r: float(r["mjd"]))
    if len(rows) <= count:
        return rows
    indices = sorted(set(int(round(i*(len(rows)-1)/(count-1))) for i in range(count))) if count > 1 else [0]
    return [rows[i] for i in indices]


def position_at_mjd(target: dict, mjd: float) -> tuple[float, float, str]:
    if target["name"] != "Barnards_Star":
        return float(target["ra"]), float(target["dec"]), "catalog_position_unpropagated"
    from astropy.coordinates import SkyCoord, Distance
    from astropy.time import Time
    import astropy.units as u
    # J2000 parameters as used in the project's prior successful local check.
    star = SkyCoord(ra=269.452076959*u.deg, dec=4.693364967*u.deg,
        pm_ra_cosdec=-801.551*u.mas/u.yr, pm_dec=10362.394*u.mas/u.yr,
        distance=Distance(parallax=546.9759*u.mas),
        radial_velocity=-110.11*u.km/u.s, obstime=Time("J2000"),frame="icrs")
    at = star.apply_space_motion(new_obstime=Time(float(mjd), format="mjd",scale="utc"))
    return float(at.ra.deg),float(at.dec.deg),"proper_motion_propagated_Barnard"


def balanced_epochs(candidates: list[dict], count: int) -> list[dict]:
    if count < 1:return []
    by_release={rel:[] for rel in ("DR1","QR3","QR2")}
    for r in candidates:
        if r["release"] in by_release:by_release[r["release"]].append(r)
    releases=[rel for rel in ("DR1","QR3") if by_release[rel]]
    if not releases and by_release["QR2"]:releases=["QR2"]
    if not releases:return []
    pools={}
    for rel in releases:
        seen=set();pools[rel]=[]
        for r in sorted(by_release[rel],key=lambda x:float(x["mjd"])):
            key=r["image_url"]
            if key not in seen: pools[rel].append(r);seen.add(key)
    quota={rel:0 for rel in releases}
    for _ in range(count):
        possibilities=[r for r in releases if quota[r]<len(pools[r])]
        if not possibilities:break
        chosen=min(possibilities,key=lambda r:(quota[r], -len(pools[r]), releases.index(r)))
        quota[chosen]+=1
    result=[]
    for rel in releases:
        result+=choose_spaced(pools[rel],quota[rel])
    return sorted(result,key=lambda r:float(r["mjd"]))
