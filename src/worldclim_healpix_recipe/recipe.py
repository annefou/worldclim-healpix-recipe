"""The WorldClim recipe: what is specific to WorldClim 2.1. The rest comes from healpix-recipe-tools."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from healpix_recipe_tools import bioclim, gdal_path, raster_settings, read_window, run, stac_item, write_staged

#: The source, as cited. WorldClim 2.1, 1970-2000, EPSG:4326.
SOURCE = {
    "name": "WorldClim 2.1 bioclimatic variables",
    "version": "2.1",
    "reference_period": ["1970-01-01", "2000-12-31"],
    "citation": (
        "Fick, S.E. and R.J. Hijmans, 2017. WorldClim 2: new 1km spatial resolution climate "
        "surfaces for global land areas. International Journal of Climatology 37 (12): 4302-4315"
    ),
    "doi": "10.1002/joc.5086",
    # Not an open licence: the recipe (code) is Apache-2.0, the data are not.
    "license": "other",
    "license_text": (
        "The data are freely available for academic use and other non-commercial use. "
        "Redistribution or commercial use is not allowed without prior permission."
    ),
    "terms_url": "https://www.worldclim.org/about.html",
    "url_template": "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_{res}_bio.zip",
    "member_template": "wc2.1_{res}_bio_{n}.tif",
}

#: Resolutions WorldClim 2.1 publishes; 30s is about 1 km.
RESOLUTIONS = ("30s", "2.5m", "5m", "10m")

#: WorldClim's BIOCLIM convention (dismo::biovars): sample standard deviation, CV of precipitation + 1 mm.
SOURCE_CONVENTION = bioclim.SOURCES["WorldClim 2.1"]

GROUP = "worldclim/v21"

#: Variables with verified definitions. The GeoTIFFs hold float32 values in these units (no scale,
#: nodata -3.4e38). bio4 and bio15 follow dismo::biovars and differ from CHELSA's: checked against
#: WorldClim's own monthly layers (examples/verify_bio_definitions.py).
VARIABLES = {
    "bio1": {"units": "degC", "standard_name": "air_temperature",
             "long_name": "Mean annual air temperature (BIO1)"},
    "bio4": {"units": "0.01 degC",
             "long_name": "Temperature seasonality: 100 x sample standard deviation (n-1) of monthly "
                          "mean temperatures (BIO4)"},
    "bio12": {"units": "kg m-2", "standard_name": "precipitation_amount",
              "long_name": "Annual precipitation (BIO12), in mm, i.e. kg m-2"},
    "bio15": {"units": "percent",
              "long_name": "Precipitation seasonality: coefficient of variation of monthly precipitation "
                           "plus 1 mm, sample standard deviation (BIO15)"},
}

_LICENSE_LINK = {"rel": "license", "href": SOURCE["terms_url"], "type": "text/html",
                 "title": "WorldClim terms of use"}


def settings(variable: str, depth: int = 13, pyramid_to: int = 8, chunk_depth: int = 7,
             convention: str = "as-published") -> dict:
    """healpix-convert settings for one variable, as plain data (see healpix_recipe_tools.raster_settings)."""
    attrs = {**VARIABLES[variable], **bioclim.attrs(variable, convention, SOURCE_CONVENTION)}
    return raster_settings(GROUP, variable, attrs, depth=depth, pyramid_to=pyramid_to, chunk_depth=chunk_depth,
                           license=SOURCE["license"], license_links=[_LICENSE_LINK])


def _read(variable: str, bbox, pad_deg: float, res: str):
    """One GeoTIFF read inside WorldClim's remote zip: no download, but tens of seconds per window."""
    if res not in RESOLUTIONS:
        raise ValueError(f"res must be one of {RESOLUTIONS}")
    n = int(variable.removeprefix("bio"))
    path = gdal_path(SOURCE["url_template"].format(res=res), SOURCE["member_template"].format(res=res, n=n))
    return read_window(path, bbox, pad_deg)


def stage(variable: str, bbox: tuple[float, float, float, float], path: str | Path,
          pad_deg: float = 0.5, res: str = "30s", convention: str = "as-published") -> Path:
    """Write the staged input healpix-convert reads: a lat/lon Zarr dataset with a STAC item."""
    bioclim.check(variable, convention, SOURCE_CONVENTION)
    window = _read(variable, bbox, pad_deg, res)
    bio12 = (_read("bio12", bbox, pad_deg, res).values
             if bioclim.needs_bio12(variable, convention, SOURCE_CONVENTION) else None)
    window = dataclasses.replace(
        window, values=bioclim.apply(variable, window.values, convention, SOURCE_CONVENTION, bio12=bio12))
    item = stac_item(
        f"worldclim-v21-{res}-{variable}-{bioclim.target(convention, SOURCE_CONVENTION)}", window,
        tuple(SOURCE["reference_period"]), license=SOURCE["license"],
        links=[{"rel": "cite-as", "href": f"https://doi.org/{SOURCE['doi']}"},
               {"rel": "license", "href": SOURCE["terms_url"], "title": SOURCE["license_text"]}])
    return write_staged(path, GROUP, variable, window, item)


def convert(variable: str, bbox: tuple[float, float, float, float], output: str | Path,
            staged: str | Path | None = None, res: str = "30s", convention: str = "as-published",
            **settings_kwargs):
    """Stage, then convert with healpix-convert's public API. Returns the output DataTree."""
    output = Path(output)
    staged = Path(staged) if staged else output.with_name(output.stem + "-staged.zarr")
    stage(variable, bbox, staged, res=res, convention=convention)
    return run(staged, settings(variable, convention=convention, **settings_kwargs), output, bbox)
