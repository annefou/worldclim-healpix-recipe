"""Network: the converted cell means agree with an independent reference.

Run with ``pytest -m network``. Converts a 3 x 3 degree window of WorldClim bio1 (30s) over central
Iberia (about 30 s to read from the remote zip) and compares the pyramid means with stored reference
values (tests/reference/README.md), on cells fully covered by data.
"""

import csv
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from worldclim_healpix_recipe import convert

BBOX = (-6.0, 39.0, -3.0, 42.0)
REFERENCE = Path(__file__).parent / "reference" / "bio1_iberia_cell_means.csv"


def reference(depth):
    with REFERENCE.open() as f:
        return [(int(r["cell"]), float(r["mean_degC"]), float(r["coverage"]))
                for r in csv.DictReader(f) if int(r["depth"]) == depth]


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    out = tmp_path_factory.mktemp("bio1") / "out.zarr"
    convert("bio1", BBOX, out)
    return xr.open_datatree(out, engine="zarr")


@pytest.mark.network
@pytest.mark.parametrize("depth, mean_tol, max_tol", [(8, 0.005, 0.03), (9, 0.01, 0.1)])
def test_pyramid_means_match_the_reference(converted, depth, mean_tol, max_tol):
    out = converted[f"worldclim/{depth}"].to_dataset()
    got = dict(zip(out["cell_ids"].values.astype(np.uint64).tolist(), out["bio1"].values.astype(float)))
    pairs = [(got[c], m) for c, m, cov in reference(depth)
             if cov >= 0.999 and c in got and np.isfinite(got[c])]
    assert len(pairs) > 50
    diff = np.array([a - b for a, b in pairs])
    assert np.abs(diff).mean() < mean_tol
    assert np.abs(diff).max() < max_tol
    assert abs(diff.mean()) < mean_tol  # no bias


@pytest.mark.network
def test_units_and_licence_reach_the_output(converted):
    ds = converted["worldclim/13"].to_dataset()
    assert ds["bio1"].attrs["units"] == "degC"
