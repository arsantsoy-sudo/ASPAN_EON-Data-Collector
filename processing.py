"""SPHEREx Space Apps 2026 - processing.
Original science methods extracted from the working monolithic main.py;
raw FITS and catalog data are never included with this source distribution.
"""
from __future__ import annotations
import argparse
from common import *


def validate(args):
    from astropy.io import fits
    rows=[]
    for r in csv_read(OBS):
        p=ROOT/r["file"]
        ra,dec=number(r["ra"]),number(r["dec"])
        if not p.is_file():
            result={"file_status":"missing","warnings":"not_downloaded"}
        else:
            result=astro.check_fits(p,ra,dec)
        rows.append({**{k:r.get(k,"") for k in ("name","class","band","release","mjd","file")},**result})
    csv_write(QA,rows,QA_COLUMNS)
    print("QUALITY:",dict(Counter(r["file_status"] for r in rows)))

def compare(args):
    try:
        from reproject import reproject_interp
    except ImportError as exc:
        raise SystemExit("For this optional command: python -m pip install reproject") from exc
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from astropy.io import fits
    from astropy.wcs import WCS
    import numpy as np

    first=Path(args.first);second=Path(args.second)
    if not first.is_file() or not second.is_file():
        raise SystemExit("Specify two existing FITS paths")
    with fits.open(first,memmap=False) as h1, fits.open(second,memmap=False) as h2:
        image1=np.asarray(h1["IMAGE"].data,dtype=float)
        image2=np.asarray(h2["IMAGE"].data,dtype=float)
        wcs1=WCS(h1["IMAGE"].header,naxis=2)
        wcs2=WCS(h2["IMAGE"].header,naxis=2)
        aligned2,footprint=reproject_interp((image2,wcs2),wcs1,shape_out=image1.shape)
    good=np.isfinite(image1)&np.isfinite(aligned2)&(footprint>0)
    if good.sum()<100:
        raise SystemExit("Insufficient common sky overlap for useful comparison")
    
    def stretch(image):
        low,high=np.nanpercentile(image[good],[2,99.5])
        scaled=np.clip((image-low)/max(high-low,1e-12),0,1)
        return np.arcsinh(scaled/.08)/np.arcsinh(1/.08)
    i1,i2=stretch(image1),stretch(aligned2)
    diff=np.where(good,i2-i1,np.nan)
    limit=max(float(np.nanpercentile(np.abs(diff[good]),99)),.03)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    axes[0].imshow(np.where(good,i1,np.nan),origin="lower",cmap="magma",vmin=0,vmax=1)
    axes[1].imshow(np.where(good,i2,np.nan),origin="lower",cmap="magma",vmin=0,vmax=1)
    axes[2].imshow(diff,origin="lower",cmap="PuOr_r",vmin=-limit,vmax=limit)
    for ax,title in zip(axes,["Epoch A", "Epoch B registered", "Display difference (NOT flux)"]):
        ax.set_title(title)
    fig.tight_layout();fig.savefig(path,dpi=130);plt.close(fig)
    print("REGISTERED PREVIEW:",path,"common pixels",int(good.sum()))
    print("This is a WCS alignment demonstration, NOT a measured motion or a flux light curve.")


def main():
    p=argparse.ArgumentParser(description="Validate real SPHEREx FITS and compare frames by WCS")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("validate",help="Inspect all downloaded FITS")
    cm=sub.add_parser("compare",help="WCS-register two FITS for display (not measured motion)")
    cm.add_argument("--first",required=True)
    cm.add_argument("--second",required=True)
    cm.add_argument("--output",default="data/registered_example.png")
    a=p.parse_args()
    {"validate":validate,"compare":compare}[a.command](a)

if __name__ == "__main__":
    main()
