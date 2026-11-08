"""The WorldClim recipe: source description, variable definitions, staging and healpix-convert settings."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

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

_WGS84 = {"name": "wgs84"}


def _number(variable: str) -> int:
    return int(variable.removeprefix("bio"))


def settings(variable: str, depth: int = 13, pyramid_to: int = 8, chunk_depth: int = 7) -> dict:
    """healpix-convert settings for one variable, as plain data.

    WorldClim (about 1 km at 30s) is resampled bilinearly at ``depth`` (13 is about 800 m), then the
    pyramid builds the coarser depths down to ``pyramid_to`` with ``mean``: on equal-area cells,
    block means are area-weighted cell means.
    """
    meta = VARIABLES[variable]
    return {
        "metadata": {
            "stac": {
                "override_properties": {"license": SOURCE["license"]},
                "override_links": [{"rel": "license", "href": SOURCE["terms_url"], "type": "text/html",
                                    "title": "WorldClim terms of use"}],
            },
        },
        "multiscale_settings": {
            "groups": ["worldclim"],
            "pyramid_groups": {
                "worldclim": {"derived_levels": list(range(depth - 1, pyramid_to - 1, -1)), "reduce": "mean"},
            },
        },
        "group_settings": {
            "worldclim/v21": {
                "healpix": {"refinement_level": depth, "indexing_scheme": "nested", "ellipsoid": _WGS84},
                "chunk": {
                    "method": "healpix_cell_dense",
                    "healpix": {"refinement_level": chunk_depth, "indexing_scheme": "nested", "ellipsoid": _WGS84},
                    "chunk_buffer_width": 3000.0,  # metres: a few WorldClim pixels
                },
                "resampler": {"name": "bilinear"},
                "output_dtype": "float32",
                "metadata": {"override_attrs": {variable: dict(meta)}},
            },
        },
    }


def _read_window(variable: str, bbox: tuple[float, float, float, float], pad_deg: float, res: str):
    """WorldClim pixels in ``bbox`` + ``pad_deg``, nodata as NaN, rows south to north.

    The GeoTIFF is read inside the remote zip (GDAL /vsizip/ over /vsicurl/): no download of the
    10 GB archive, but a window takes tens of seconds, since the member is compressed.
    """
    import rasterio
    from rasterio.windows import from_bounds

    if res not in RESOLUTIONS:
        raise ValueError(f"res must be one of {RESOLUTIONS}")
    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".zip,.tif")
    path = ("/vsizip//vsicurl/" + SOURCE["url_template"].format(res=res) + "/"
            + SOURCE["member_template"].format(res=res, n=_number(variable)))
    w, s, e, n = bbox[0] - pad_deg, bbox[1] - pad_deg, bbox[2] + pad_deg, bbox[3] + pad_deg
    with rasterio.open(path) as src:
        win = from_bounds(w, s, e, n, src.transform).round_offsets().round_lengths()
        raw = src.read(1, window=win)
        scale, offset, nodata = src.scales[0], src.offsets[0], src.nodata
        t = src.window_transform(win)
    values = raw.astype("float64")
    if nodata is not None:
        values[raw == nodata] = np.nan
    values = values * scale + offset
    lon = t.c + t.a * (np.arange(values.shape[1]) + 0.5)
    lat = t.f + t.e * (np.arange(values.shape[0]) + 0.5)
    return values[::-1], lon, lat[::-1]  # ascending latitude


def stage(variable: str, bbox: tuple[float, float, float, float], path: str | Path,
          pad_deg: float = 0.5, res: str = "30s") -> Path:
    """Write the staged input healpix-convert reads: a lat/lon Zarr dataset with a STAC item."""
    import shapely
    import xarray as xr

    values, lon, lat = _read_window(variable, bbox, pad_deg, res)
    ds = xr.Dataset({variable: (("lat", "lon"), values.astype("float32"))}, coords={"lat": lat, "lon": lon})
    ds["lat"].attrs.update(standard_name="latitude", units="degrees_north")
    ds["lon"].attrs.update(standard_name="longitude", units="degrees_east")
    box = shapely.box(float(lon[0]), float(lat[0]), float(lon[-1]), float(lat[-1]))
    stac_item = {
        "type": "Feature",
        "stac_version": "1.1.0",
        # healpix-convert requires the field; the DEM GLO-30 notebook uses the projection extension
        "stac_extensions": ["https://stac-extensions.github.io/projection/v2.0.0/schema.json"],
        "id": f"worldclim-v21-{res}-{variable}",
        "geometry": shapely.geometry.mapping(box),
        "bbox": list(box.bounds),
        "properties": {
            "datetime": None,
            "start_datetime": "1970-01-01T00:00:00Z",
            "end_datetime": "2000-12-31T23:59:59Z",
            "proj:code": "EPSG:4326",
            "license": SOURCE["license"],
        },
        "links": [
            {"rel": "cite-as", "href": f"https://doi.org/{SOURCE['doi']}"},
            {"rel": "license", "href": SOURCE["terms_url"], "title": SOURCE["license_text"]},
        ],
        "assets": {},
    }
    path = Path(path)
    xr.DataTree.from_dict({"/": xr.Dataset(attrs={"stac_discovery": stac_item}), "worldclim/v21": ds}).to_zarr(
        path, mode="w-", zarr_format=3)
    return path


def convert(variable: str, bbox: tuple[float, float, float, float], output: str | Path,
            staged: str | Path | None = None, res: str = "30s", **settings_kwargs):
    """Stage, then convert with healpix-convert's public API. Returns the output DataTree."""
    import healpix_convert as hc
    import shapely

    output = Path(output)
    staged = Path(staged) if staged else output.with_name(output.stem + "-staged.zarr")
    stage(variable, bbox, staged, res=res)
    cfg = hc.ConvertSettings.model_validate(settings(variable, **settings_kwargs))
    return hc.create_healpix_dataset([str(staged)], cfg, str(output), output_extent=shapely.box(*bbox))
