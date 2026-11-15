<img width="738" height="414" alt="ASPAN EON project image" src="https://github.com/user-attachments/assets/dd425475-59b1-40c8-b8a3-e4c243ba054d" />

# ASPAN EON: SPHEREx Data Collector

ASPAN EON is our team's, The K'Oirat's project for exploring infrared observations of astronomical objects over time, developed for NASA SPACE APPS CHALLENGE 2026. My role was to collect and prepare the data for our web application using Python and NASA/IPAC's Infrared Science Archive (IRSA)

The collection contains 2240 real SPHEREx FITS observations of 95 targets. This repository holds the scripts, catalogs, metadata, and previews

the full FITS dataset is stored separately because of its size. It's very large in size, gigabytes

## About SPHEREx

SPHEREx is a NASA space telescope launched on March 11, 2025. 
It studies the history of the Universe, galaxy formation, and molecules associated with planet formation

Its six detectors (D1–D6) cover infrared wavelengths of about 0.75 to 5.0 micrometers across 102 nominal spectral channels. Repeated observations also let us compare objects at different times

##  sources of data

All observations come from the official NASA/IPAC IRSA archive, using the DR1 and QR3 releases. The collection uses 3 services:

IRSA TAP searches for exposures covering selected stellar coordinates
MOST (Moving Object Search Tool) finds observations near predicted asteroid positions
IRSA FITS cutout service downloads small regions from the original images



## here's the dataset values:

| Property | Value |
|---|---|
| Targets | 95 |
| FITS observations | 2,240 |
| Same-detector observation groups | 564 |
| Detectors | D1–D6 |
| Releases | DR1 and QR3 |
| Missing files at export | 0 |
| PNG previews | 22 |

The targets include 30 moving objects, 30 variable stars, 30 relatively stable stars, and 5 NASA challenge targets: Barnard's Star, Epsilon Indi B, WISE 0855, RW Aur, and R Dra. Totalling 95

Structural checks marked 1169 files as `structurally_ok` and 1071 as `review_needed`. A warning means the observation needs inspection, not that it is automatically corrupted and thus unusable

## pipeline work

### 1. Find observations

`targets.csv` lists object names, categories, and coordinates
`search.py` queries IRSA TAP for stars, 
while `moving.py` uses MOST for observations near predicted asteroid positions

### 2. Select observations

The pipeline selects observations by detector coverage, time (MJD), and data release. 
For moving objects, it chooses observation pairs with a shared sky center so the same region can be compared at different times, so u can see the changes across time.

### 3. Download images

`download.py` retrieves FITS cutouts from IRSA. It can resume without replacing files already downloaded successfully

### 4. Check the files

`processing.py` and `astronomy.py` check image dimensions, valid pixels, FITS extensions, quality flags, and WCS coordinates. Files with warnings are recorded rather than automatically discarded

### 5. Export the dataset

`delivery.py` creates observation groups, metadata tables and an export for the rest of the team

## Scripts and setup

| Script | Purpose |
|---|---|
| `search.py` | Find stellar observations through IRSA TAP |
| `moving.py` | Find asteroid observations and pairs through MOST |
| `download.py` | Download FITS cutouts |
| `processing.py` | Validate FITS files and support WCS comparison |
| `delivery.py` | Build reports, sequences, and exports |
| `astronomy.py` | Handle astronomical calculations and FITS utilities |
| `common.py` | Store shared paths, settings, and utilities |

```bash
python -m pip install -r requirements.txt
```


## Files for the web application
Scripts and metadata are on GitHub. Download the full FITS collection from [Google Drive](https://drive.google.com/drive/folders/1cAlPAv3DCb9hW8obt2mlSSarVTVxKQYU?usp=drive_link)

| File | Contents |
|---|---|
| `dataset/catalogs/metadata.csv` | Main observation manifest |
| `dataset/catalogs/object_summary.csv` | Available observations per object |
| `dataset/catalogs/band_summary.csv` | Detector coverage |
| `dataset/catalogs/sequences.csv` | Observation groups for comparison |
| `dataset/catalogs/quality_report.csv` | Check results and warnings |
| `dataset/summary.json` | Dataset statistics |
| `data/catalogs/observations.csv` | Original selected observations |
| `data/catalogs/moving_pairs.csv` | Selected asteroid observation pairs |
| `previews/` | PNG previews |

### Metadata fields

| Fields | Meaning |
|---|---|
| `name`, `class` | Object name and category |
| `mjd` | Observation time in Modified Julian Date |
| `detector`, `release` | Detector and data release |
| `file` | Relative path to the FITS file |
| `ra`, `dec` | Reference sky coordinates |
| `object_ra`, `object_dec` | Predicted asteroid coordinates |
| `pair_id` | Related asteroid observations |
| `status`, `warnings` | Check results |
| `source_url`, `cutout_url` | Original data links |

FITS paths point to files in the exported dataset, not files stored on GitHub

## Using the data on the website

The dataset supports browsing by category and detector, displaying FITS images, comparing dates, aligning frames with WCS, showing predicted asteroid positions, and exploring possible brightness changes Comparisons need WCS alignment and consistent display settings. Even images from the same detector can have different effective wavelengths, so a brightness difference does not necessarily mean the object changed over time. PNG previews are for display

## Example: Ceres

One selected pair of D1 observations is about **3.21 hours** apart. MOST predicts that Ceres moved approximately **102 arcseconds** during that interval
WCS alignment lets us compare the same sky region in both images. This illustrates the workflow, but the predicted motion has not yet been independently confirmed by measuring the source position in both frames


## Limitations
All **2240 selected FITS files** are present, but a successful download does not guarantee a scientifically useful observation. Some files still need quality review, and predicted positions are not confirmed detections The exported summary therefore records `scientific_motion_verified: false`. This distinction matters when presenting the dataset or using it in the website

## References and acknowledgements

- [NASA SPHEREx Mission](https://science.nasa.gov/mission/spherex/)
- [NASA/IPAC IRSA SPHEREx Archive](https://irsa.ipac.caltech.edu/Missions/spherex.html)
- [SPHEREx Archive Documentation](https://caltech-ipac.github.io/spherex-archive-documentation/)

This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, funded by the National Aeronautics and Space Administration
