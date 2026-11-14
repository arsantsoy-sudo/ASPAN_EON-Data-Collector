"""Four-epoch, fixed-sky D1 previews for the four remaining NASA targets.

Read-only: uses downloaded SPHEREx FITS, never modifies source files.
Run inside SPHEREx_SpaceApps_2026_KIT: python preview_other_nasa.py
"""
import csv
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.wcs import WCS
from reproject import reproject_interp

CATALOG = Path('data/catalogs/observations.csv')
OUTPUT = Path('data/previews/nasa_four_epochs')
TARGETS = ['Epsilon_Indi_B', 'WISE_0855', 'RW_Aur', 'R_Dra']


def read_image(file):
    with fits.open(file, memmap=False) as hdul:
        image = np.asarray(hdul['IMAGE'].data, dtype=float)
        wcs = WCS(hdul['IMAGE'].header).celestial
    if image.ndim != 2 or not wcs.has_celestial:
        raise ValueError(f'Invalid image or WCS: {file}')
    return image, wcs


def display_only(image):
    good = np.isfinite(image)
    if good.sum() < 20:
        return np.full(image.shape, np.nan)
    low, high = np.nanpercentile(image[good], [2, 99.5])
    scaled = np.clip((image - low) / max(high - low, 1e-12), 0, 1)
    return np.arcsinh(scaled / 0.08) / np.arcsinh(1 / 0.08)


def main():
    if not CATALOG.exists():
        raise SystemExit(f'Catalog not found: {CATALOG}. Run from the project folder.')
    with CATALOG.open(encoding='utf-8-sig', newline='') as f:
        observations = list(csv.DictReader(f))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for target in TARGETS:
        rows = sorted((r for r in observations
                       if r['name'] == target and r['band'] == 'D1'
                       and Path(r['file']).is_file()),
                      key=lambda r: float(r['mjd']))
        if len(rows) != 4:
            print(f'{target}: SKIP — D1 files available: {len(rows)}/4')
            continue

        try:
            reference, ref_wcs = read_image(rows[0]['file'])
            aligned = [reference]
            footprints = [np.isfinite(reference)]
            for row in rows[1:]:
                data, src_wcs = read_image(row['file'])
                resampled, footprint = reproject_interp(
                    (data, src_wcs), ref_wcs, shape_out=reference.shape)
                aligned.append(resampled)
                footprints.append((footprint > 0) & np.isfinite(resampled))

            common = np.logical_and.reduce(footprints)
            coverage = 100 * common.sum() / common.size
            if common.sum() < 100:
                print(f'{target}: LOW OVERLAP ({coverage:.1f}%), inspect WCS before use')

            fig, axes = plt.subplots(2, 2, figsize=(9, 9), sharex=True, sharey=True)
            for ax, row, data, footprint in zip(axes.flat, rows, aligned, footprints):
                ax.imshow(display_only(np.where(footprint, data, np.nan)),
                          origin='lower', cmap='magma', vmin=0, vmax=1,
                          interpolation='nearest')
                ax.set_title(f"MJD {float(row['mjd']):.3f}  |  {row['release']}  |  D1", fontsize=10)
                ax.set_xlim(-0.5, reference.shape[1] - 0.5)
                ax.set_ylim(-0.5, reference.shape[0] - 0.5)
                ax.set_xlabel('X (fixed reference pixels)')
                ax.set_ylabel('Y (fixed reference pixels)')
            fig.suptitle(f'{target.replace("_", " ")} — four epochs, fixed WCS\n'
                         f'Common coverage {coverage:.1f}% | source not identified', fontsize=12)
            fig.text(.5, .005,
                     'Display contrast set independently for each frame; NOT photometry or measured motion.',
                     ha='center', fontsize=8)
            fig.tight_layout(rect=(0, .025, 1, .94))
            destination = OUTPUT / f'{target}_D1_4epochs.png'
            fig.savefig(destination, dpi=150)
            plt.close(fig)
            print(f'{target}: SAVED {destination} | common sky coverage {coverage:.1f}%')
        except Exception as error:
            plt.close('all')
            print(f'{target}: ERROR {type(error).__name__}: {error}')

    print('Original FITS and observations.csv unchanged.')


if __name__ == '__main__':
    main()
