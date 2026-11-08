# worldclim-healpix-recipe

[WorldClim 2.1](https://www.worldclim.org/data/worldclim21.html) bioclimatic variables (1970-2000)
on HEALPix (WGS84 ellipsoid, NESTED cell ids), converted with
[healpix-convert](https://github.com/GRID4EARTH/healpix-convert) as a third-party recipe.

> **Status: trial**, the second recipe after
> [chelsa-healpix-recipe](https://github.com/annefou/chelsa-healpix-recipe). The layout is being
> discussed in [healpix-convert#18](https://github.com/GRID4EARTH/healpix-convert/issues/18).

> **Data licence.** This repository is code (Apache-2.0). WorldClim's data are not open: *"The data
> are freely available for academic use and other non-commercial use. Redistribution or commercial
> use is not allowed without prior permission"* ([terms](https://www.worldclim.org/about.html)).
> Running the recipe for your own academic work is fine; publishing or sharing the converted layers
> needs WorldClim's permission. The licence is written into the STAC metadata of every output.

## What a recipe is here

Nothing is added to healpix-convert. The shared code (reading, staging, settings, BIOCLIM
conventions) comes from [healpix-recipe-tools](https://github.com/annefou/healpix-recipe-tools);
this repository holds only what is specific to WorldClim, following the
[recipe contract](https://github.com/annefou/healpix-recipe-template/blob/main/CONTRACT.md). A recipe is:

1. **a staging step**: one GeoTIFF is read *inside* WorldClim's remote zip (GDAL `/vsizip/` over
   `/vsicurl/`, no download of the 10 GB archive; a 4 x 4 degree window takes about 25-35 s) and
   written as a lat/lon Zarr dataset with a STAC item;
2. **a settings dict**: bilinear resampling to depth 13 (about 800 m), then a pyramid of `mean`
   down to depth 8;
3. **definitions**: units and long names set explicitly with `override_attrs`.

```python
from worldclim_healpix_recipe import convert

dt = convert("bio1", bbox=(-6.0, 39.0, -3.0, 42.0), output="bio1-iberia.zarr")   # res="30s" by default
dt["worldclim/8"]      # depth 8 (about 25 km) cell means
```

## Variables, and how they differ from CHELSA's

WorldClim stores float32 values in physical units, with a declared nodata value (-3.4e38).
Its variables follow R's `dismo::biovars`, which is **not** what CHELSA does for `bio4` and `bio15`.
Recomputed from WorldClim's own monthly layers over Iberia (`examples/verify_bio_definitions.py`):

| Variable | Unit | WorldClim definition | Ratio | CHELSA v2.1 |
|---|---|---|---|---|
| `bio1` | degC | mean of monthly means | 1.000 | same |
| `bio4` | 0.01 degC | 100 x **sample** standard deviation (n-1) of monthly means | 99.9999 | 100 x **population** SD: WorldClim's is about 4.4 % larger (sqrt(12/11)) |
| `bio12` | kg m-2 (mm) | sum of monthly precipitation | 1.0 | same |
| `bio15` | percent | coefficient of variation of **(monthly precipitation + 1 mm)**, sample SD | 1.0000000 | CV of monthly precipitation, population SD |

The same variable name therefore means different quantities in the two sources. Do not mix them
without converting.

Why: WorldClim's variables follow R's `dismo::biovars`
([source](https://github.com/cran/dismo/blob/master/R/biovars.R)): `p[,4] <- 100 * apply(tavg, 1, sd)`,
where R's `sd()` divides by n-1, and `p[,15] <- apply(prec+1, 1, cv)`, commented *"the "1 +" is to
avoid strange CVs for areas where mean rainfaill is < 1"*. CHELSA computes its own way.

Per-pixel ratios (1st percentile / median / 99th percentile), measured 2026-11-08:

| Ratio | WorldClim, 10', Iberia (2,731 px) | CHELSA, 30", 39N 6W (14,400 px) |
|---|---|---|
| bio4 / (100 x sample SD) | 0.9997 / 1.0000 / 1.0004 | 0.9574 / 0.9574 / 0.9575 |
| bio4 / (100 x population SD) | 1.0441 / 1.0445 / 1.0449 | 0.9999 / 1.0000 / 1.0001 |
| bio15 / CV(prec + 1, sample SD) | 1.0000 / 1.0000 / 1.0000 | 0.9697 / 0.9744 / 0.9795 |
| bio15 / CV(prec, population SD) | 1.0042 / 1.0235 / 1.0368 | 0.9991 / 1.0000 / 1.0009 |

WorldClim was checked at 10 arc-minutes, whose monthly layers are small enough to download; the 30
arc-second files come from the same software but were not checked directly.

## Conventions: comparing with CHELSA

CHELSA and WorldClim give the same BIOCLIM names to differently computed values: CHELSA uses the
population standard deviation (n) and the CV of monthly precipitation; WorldClim follows R's
`dismo::biovars`, with the sample standard deviation (n-1) and the CV of monthly precipitation
plus 1 mm. `bio4` differs by sqrt(12/11), about 4.4 %, everywhere.

`convention=` converts exactly, so values from the two sources can be compared:

```python
convert("bio4",  bbox, "bio4.zarr",  convention="population")    # as CHELSA computes it
convert("bio15", bbox, "bio15.zarr", convention="population")    # also reads bio12 (see below)
```

| `convention` | Meaning |
|---|---|
| `"as-published"` (default) | the source's own values (dismo convention) |
| `"population"` | population SD, CV of monthly precipitation (CHELSA's) |
| `"dismo"` | sample SD, CV of monthly precipitation + 1 mm (WorldClim's) |

- `bio4`: rescaled by sqrt(11/12) or sqrt(12/11), exact (both use the same 12 monthly values).
- `bio15`: adding 1 mm to every month leaves the standard deviation unchanged and raises the mean
  m = bio12 / 12 by 1, so the conversion uses `bio12` of the same source:
  CV_population = CV_dismo x (m + 1) / m x sqrt(11/12), and its inverse. Where it never rains
  (m = 0) the population CV is missing and the dismo CV is 0. Checked against the CV recomputed
  from the monthly layers: ratio 1.00000 (WorldClim to population) and 1.0000 +- 0.0009 (CHELSA to
  dismo, whose values are stored to 0.1).
- `bio1`, `bio12`: defined alike, unchanged.

The output states its convention (`bioclim_convention`) and, when converted, how (`comment`).

## Coasts: land masks

WorldClim marks the sea as nodata, unlike CHELSA, which has values over the sea. The recipe applies
the same land mask as the CHELSA recipe, a mask **you choose** (`land_mask=`, see
[healpix-recipe-tools](https://github.com/annefou/healpix-recipe-tools#coasts-and-land-masks)):
Natural Earth 10 m land by default, any polygon file or URL, or `None` for WorldClim's own mask. With
the same mask, coastal cells of the two sources describe the same land.

## Agreement with an independent reference

The network tests convert `bio1` over central Iberia (6-3W, 39-42N) and compare the pyramid means
with stored reference values computed independently (an area-weighted binning of the same pixels,
see [tests/reference](tests/reference/README.md)), on cells fully covered by data.
Measured 2026-11-08 (healpix-convert `dfa4ed3`):

| Depth | Cells | Mean difference | Mean abs. difference | Max abs. difference |
|---|---|---|---|---|
| 8 (~25 km) | 70 | -0.0001 degC | 0.0012 degC | 0.006 degC |
| 9 (~12 km) | 377 | -0.0002 degC | 0.0030 degC | 0.039 degC |

Staging and conversion of the window took about 40 s, most of it reading the zip.

## Open points

- **Coverage is not reported**: the pyramid's `mean` ignores missing children (coasts, window
  edges), as for CHELSA.
- **Reading is slow** for on-the-fly use (tens of seconds per window, more for southern windows,
  since the zip member is decompressed from its start). For bulk work, download the zip once.

## Running

```bash
pixi run -e test test            # offline: settings, definitions, licence
pixi run -e test test-network    # reads WorldClim and compares with the stored reference
python examples/verify_bio_definitions.py    # rechecks bio4 / bio15 definitions (~95 MB download)
```

## Licence and citation

Code: Apache License 2.0. Data: WorldClim terms of use (above). Cite Fick, S.E. and R.J. Hijmans,
2017. WorldClim 2: new 1km spatial resolution climate surfaces for global land areas. International
Journal of Climatology 37 (12): 4302-4315, [doi:10.1002/joc.5086](https://doi.org/10.1002/joc.5086).
