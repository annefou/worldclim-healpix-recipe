"""WorldClim 2.1 bioclimatic variables on HEALPix (WGS84, NESTED), as a healpix-convert recipe.

A recipe is a staging step (WorldClim's GeoTIFFs read into a lat/lon Zarr dataset) plus a
healpix-convert settings dict, run with healpix-convert's public API. Nothing is added to
healpix-convert itself. The recipe is code (Apache-2.0); WorldClim's data are free for academic
and non-commercial use only, and may not be redistributed without permission.
"""

from worldclim_healpix_recipe.conventions import CONVENTIONS
from worldclim_healpix_recipe.recipe import RESOLUTIONS, SOURCE, VARIABLES, convert, settings, stage

__version__ = "0.1.0.dev0"
__all__ = ["CONVENTIONS", "RESOLUTIONS", "SOURCE", "VARIABLES", "convert", "settings", "stage"]
