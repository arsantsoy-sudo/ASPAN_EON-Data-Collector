"""SPHEREx Space Apps 2026 — download.

Original science methods extracted from the working monolithic main.py;
raw FITS and catalog data are never included with this source distribution.
"""
from __future__ import annotations
import argparse
from common import *


def download(args):
    import requests
    from astropy.io import fits
    rows=csv_read(OBS)
    if args.nasa_only:rows=[r for r in rows if r["class"].endswith("_nasa")]
    if args.moving_only:rows=[r for r in rows if r["class"]=="moving"]
    if args.target:rows=[r for r in rows if r["name"]==args.target]
    if args.band:rows=[r for r in rows if r["band"].upper()==args.band.upper()]
    if not rows: raise RuntimeError("No observation candidates. Run search first.")
    if args.limit:rows=rows[:args.limit]
    cfg=settings();ok=errors=0
    session=requests.Session();session.headers["User-Agent"]="SPHEREx-SpaceApps-educational/1.0"
    for i,r in enumerate(rows,1):
        dest=ROOT/r["file"]
        if dest.exists():
            try:
                with fits.open(dest,memmap=False) as f:
                    if "IMAGE" not in f:raise ValueError("No IMAGE")
                ok+=1;continue
            except Exception:
                errors+=1
                print(f"[{i}/{len(rows)}] existing file needs manual inspection: {dest}")
                continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        try:
            resp=None
            for attempt in range(3):
                try:
                    resp=session.get(r["cutout_url"],timeout=int(cfg["request_timeout_seconds"]),stream=True)
                    resp.raise_for_status()
                    tmp=dest.with_suffix(".part")
                    with tmp.open("wb") as f:
                        for chunk in resp.iter_content(2**20):
                            if chunk:f.write(chunk)
                    with fits.open(tmp,memmap=False) as hdul:
                        if "IMAGE" not in hdul:raise ValueError("Missing IMAGE")
                    tmp.replace(dest);break
                except Exception:
                    if resp is not None:resp.close()
                    try:tmp.unlink(missing_ok=True)
                    except UnboundLocalError:pass
                    if attempt==2:raise
                    time.sleep(2**attempt)
                finally:
                    if resp is not None:resp.close()
            ok+=1
            print(f"[{i}/{len(rows)}] {r['name']} {r['band']}: saved",flush=True)
        except Exception as exc:
            errors+=1
            print(f"[{i}/{len(rows)}] {r['name']} {r['band']}: ERROR {exc}",flush=True)
    print("DOWNLOAD finished: available",ok,"errors",errors)
    print("Original V3 outside this project was not modified.")


def main():
    p=argparse.ArgumentParser(description="Download IRSA SPHEREx FITS without overwriting originals")
    p.add_argument("--limit",type=int,default=0)
    p.add_argument("--nasa-only",action="store_true")
    p.add_argument("--moving-only",action="store_true")
    p.add_argument("--target",default="")
    p.add_argument("--band",default="")
    download(p.parse_args())

if __name__ == "__main__":
    main()
