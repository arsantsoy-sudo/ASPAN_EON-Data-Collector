"""SPHEREx Space Apps 2026 — delivery.

Original science methods extracted from the working monolithic main.py;
raw FITS and catalog data are never included with this source distribution.
"""
from __future__ import annotations
import argparse
from common import *

from search import get_targets
from processing import validate


def sequences(args):
    obs=csv_read(OBS); quality={r["file"]:r for r in csv_read(QA)}
    groups=defaultdict(list)
    for r in obs:
        if (ROOT/r["file"]).exists() and quality.get(r["file"],{}).get("file_status") not in ("error","missing"):
            groups[(r["name"],r["band"])].append(r)
    result=[]
    for (name,band),rows in sorted(groups.items()):
        release="+".join(sorted(set(r["release"] for r in rows)))
        rows.sort(key=lambda x:float(x["mjd"]))
        unique_dates=len(set(round(float(r["mjd"]),3) for r in rows))
        moving=any(r["class"] in ("moving","moving_nasa") for r in rows)
        result.append({"name":name,"band":band,"release":release,"fits_count":len(rows),
                       "approx_unique_epochs":unique_dates,"mjd_first":rows[0]["mjd"],"mjd_last":rows[-1]["mjd"],
                       "file_list":";".join(r["file"] for r in rows),
                       "registration_status":"NOT_DONE", "measured_motion_status":"NOT_MEASURED",
                       "photometry_status":"NOT_MEASURED", "warning":"moving_target_centered" if moving and rows[0]["source"].startswith("MOST/") else "wavelength_match_required;DR1_QR3_cross_calibration_required"})
    csv_write(CAT/"sequences.csv",result,["name","band","release","fits_count","approx_unique_epochs",
          "mjd_first","mjd_last","file_list","registration_status","measured_motion_status","photometry_status","warning"])
    print("SEQUENCES:",len(result),"groups, registration not claimed")

def export(args):
    """Clean, atomic-ish handoff; no scripts, no NPZ, no preexisting junk catalogs."""
    if not QA.exists(): validate(args)
    if not (CAT/"sequences.csv").exists():sequences(args)
    obs=csv_read(OBS);quality={r["file"]:r for r in csv_read(QA)}
    dest=TEAM
    if dest.exists():
        i=2
        while (ROOT/f"TEAM_DATASET_{i:02d}").exists():i+=1
        dest=ROOT/f"TEAM_DATASET_{i:02d}"
    (dest/"fits").mkdir(parents=True)
    (dest/"catalogs").mkdir()
    (dest/"previews").mkdir()
    meta=[];per_object=defaultdict(list);per_band=defaultdict(list); missing=[]; count_png=Counter();cfg=settings()
    for r in obs:
        src=ROOT/r["file"]
        exists=src.is_file()
        q=quality.get(r["file"],{})
        status=q.get("file_status","not_validated") if exists else "missing"
        rel_path=""
        if exists:
            rel=Path("fits")/r["class"]/r["name"]/src.name
            dst=dest/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst);rel_path=rel.as_posix()
            per_object[r["name"]].append(r);per_band[(r["name"],r["band"])].append(r)
            if (r["name"] in cfg["png_targets"] or r["class"].endswith("_nasa")) and count_png[r["name"]]<cfg["png_limit_per_target"]:
                preview=dest/"previews"/r["name"]/(src.stem+".png")
                if astro.make_png(src,preview,f"{r['name']} | {r['band']} | MJD {r['mjd']}"):
                    count_png[r["name"]]+=1
        else:
            missing.append({"name":r["name"],"band":r["band"],"mjd":r["mjd"],"source_url":r["image_url"]})
        lo,hi=astro.BAND_UM.get(r["band"],("",""))
        meta.append({"name":r["name"],"class":r["class"],"mjd":r["mjd"],"ra":r["ra"],"dec":r["dec"],
                     "detector":r["band"],"band_min_um":lo,"band_max_um":hi,"exact_wavelength_um":"",
                     "release":r["release"],"file":rel_path,"status":status,
                     "object_ra":r.get("object_ra", ""), "object_dec":r.get("object_dec", ""),
                     "pair_id":r.get("pair_id", ""),
                     "warnings":q.get("warnings", ""),"source_url":r["image_url"],"cutout_url":r["cutout_url"],
                     "source_identification":"unverified"})
    md_fields=["name","class","mjd","ra","dec","detector","band_min_um","band_max_um", "exact_wavelength_um",
               "release","file","status","warnings","source_url","cutout_url","source_identification",
               "object_ra","object_dec","pair_id"]
    csv_write(dest/"catalogs"/"metadata.csv",meta,md_fields)
    summaries=[]
    for t in get_targets():
        rows=per_object[t["name"]]
        summaries.append({"name":t["name"],"class":t["class"],"fits_saved":len(rows),
                          "detectors":",".join(sorted(set(r["band"] for r in rows))),
                          "unique_mjd_approx":len(set(round(float(r["mjd"]),3) for r in rows)) if rows else 0,
                          "found_in_catalog":sum(r["name"]==t["name"] for r in obs)})
    csv_write(dest/"catalogs"/"object_summary.csv",summaries,["name","class","fits_saved","detectors","unique_mjd_approx","found_in_catalog"])
    bands=[]
    for (name,band),rows in sorted(per_band.items()):
        lo,hi=astro.BAND_UM.get(band,("",""))
        bands.append({"name":name,"band":band,"fits_saved":len(rows),"wavelength_min_um":lo,"wavelength_max_um":hi})
    csv_write(dest/"catalogs"/"band_summary.csv",bands,["name","band","fits_saved","wavelength_min_um","wavelength_max_um"])
    qa_out=[]
    for r in meta:
        qa_out.append({"name":r["name"],"file":r["file"],"status":r["status"],"warnings":r["warnings"]})
    csv_write(dest/"catalogs"/"quality_report.csv",qa_out,["name","file","status","warnings"])
    # Map original paths to exported paths without guessing or ambiguous joins.
    by_original = {}
    for r in obs:
        src = ROOT / r["file"]
        if src.is_file():
            by_original[r["file"]] = (Path("fits") / r["class"] / r["name"] / src.name).as_posix()
    seqs = []
    for s in csv_read(CAT / "sequences.csv"):
        paths = [by_original[x] for x in s["file_list"].split(";") if x in by_original]
        seqs.append({**s, "file_list": ";".join(paths), "fits_count": len(paths)})
    if seqs:
        csv_write(dest / "catalogs" / "sequences.csv", seqs, list(seqs[0].keys()))
    summary={"targets":len(summaries),"fits_copied":sum(bool(r["file"]) for r in meta),
             "missing_or_unavailable":len(missing),"png":sum(count_png.values()),
             "by_class":dict(Counter(r["class"] for r in meta if r["file"])),
             "source_dataset":"SPHEREx Space Apps 2026", "scientific_motion_verified":False}
    (dest/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (dest/"README.md").write_text(README_TEAM,encoding="utf-8")
    # Verify every exported path; report absence explicitly.
    not_found=[r["file"] for r in meta if r["file"] and not (dest/r["file"]).exists()]
    if not_found:raise RuntimeError(f"Export verification failed: {not_found[:3]}")
    print("DELIVERY:",dest,"\nSUMMARY:",json.dumps(summary,ensure_ascii=False))

def audit(args):
    """Summarize actual downloaded files and detector/release balance without hiding gaps."""
    obs=csv_read(OBS)
    filtered=[r for r in obs if not args.nasa_only or r["class"].endswith("_nasa")]
    if not filtered:
        print("No observations found. Run search first.");return
    grouped=defaultdict(list)
    for r in filtered:grouped[(r["name"],r["band"])].append(r)
    print("TARGET | BAND | DR1 | QR3 | QR2 | SAVED | SPAN_days")
    output=[]
    for (name,band),items in sorted(grouped.items()):
        counts=Counter(r["release"] for r in items)
        saved=sum((ROOT/r["file"]).is_file() for r in items)
        time_span=round(max(float(r["mjd"]) for r in items)-min(float(r["mjd"]) for r in items),1)
        print(f"{name} | {band} | {counts['DR1']} | {counts['QR3']} | {counts['QR2']} | {saved}/{len(items)} | {time_span}")
        output.append({"name":name,"band":band,"DR1":counts["DR1"],"QR3":counts["QR3"],
                       "QR2":counts["QR2"],"downloaded":saved,"planned":len(items),"span_days":time_span})
    csv_write(CAT/"balance_report.csv",output,list(output[0].keys()))
    print("BALANCE REPORT:",CAT/"balance_report.csv")
    print("Equal counts do not guarantee same wavelength or exact same MJD across bands.")

def status(args):
    rows=csv_read(OBS); qa=csv_read(QA)
    print("Observations:",len(rows),"Targets:",len(get_targets()),"Saved FITS:",sum((ROOT/r["file"]).exists() for r in rows))
    print("Releases:",dict(Counter(r["release"] for r in rows)))
    print("Detectors:",dict(Counter(r["band"] for r in rows)))
    print("QC:",dict(Counter(r["file_status"] for r in qa)))
    print("Search status:",dict(Counter(r["status"] for r in csv_read(SEARCH_LOG))))


README_TEAM="""# SPHEREx Space Apps 2026 — Team FITS dataset

## Content
- `fits/`: original IRSA multi-extension FITS cutouts (IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE when available).
- `catalogs/metadata.csv`: one observation per row, relative FITS filename, MJD, RA/Dec, detector, release, warnings, IRSA source and cutout URLs.
- `catalogs/object_summary.csv`: counts for each target (including zero counts).
- `catalogs/band_summary.csv`: detector coverage; wavelength ranges are detector-wide, NOT calibrated source wavelengths.
- `catalogs/quality_report.csv`: inspection warnings; status `structurally_ok` is NOT a scientifically validated detection.
- `catalogs/sequences.csv`: possible same-detector time series; NOT registered/photometrically matched by this package.
- `previews/`: selected PNG examples; display brightness is independently scaled and must not be used to measure flux change.

## Limits and provenance
Images come from NASA/IPAC IRSA. Every file's release, time, source URL and detector are in `metadata.csv`. Older and newer calibrations are not naively combined for precision photometry. Same detector does not guarantee identical wavelength of a source (SPHEREx uses linear variable filters). For asteroid rows, `ra/dec` denote the fixed cutout center; `object_ra/object_dec` give the predicted object position at each `mjd`, derived from MOST; `pair_id` groups fixed-sky image pairs. The predicted positions are NOT detections. Images need registration and source identification to demonstrate measured motion. No automatic source identity, measured proper motion, flux variation, model accuracy, spectral extraction or motion detection is claimed.

For public time-lapse, check that frames share a fixed sky field, matching wavelengths, valid WCS, and adequate time separation; then register/reproject to a common WCS and measure motion or photometry with appropriate uncertainty. Five NASA challenge targets require separate confirmation of observation availability.

## Official references
https://irsa.ipac.caltech.edu/Missions/spherex.html
https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts/
https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/

Acknowledgement: This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.
"""


def main():
    p=argparse.ArgumentParser(description="Audit, group, and export SPHEREx scientific dataset")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("sequences",help="Group same-detector observations (not registered)")
    sub.add_parser("export",help="Copy source FITS into a new TEAM_DATASET")
    sub.add_parser("status",help="Report current data counts")
    a=sub.add_parser("audit",help="Report detector/release balance")
    a.add_argument("--nasa-only",action="store_true")
    a=p.parse_args()
    {"sequences":sequences,"export":export,"status":status,"audit":audit}[a.command](a)

if __name__ == "__main__":
    main()
