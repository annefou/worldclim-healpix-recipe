"""Check WorldClim's bio4 and bio15 definitions against its own monthly layers.

    python examples/verify_bio_definitions.py [download directory]

Downloads the 10 arc-minute bio, tavg and prec zips (about 95 MB) and compares, over Iberia,
the published bio variables with values recomputed from the monthly layers. Measured 2026-11-08:

    bio4  / sd(tavg, ddof=1)                 = 99.9999   (sample standard deviation)
    bio4  / sd(tavg, ddof=0)                 = 104.45    (population: what CHELSA uses)
    bio15 / CV(prec + 1, ddof=1)             = 1.0000000 (dismo::biovars convention)
    bio15 / CV(prec, ddof=0)                 = 1.023     (what CHELSA uses)
    bio12 / sum(prec) = 1.0, bio1 / mean(tavg) = 1.000002
"""

import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

BASE = "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/"
BBOX = (-10.0, 36.0, 4.0, 44.0)


def main(folder: Path) -> None:
    for v in ("bio", "tavg", "prec"):
        target = folder / f"wc2.1_10m_{v}.zip"
        if not target.exists():
            urllib.request.urlretrieve(f"{BASE}wc2.1_10m_{v}.zip", target)

    def read(v, member):
        with rasterio.open(f"/vsizip/{folder / f'wc2.1_10m_{v}.zip'}/{member}") as s:
            a = s.read(1, window=from_bounds(*BBOX, s.transform).round_offsets().round_lengths()).astype(float)
            a[a == s.nodata] = np.nan
            return a

    tavg = np.stack([read("tavg", f"wc2.1_10m_tavg_{m:02d}.tif") for m in range(1, 13)])
    prec = np.stack([read("prec", f"wc2.1_10m_prec_{m:02d}.tif") for m in range(1, 13)])
    bio = {n: read("bio", f"wc2.1_10m_bio_{n}.tif") for n in (1, 4, 12, 15)}
    ok = np.isfinite(bio[4]) & np.isfinite(tavg).all(0) & np.isfinite(prec).all(0) & (prec.sum(0) > 0)

    def ratio(a, b):
        return float(np.median(a[ok] / b[ok]))

    print(f"{int(ok.sum())} land pixels")
    print("bio1  / mean(tavg)          ", ratio(bio[1], tavg.mean(0)))
    print("bio4  / sd(tavg, ddof=1)    ", ratio(bio[4], tavg.std(0, ddof=1)))
    print("bio4  / sd(tavg, ddof=0)    ", ratio(bio[4], tavg.std(0, ddof=0)))
    print("bio12 / sum(prec)           ", ratio(bio[12], prec.sum(0)))
    print("bio15 / CV(prec + 1, ddof=1)", ratio(bio[15], 100 * (prec + 1).std(0, ddof=1) / (prec + 1).mean(0)))
    print("bio15 / CV(prec, ddof=0)    ", ratio(bio[15], 100 * prec.std(0, ddof=0) / prec.mean(0)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory() as tmp:
            main(Path(tmp))
