"""Offline: the settings are valid healpix-convert settings and carry the definitions and licence."""

import pytest

import healpix_convert as hc

from worldclim_healpix_recipe import RESOLUTIONS, SOURCE, VARIABLES, settings


@pytest.mark.parametrize("variable", sorted(VARIABLES))
def test_settings_validate_with_healpix_convert(variable):
    assert hc.ConvertSettings.model_validate(settings(variable)) is not None


@pytest.mark.parametrize("variable", sorted(VARIABLES))
def test_units_are_set_explicitly(variable):
    group = settings(variable)["group_settings"]["worldclim/v21"]
    assert group["metadata"]["override_attrs"][variable]["units"] == VARIABLES[variable]["units"]


def test_definitions_name_the_sample_standard_deviation_and_the_plus_one():
    # WorldClim follows dismo::biovars, unlike CHELSA (population SD, no +1)
    assert "sample standard deviation (n-1)" in VARIABLES["bio4"]["long_name"]
    assert "plus 1 mm" in VARIABLES["bio15"]["long_name"]


def test_the_licence_is_not_presented_as_open():
    assert SOURCE["license"] == "other"
    links = settings("bio1")["metadata"]["stac"]["override_links"]
    assert links[0]["href"] == SOURCE["terms_url"]


def test_resolutions():
    assert RESOLUTIONS == ("30s", "2.5m", "5m", "10m")
