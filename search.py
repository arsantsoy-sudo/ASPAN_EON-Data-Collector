"""SPHEREx Space Apps 2026 — search.

Original science methods extracted from the working monolithic main.py;
raw FITS and catalog data are never included with this source distribution.
"""
from __future__ import annotations
import argparse
from common import *


def get_targets(resolve=False) -> list[dict]:
    """Preserve existing target list; resolve only missing NASA names with Sesame."""
    existing=csv_read(TARGETS)
    if not existing: raise RuntimeError("targets.csv is empty or missing")
    rows=[]; names=set()
    for r in existing:
        name=r.get("name","").strip()
        if not name or canonical(name) in names: continue
        names.add(canonical(name))
        rows.append({"name":name,"class":r.get("class",""),"ra":r.get("ra",""),"dec":r.get("dec",""),
                     "resolver_name":r.get("resolver_name",name),"most_id":r.get("most_id", ""),
                     "position_epoch":"", "pmra_mas_yr":"", "pmdec_mas_yr":""})
    for name,query,cls,ra,dec in NASA:
        if canonical(name) in names: continue
        names.add(canonical(name))
        rows.append({"name":name,"class":cls,"ra":ra if ra is not None else "",
                     "dec":dec if dec is not None else "", "resolver_name":query,"most_id":"",
                     "position_epoch":"", "pmra_mas_yr":"", "pmdec_mas_yr":""})
    coord_path = CAT / "target_coordinates.csv"
    overrides = {r.get("name"): r for r in csv_read(coord_path)}
    for t in rows:
        if t["name"] in overrides:
            old=overrides[t["name"]]
            for field in ("ra","dec","position_epoch","pmra_mas_yr","pmdec_mas_yr"):
                if old.get(field) not in (None, ""):t[field]=old[field]
    if resolve:
        from astropy.coordinates import SkyCoord
        for t in rows:
            if t["class"].endswith("_nasa") and (number(t["ra"]) is None or number(t["dec"]) is None):
                print("Resolving NASA target:",t["resolver_name"])
                try:
                    point=SkyCoord.from_name(t["resolver_name"])
                    t["ra"],t["dec"]=round(point.ra.deg,9),round(point.dec.deg,9)
                except Exception as e:
                    print("  unresolved:",str(e)[:140])
    cols=["name","class","ra","dec","position_epoch","pmra_mas_yr","pmdec_mas_yr"]
    csv_write(coord_path,rows,cols)
    csv_write(CAT/"targets_95.csv",rows,["name","class","ra","dec","resolver_name","most_id"]+cols[4:])
    return rows

def query_tap(ra:float,dec:float,maxrec:int) -> list[dict]:
    """Use official IRSA cutouts-notebook TAP table and ADQL query."""
    import pyvo
    adql=f"""SELECT a.uri, p.time_bounds_lower, p.energy_bandpassname
    FROM spherex.artifact a JOIN spherex.plane p ON a.planeid=p.planeid
    WHERE 1=CONTAINS(POINT('ICRS',{ra:.10f},{dec:.10f}),p.poly)
    ORDER BY p.time_bounds_lower"""
    result=pyvo.dal.TAPService("https://irsa.ipac.caltech.edu/TAP").search(adql,maxrec=maxrec)
    output=[]
    for r in result:
        def string(x):
            if x is None: return ""
            return x.decode("utf-8") if isinstance(x,bytes) else str(x)
        uri=string(r["uri"])
        if uri.startswith("/"): url="https://irsa.ipac.caltech.edu"+uri
        elif uri.startswith("https://"): url=uri
        else: url="https://irsa.ipac.caltech.edu/"+uri
        if not urlsplit(url).path.lower().endswith(".fits"): continue
        output.append({"image_url":url,"mjd":string(r["time_bounds_lower"]),
                       "band":string(r["energy_bandpassname"])})
    return output

def cutout_url(url:str,ra:float,dec:float,size:float)->str:
    """Official cutout service uses ?center=RA,DEC&size=degrees."""
    return url.split("?",1)[0]+f"?center={ra:.9f},{dec:.9f}d&size={size:.6f}"

def safe_filename(url: str, size: float, ra:float, dec:float) -> str:
    base=Path(urlsplit(url).path).name
    stem=base[:-5] if base.endswith(".fits") else base
    digest=hashlib.sha256(f"{url}|{ra:.9f}|{dec:.9f}|{size}".encode()).hexdigest()[:12]
    return stem+"_"+digest+".fits"

def search_one(target:dict,maxrec:int) -> list[dict]:
    ra,dec=number(target["ra"]),number(target["dec"])
    if ra is None or dec is None: raise ValueError("missing RA/Dec; resolve target first")
    return query_tap(ra,dec,maxrec)

def search(args):
    """Select balanced DR1/QR3 epochs, keep the 95-target catalog intact.

    NASA-only refresh updates only those five targets. Existing files aren't touched.
    """
    cfg=settings()
    targets=get_targets(resolve=args.resolve_nasa)
    if args.nasa_only:
        targets=[t for t in targets if t["class"].endswith("_nasa")]
    elif args.stars_only:
        targets=[t for t in targets if t["class"] in ("stable", "variable")]
    cache=CAT/"search_cache";cache.mkdir(parents=True,exist_ok=True)
    log=[];selected=[];calls=0
    previous=csv_read(OBS)
    for ix,target in enumerate(targets,1):
        name=target["name"]
        if target["class"] == "moving":
            log.append({"name":name,"status":"requires_ephemeris","results":0,"note":"Use MOST dated observations"})
            continue
        if number(target["ra"]) is None or number(target["dec"]) is None:
            log.append({"name":name,"status":"missing_coordinates","results":0,"note":"Resolve target first"})
            continue
        # The old cache used static J2000 coords for Barnard; never reuse it.
        cachefile=cache/(name+("_pm_v2" if name=="Barnards_Star" else "")+".json")
        if cachefile.exists() and not args.refresh:
            try:records=json.loads(cachefile.read_text(encoding="utf-8"))
            except Exception:records=[]
        else:
            # Two distinct positions for Barnard, since it moved substantially since J2000.
            anchor_dates=[60914.2,61285.2] if name=="Barnards_Star" else [None]
            if calls+len(anchor_dates)>args.max_queries:
                log.append({"name":name,"status":"pending","results":0,"note":"Increase --max-queries"})
                continue
            records=[]
            try:
                for anchor in anchor_dates:
                    if anchor is None:ra,dec=float(target["ra"]),float(target["dec"])
                    else:ra,dec,_=astro.position_at_mjd(target,anchor)
                    print(f"IRSA [{ix}/{len(targets)}] {name} @ {ra:.5f}, {dec:.5f}",flush=True)
                    records+=query_tap(ra,dec,int(cfg["max_search_rows_per_target"]))
                    calls+=1
                records=list({r["image_url"]:r for r in records}.values())
                cachefile.write_text(json.dumps(records,indent=2),encoding="utf-8")
            except Exception as exc:
                calls+=1
                log.append({"name":name,"status":"search_error","results":0,"note":str(exc)[:180]})
                continue
        log.append({"name":name,"status":"searched","results":len(records),"note":"DR1/QR3 balanced by detector"})
        groups=defaultdict(list)
        for r in records:
            rel=astro.release_from_url(r["image_url"])
            if rel not in cfg["preferred_releases"]:continue
            mjd=number(r["mjd"])
            if mjd is None:continue
            band=r["band"].replace("SPHEREx-","")
            if band not in astro.BAND_UM:continue
            groups[band].append({**r,"mjd":mjd,"band":band,"release":rel})
        chosen=[]
        for band in astro.BAND_UM:
            options=groups[band]
            if any(r["release"]=="DR1" for r in options):
                options=[r for r in options if r["release"]!="QR2"]
            elif not cfg.get("allow_qr2_fallback",False):
                options=[r for r in options if r["release"]!="QR2"]
            chosen+=astro.balanced_epochs(options,int(cfg["max_per_detector"]))
        # All detector cutouts use ONE fixed sky center per target: vital for blinking.
        if name=="Barnards_Star" and chosen:
            positions=[astro.position_at_mjd(target,r["mjd"]) for r in chosen]
            center_ra=(min(p[0] for p in positions)+max(p[0] for p in positions))/2
            center_dec=(min(p[1] for p in positions)+max(p[1] for p in positions))/2
        else:
            center_ra,center_dec=float(target["ra"]),float(target["dec"])
        for rec in chosen:
            if name=="Barnards_Star":
                ra,dec,method=astro.position_at_mjd(target,rec["mjd"])
            else:
                ra,dec,method=float(target["ra"]),float(target["dec"]),"catalog_position_unpropagated"
            url=rec["image_url"]
            selected.append({"name":name,"class":target["class"],"ra":ra,"dec":dec,
                "mjd":rec["mjd"],"band":rec["band"],"release":rec["release"],
                "image_url":url,"cutout_url":cutout_url(url,center_ra,center_dec,float(cfg["cutout_deg"])),
                "file":str(Path("data/raw")/target["class"]/name/
                           safe_filename(url,float(cfg["cutout_deg"]),center_ra,center_dec)).replace("\\","/"),
                "source":"IRSA TAP (point search)","identity_verified":"no",
                "note":method+";fixed_sky_center;source_detection_not_verified"})
    if args.nasa_only:
        selected=[r for r in previous if not r["class"].endswith("_nasa")]+selected
    elif args.stars_only:
        # Preserve *every* NASA and moving-object row. Existing FITS stay untouched.
        selected=[r for r in previous if r["class"] not in ("stable", "variable")]+selected
        # On temporary network/resolver problems, keep older stellar catalog entries.
        updated={r["name"] for r in selected if r["class"] in ("stable", "variable")}
        selected += [r for r in previous if r["class"] in ("stable", "variable") and r["name"] not in updated]
    else:
        # Old imported MOST rows are independent of point-based stellar searches.
        selected += [r for r in previous if r.get("source","").startswith("MOST/imported")]
    unique={(r["name"],r["image_url"],r["cutout_url"]):r for r in selected}
    # Save previous manifest when contents change, without deleting original FITS.
    if previous and list(unique.values())!=previous:
        backup=CAT/("observations_before_reselection_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".csv")
        csv_write(backup,previous,OBS_COLUMNS)
        print("Previous observation list backed up:",backup)
    csv_write(OBS,list(unique.values()),OBS_COLUMNS)
    csv_write(SEARCH_LOG,log,["name","status","results","note"])
    print("SEARCH:",len(unique),"candidate observations; TAP calls",calls)
    print("Use 'python main.py audit' to check balance before download.")


def main():
    p=argparse.ArgumentParser(description="Search SPHEREx stellar/NASA observations via IRSA TAP")
    p.add_argument("--max-queries", type=int, default=12)
    scope=p.add_mutually_exclusive_group()
    scope.add_argument("--nasa-only", action="store_true")
    scope.add_argument("--stars-only", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--resolve-nasa", action="store_true")
    search(p.parse_args())

if __name__ == "__main__":
    main()
