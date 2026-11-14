<img width="738" height="414" alt="images (5)" src="https://github.com/user-attachments/assets/dd425475-59b1-40c8-b8a3-e4c243ba054d" />


 # ASPAN EON — SPHEREx Data Collector

**NASA Space Apps Challenge 2026**  
**Component:** Scientific Data Collection  
**Contributor:** Arsan Tsoi  
**Data source:** NASA/IPAC Infrared Science Archive (IRSA)

## 1. About the Project

ASPAN EON is our team's project for exploring astronomical objects through infrared observations taken at different times.

To make this possible, we needed real observations that could be displayed, compared, and organized into time sequences.

My role was to collect and prepare these data. I used Python and NASA/IPAC's Infrared Science Archive (IRSA) to find SPHEREx observations, download FITS images, check their quality, and prepare the dataset for our web application.

The final collection includes **2,240 real SPHEREx FITS observations covering 95 astronomical targets**.

This repository contains the Python scripts, observation catalogs, metadata, and image previews. The full FITS collection is stored separately because of its size.

## 2. About NASA SPHEREx

SPHEREx (Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer) is a NASA space telescope launched on March 11, 2025.

The mission studies the history of the Universe, galaxy formation, and water and other molecules associated with planet formation.

SPHEREx observes infrared light from approximately 0.75 to 5.0 micrometers using six detectors (D1–D6) and 102 nominal spectral channels.

Because the telescope observes parts of the sky repeatedly, its archive can also be used to explore how astronomical objects change over time.

## 3. Where the Data Come From

All scientific observations in this project come from the official **NASA/IPAC Infrared Science Archive (IRSA)**.

The collection process uses three archive services:

- **IRSA TAP:** Searches for SPHEREx exposures covering the coordinates of selected stars.
- **MOST (Moving Object Search Tool):** Finds observations near the predicted positions of asteroids and other Solar System objects.
- **IRSA FITS cutout service:** Retrieves smaller scientific image regions from the original observations.

We used data from the DR1 and QR3 releases.

The FITS files contain real telescope observations. We did not generate synthetic astronomical images or artificial source detections.

Observation information and archive links are preserved in the metadata.

## 4. Dataset Overview

| Property | Result |
|---|---|
| Astronomical targets | 95 |
| FITS observations | 2,240 |
| Same-detector observation groups | 564 |
| Detectors | D1–D6 |
| Data releases | DR1 and QR3 |
| Missing files at export | 0 |
| PNG previews | 22 |

The collection includes 30 moving objects, 30 variable stars, 30 relatively stable stars, and five additional NASA challenge targets.

The five NASA targets are Barnard's Star, Epsilon Indi B, WISE 0855, RW Aur, and R Dra.

During structural validation, **1,169 FITS were marked `structurally_ok`**, while **1,071 received `review_needed` warnings**.

These warnings do not automatically mean that the files are corrupted or unusable. They indicate observations that may require further inspection.

## 5. How the Pipeline Works

The data collection process is divided into five main stages.

### 1. Finding observations

We start with `targets.csv`, which contains object names, categories, and coordinates.

`search.py` searches IRSA TAP for observations of stellar targets. For asteroids, `moving.py` uses MOST to find exposures near their predicted positions.

### 2. Selecting observations

From the search results, we select observations based on detector coverage, observation time (MJD), and available data releases.

For moving objects, the pipeline selects suitable observation pairs using a shared sky center. This makes it easier to compare the same region at different times.

### 3. Downloading FITS images

`download.py` retrieves scientific FITS cutouts from IRSA.

The downloader can be run again without replacing files that have already been downloaded successfully.

### 4. Checking the data

`processing.py` and `astronomy.py` inspect image dimensions, valid pixels, FITS extensions, quality flags, and WCS coordinates.

Files with warnings are recorded rather than automatically discarded.

### 5. Preparing the dataset

Finally, `delivery.py` generates observation groups, audit reports, metadata tables, and an export that the rest of our team can use.

## 6. Python Scripts

| Script | Purpose |
|---|---|
| `search.py` | Searches stellar observations through IRSA TAP |
| `moving.py` | Uses MOST for asteroid positions and observation pairs |
| `download.py` | Downloads scientific FITS cutouts |
| `processing.py` | Validates FITS files and supports WCS comparison |
| `delivery.py` | Generates reports, sequences, and dataset exports |
| `astronomy.py` | Handles astronomical calculations and FITS utilities |
| `common.py` | Provides shared paths, configuration, and utilities |

### Installation

Python 3.10 or newer is recommended.

```bash
python -m pip install -r requirements.txt
```

To check the available commands:

```bash
python search.py --help
python moving.py --help
python download.py --help
python processing.py --help
python delivery.py --help
```

Reproducing the complete dataset may also require the original observation catalog, search caches, and additional downloads from IRSA.

## 7. Files for the Web Application

The GitHub repository contains scripts and metadata, while the full FITS dataset is distributed separately.

**Full FITS dataset (Google Drive): https://drive.google.com/drive/folders/1cAlPAv3DCb9hW8obt2mlSSarVTVxKQYU?usp=drive_link

| File | Description |
|---|---|
| `dataset/catalogs/metadata.csv` | Main observation manifest for the application |
| `dataset/catalogs/object_summary.csv` | Observations available for each object |
| `dataset/catalogs/band_summary.csv` | Detector coverage |
| `dataset/catalogs/sequences.csv` | Groups of observations for comparison |
| `dataset/catalogs/quality_report.csv` | Validation results and warnings |
| `dataset/summary.json` | Dataset statistics |
| `data/catalogs/observations.csv` | Original selected observations |
| `data/catalogs/moving_pairs.csv` | Selected asteroid observation pairs |
| `previews/` | PNG images for demonstration |

### Important Metadata Fields

The observation metadata includes:

- `name`, `class` — object name and category.
- `mjd` — observation time in Modified Julian Date.
- `detector`, `release` — detector and data release.
- `file` — relative path to the FITS image.
- `ra`, `dec` — reference sky coordinates.
- `object_ra`, `object_dec` — predicted asteroid coordinates, where available.
- `pair_id` — identifies related asteroid observations.
- `status`, `warnings` — validation results.
- `source_url`, `cutout_url` — links to the original data sources.

The FITS paths refer to files in the full exported dataset, not to files stored directly on GitHub.

## 8. Using the Data on Our Website

The dataset is prepared for several features of the ASPAN EON application:

1. Browsing targets by category and detector.
2. Displaying scientific FITS images.
3. Selecting and comparing observations from different epochs.
4. Aligning images using WCS coordinates.
5. Visualizing predicted asteroid positions.
6. Exploring possible brightness changes.
7. Viewing metadata and quality warnings.

For reliable comparisons, the application should use WCS alignment and consistent visualization settings.

Images from the same detector may still differ in effective wavelength. Brightness changes therefore require further analysis before being treated as physical variability.

The PNG previews are intended for display, not scientific photometry.

## 9. Example: Observing Ceres

Ceres provides an example of how the dataset can be used to explore moving objects.

One selected pair of D1 observations is separated by approximately **3.21 hours**.

According to MOST predictions, Ceres should have moved by approximately **102 arcseconds** during this interval.

By aligning the FITS images using WCS, we can compare the same region of the sky at both observation times.

This demonstrates the approach used in our project. However, the predicted movement has not yet been independently confirmed through astrometric measurements of the source in both images.

## 10. Potential for Further Analysis

The dataset could also support future work in automatic object detection, motion analysis, and variability classification.

For example, machine learning might help identify interesting changes between observation epochs.

However, this would require additional processing and reliable labels. The repository does not contain a trained detection model or claim a measured ML accuracy.

## 11. Limitations and Data Quality

The collection contains all **2,240 selected FITS files**, but successful downloading and structural validation do not guarantee that every observation is suitable for scientific analysis.

Some images need further quality review, and predicted moving-object coordinates are not the same as confirmed detections.

For this reason, the exported summary records:

`scientific_motion_verified: false`

We keep these limitations explicit so that the website and presentation do not overstate what has been demonstrated.

## 12. References and Acknowledgements

- [NASA SPHEREx Mission](https://science.nasa.gov/mission/spherex/)
- [NASA/IPAC IRSA SPHEREx Archive](https://irsa.ipac.caltech.edu/Missions/spherex.html)
- [SPHEREx Archive Documentation](https://caltech-ipac.github.io/spherex-archive-documentation/)

This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, funded by the National Aeronautics and Space Administration.

---

**ASPAN EON — Scientific Data Collection Component**  
NASA Space Apps Challenge 2026
