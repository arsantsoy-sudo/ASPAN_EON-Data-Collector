"""SPHEREx Space Apps 2026 — moving.

Original science methods extracted from the working monolithic main.py;
raw FITS and catalog data are never included with this source distribution.
"""
from __future__ import annotations
import argparse
from common import *

from search import get_targets, cutout_url, safe_filename


def import_moving(args):
    """Use preexisting moving-object ephemeris records; do not invent positions."""
    path=Path(args.csv).resolve(); old=csv_read(path)
    targets={r["name"]:r for r in get_targets()}
    known=csv_read(OBS); oldkeys={(r["name"],r["image_url"],r["cutout_url"]) for r in known}
    count=0; cfg=settings()
    for r in old:
        name=r.get("name","")
        if name not in targets or targets[name]["class"] != "moving":continue
        ra=number(r.get("ra"));dec=number(r.get("dec"));mjd=number(r.get("date_mjd",r.get("mjd")))
        url=r.get("image_url","")
        if ra is None or dec is None or mjd is None or not url.startswith("https://") or not urlsplit(url).path.lower().endswith(".fits"):
            continue
        release=astro.release_from_url(url)
        if release not in ("QR2","QR3","DR1"):continue
        band=r.get("band","").replace("SPHEREx-","")
        if band not in astro.BAND_UM:band=astro.detector_from_filename(url)
        if band not in astro.BAND_UM:continue
        cut=cutout_url(url,ra,dec,float(cfg["cutout_deg"]))
        entry={"name":name,"class":"moving","ra":ra,"dec":dec,"mjd":mjd,"band":band,
               "release":release,"image_url":url,"cutout_url":cut,
               "file":str(Path("data/raw/moving")/name/safe_filename(url,float(cfg["cutout_deg"]),ra,dec)).replace("\\","/"),
               "source":"MOST/imported_ephemeris", "identity_verified":"no",
               "note":"target_center_follows_ephemeris;not_a_fixed_sky_animation"}
        key=(name,url,cut)
        if key not in oldkeys:known.append(entry);oldkeys.add(key);count+=1
    csv_write(OBS,known,OBS_COLUMNS)
    print("Imported moving target observations:",count,"from",path.name)

def _most_cell(row, key):
    """Read an Astroquery table cell without turning masked values into data."""
    try:
        value = row[key]
        if getattr(value, "mask", False) is True:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8").strip()
        return str(value).strip()
    except (KeyError, IndexError):
        return ""

def query_most(target: dict, start: str, end: str) -> list[dict]:
    """Return ALL dated, real DR1/QR3 SPHEREx exposures along an orbit.

    MOST calculates asteroid ephemerides; we never infer them from a static RA/Dec.
    No synthetic URLs, and no QR2->DR1 string replacement.
    """
    from astroquery.ipac.irsa.most import Most
    designation = str(target.get("most_id", "")).strip()
    # NASA/IPAC tutorial uses '20000004' (NAIF asteroid number) for Vesta.
    obj_name = str(20000000 + int(designation)) if designation.isdigit() else target.get("resolver_name", target["name"])
    response = Most.query_object(
        catalog="spherex", output_mode="Regular", obj_name=obj_name,
        obs_begin=start, obs_end=end, with_tarballs=False
    )
    table = response.get("results") if isinstance(response, dict) else None
    if table is None:
        raise RuntimeError("MOST did not return its expected results table")
    columns = set(table.colnames)
    required = {"ra_obj", "dec_obj", "mjd_obs", "image_url"}
    missing = required - columns
    if missing:
        raise RuntimeError("MOST unexpected columns: missing " + ",".join(sorted(missing)))
    observations = []
    for item in table:
        url = _most_cell(item,"image_url")
        if url.startswith("/"):
            url = "https://irsa.ipac.caltech.edu" + url
        elif not url.startswith("https://"):
            url = "https://irsa.ipac.caltech.edu/" + url.lstrip("/")
        parsed = urlsplit(url)
        if parsed.hostname != "irsa.ipac.caltech.edu" or not parsed.path.lower().endswith(".fits") or "/spherex/" not in parsed.path.lower():
            continue
        url = url.split("?",1)[0]
        release = astro.release_from_url(url)
        if release not in ("DR1", "QR3"):
            continue
        ra,dec,mjd = (number(_most_cell(item,k)) for k in ("ra_obj", "dec_obj", "mjd_obs"))
        if None in (ra,dec,mjd) or not (0<=ra<360 and -90<=dec<=90):
            continue
        band = astro.detector_from_filename(url)
        if band not in astro.BAND_UM:
            # Never label an unknown detector as a known band.
            continue
        observations.append({"image_url":url,"ra":ra,"dec":dec,"mjd":mjd,"band":band,"release":release})
    return list({r["image_url"]:r for r in observations}.values())

def search_moving(args):
    """Search just 30 asteroids; preserve every unrelated manifest row/FITS."""
    cfg=settings()
    targets=[t for t in get_targets() if t["class"] == "moving"]
    previous=csv_read(OBS)
    new_by_name={}
    reports=[]; calls=0
    cache_dir=CAT/"most_cache";cache_dir.mkdir(parents=True,exist_ok=True)
    for i,t in enumerate(targets,1):
        name=t["name"]
        cache_file=cache_dir/(name+"_"+args.obs_begin+"_"+args.obs_end+".json")
        try:
            if cache_file.is_file() and not args.refresh:
                records=json.loads(cache_file.read_text(encoding="utf-8"))
                mode="cache"
            else:
                if calls>=args.max_queries:
                    reports.append({"name":name,"status":"pending","found":0,"selected":0,"details":"not queried yet"})
                    continue
                print(f"MOST [{i}/{len(targets)}] {name}",flush=True)
                calls+=1
                records=query_most(t,args.obs_begin,args.obs_end)
                # Cache all parsed matches, not just selected six from V3.
                tmp=cache_file.with_suffix(".tmp")
                tmp.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
                tmp.replace(cache_file)
                mode="network"
            groups=defaultdict(list)
            for rec in records:
                if rec["release"] in ("DR1","QR3") and rec["band"] in astro.BAND_UM:
                    groups[rec["band"]].append(rec)
            entries=[]
            for band in astro.BAND_UM:
                selected=astro.balanced_epochs(groups[band],int(cfg["max_per_detector"]))
                for rec in selected:
                    ra,dec=rec["ra"],rec["dec"]
                    url=rec["image_url"]
                    # EPHEMERIS-CENTERED CUTOUTS: These follow the asteroid.
                    # Fixed-sky movies need a separate field selection/registration.
                    entries.append({"name":name,"class":"moving","ra":ra,"dec":dec,
                        "mjd":rec["mjd"],"band":band,"release":rec["release"],
                        "image_url":url,
                        "cutout_url":cutout_url(url,ra,dec,float(cfg["cutout_deg"])),
                        "file":str(Path("data/raw/moving")/name/safe_filename(url,float(cfg["cutout_deg"]),ra,dec)).replace("\\","/"),
                        "source":"MOST/fresh_ephemeris","identity_verified":"no",
                        "note":"ephemeris_centered;moving_source_not_verified;fixed_sky_blink_not_assured"})
            if entries:
                new_by_name[name]=entries
                status="selected"
            else:
                status="no_DR1_QR3_matches"
            reports.append({"name":name,"status":status,"found":len(records),"selected":len(entries),"details":mode})
        except Exception as exc:
            print(f"  MOST failed for {name}: {exc}",flush=True)
            reports.append({"name":name,"status":"error","found":0,"selected":0,"details":str(exc)[:160]})
    # Never discard old asteroid entries merely because a new query failed.
    replaced=set(new_by_name)
    updated=[r for r in previous if not (r["class"]=="moving" and r["name"] in replaced)]
    for name in replaced:
        updated+=new_by_name[name]
    unique={(r["name"],r["image_url"],r["cutout_url"]):r for r in updated}
    result=list(unique.values())
    if result!=previous:
        backup=CAT/("observations_before_most_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".csv")
        csv_write(backup,previous,OBS_COLUMNS)
        print("Observation backup:",backup)
        csv_write(OBS,result,OBS_COLUMNS)
    csv_write(CAT/"moving_search_status.csv",reports,["name","status","found","selected","details"])
    print("MOST SEARCH: requests",calls,"updated asteroids",len(replaced),"total rows",len(result))
    print("Status:",dict(Counter(x["status"] for x in reports)))
    print("No FITS downloaded; previous NASA/star observations preserved.")

def _moving_angle(a: dict, b: dict) -> float:
    """Small-field angular separation in degrees; handles RA crossing 0 degrees."""
    dec_mid = math.radians((float(a["dec"]) + float(b["dec"])) / 2)
    dra = (float(b["ra"]) - float(a["ra"]) + 180) % 360 - 180
    return math.hypot(dra * math.cos(dec_mid), float(b["dec"]) - float(a["dec"]))

def _shared_center(a: dict, b: dict) -> tuple[float, float]:
    """One fixed sky position for BOTH asteroid FITS in the same pair."""
    a_ra, b_ra = float(a["ra"]), float(b["ra"])
    dra = (b_ra - a_ra + 180) % 360 - 180
    return (a_ra + dra/2) % 360, (float(a["dec"]) + float(b["dec"])) / 2

def select_moving_pairs(args):
    """Re-select cached MOST observations into fixed-sky pairs WITHOUT any network requests.

    Each pair contains two different real exposures of the same detector, with
    a single identical cutout center. A 0.14 deg cutout is expected to include
    both ephemeris positions; detector footprint must still be tested on FITS.
    """
    cfg=settings(); size=float(cfg["cutout_deg"])
    limit=int(cfg.get("max_per_detector",4))
    cache_dir=CAT/"most_cache"
    previous=csv_read(OBS)
    if not previous:raise RuntimeError("Missing observations.csv; refusing to change anything")
    targets=[t for t in get_targets() if t["class"]=="moving"]
    if not cache_dir.exists():raise RuntimeError("Missing MOST cache; refusing to change observations")
    replacements={};report=[];pair_report=[]
    for target in targets:
        name=target["name"]
        if args.target and name!=args.target:continue
        cache_files=sorted(cache_dir.glob(name+"_*.json"))
        if not cache_files:
            report.append((name,"NO CACHE",0,0));continue
        records=json.loads(cache_files[-1].read_text(encoding="utf-8"))
        groups=defaultdict(list)
        for rec in records:
            if rec.get("band") not in astro.BAND_UM or rec.get("release") not in ("DR1","QR3"):continue
            if any(number(rec.get(k)) is None for k in ("mjd","ra","dec")):continue
            if not str(rec.get("image_url","")).startswith("https://irsa.ipac.caltech.edu/"):continue
            groups[rec["band"]].append(rec)
        selected=[];num_pairs=0
        for band in astro.BAND_UM:
            g=sorted(groups[band],key=lambda r:float(r["mjd"]))
            pair_candidates=[]
            for i,a in enumerate(g):
                for b in g[i+1:]:
                    dt=float(b["mjd"])-float(a["mjd"])
                    if dt>2.0:break
                    if dt<0.005 or a["image_url"]==b["image_url"]:continue
                    separation=_moving_angle(a,b)
                    # Nonzero predicted movement with plausible overlap in 0.14 deg field.
                    if not 0.004 <= separation <= min(0.060,size*0.43):continue
                    # Prefer visible movement (roughly 0.025 deg), and avoid
                    # extremely short or long time gaps when alternatives exist.
                    score=abs(separation-0.025)+0.002*abs(dt-0.15)
                    pair_candidates.append((score,dt,separation,a,b))
            pair_candidates.sort(key=lambda t:(t[0],t[1]))
            used_urls=set();pidx=0
            for score,dt,sep,a,b in pair_candidates:
                if a["image_url"] in used_urls or b["image_url"] in used_urls:continue
                pidx+=1;num_pairs+=1
                center_ra,center_dec=_shared_center(a,b)
                pair_id=f"{name}_{band}_pair{pidx}"
                for rec in (a,b):
                    url=rec["image_url"]
                    filename=safe_filename(url,size,center_ra,center_dec)
                    selected.append({"name":name,"class":"moving",
                        "ra":f"{center_ra:.9f}","dec":f"{center_dec:.9f}",
                        "object_ra":str(rec["ra"]), "object_dec":str(rec["dec"]),
                        "pair_id":pair_id,
                        "mjd":rec["mjd"],"band":band,"release":rec["release"],
                        "image_url":url,"cutout_url":cutout_url(url,center_ra,center_dec,size),
                        "file":str(Path("data/raw/moving")/name/filename).replace("\\","/"),
                        "source":"MOST/cached_ephemeris;fixed_sky_pair",
                        "identity_verified":"no",
                        "note":f"{pair_id};fixed_center;predicted_sep_deg={sep:.5f};source_not_measured"})
                pair_report.append({"name":name,"band":band,"pair_id":pair_id,
                    "mjd_a":a["mjd"],"mjd_b":b["mjd"],"hours":round(dt*24,3),
                    "predicted_separation_deg":round(sep,6),"center_ra":round(center_ra,9),
                    "center_dec":round(center_dec,9),"release_a":a["release"],"release_b":b["release"]})
                used_urls.add(a["image_url"]);used_urls.add(b["image_url"])
                if pidx*2>=limit:break
        if selected:
            replacements[name]=selected
        report.append((name,"selected" if selected else "NO PAIRS",len(records),len(selected)))
    if not replacements:
        print("No cache pairs found; observations unchanged")
        for r in report:print(*r)
        return
    result=[r for r in previous if not (r.get("class")=="moving" and r.get("name") in replacements)]
    for t in targets:
        if t["name"] in replacements:result.extend(replacements[t["name"]])
    backup=CAT/("observations_before_fixed_pairs_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".csv")
    csv_write(backup,previous,OBS_COLUMNS)
    csv_write(OBS,result,OBS_COLUMNS)
    pair_columns=["name","band","pair_id","mjd_a","mjd_b","hours","predicted_separation_deg",
                  "center_ra","center_dec","release_a","release_b"]
    csv_write(CAT/"moving_pairs.csv",pair_report,pair_columns)
    print("Backup:",backup)
    print("FIXED SKY PAIRS:",len(replacements),"asteroids,",len(pair_report),"pairs,",sum(len(x) for x in replacements.values()),"FITS candidates")
    print("Catalog total:",len(result),"; no FITS downloaded or deleted")
    print("Report: data/catalogs/moving_pairs.csv")
    for name,status,found,n in report:
        print(f"{name}: {status}, {n} observations from {found} raw matches")
    print("NOTE: predicted overlap is not verified until real FITS WCS/IMAGE is inspected")


def main():
    p=argparse.ArgumentParser(description="MOST asteroid search, import, and fixed-sky pair selection")
    sub=p.add_subparsers(dest="command", required=True)
    im=sub.add_parser("import-moving", help="Import dated MOST ephemeris records")
    im.add_argument("--csv", required=True)
    mo=sub.add_parser("search-moving", help="Query MOST for 30 asteroids")
    mo.add_argument("--max-queries",type=int,default=3)
    mo.add_argument("--obs-begin",default="2025-05-01")
    mo.add_argument("--obs-end",default="2026-11-13")
    mo.add_argument("--refresh",action="store_true")
    sm=sub.add_parser("select-moving-pairs", help="Select pairs from cached MOST observations; no network")
    sm.add_argument("--target",default="")
    a=p.parse_args()
    {"import-moving":import_moving, "search-moving":search_moving,
     "select-moving-pairs":select_moving_pairs}[a.command](a)

if __name__ == "__main__":
    main()
