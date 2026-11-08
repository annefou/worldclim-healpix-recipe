# Reference cell means

`bio1_iberia_cell_means.csv`: WorldClim 2.1 `bio1` at 30 arc-seconds (degC) averaged into HEALPix
cells (WGS84, NESTED) at depths 8 and 9, for the window 6-3W, 39-42N read with a 0.5 degree margin.
Columns: `depth`, `cell`, `mean_degC`, `coverage` (valid pixel area / cell area).

These values come from an independent implementation, not from this recipe: the area-weighted
binning of pixel centres in [healpix-connector](https://github.com/annefou/healpix-connector)
(`healpix_connector.binning.bin_to_cells`, commit `5a7e671`), applied to the same pixels read from
WorldClim's zip, written once on 2026-11-08. They are stored here so that this repository does not
depend on healpix-connector.
