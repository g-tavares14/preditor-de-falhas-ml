"""Validação da especificação de medição na borda do domínio."""

import pytest

from preditor_de_falhas_ml.domain.spec import (
    CountrySelection,
    MeasurementSpec,
    ProbeIdSelection,
    ResultFilters,
)


def test_country_is_normalized_and_oneoff_by_default():
    spec = MeasurementSpec(
        target=" 8.8.8.8 ",
        address_family=4,
        selection=CountrySelection(" br ", 2),
        packets=4,
    )
    assert spec.target == "8.8.8.8"
    assert spec.selection.country_code == "BR"
    assert spec.is_oneoff is True
    assert spec.as_configuration()["probe_count"] == 2


def test_interval_and_duration_together_make_recurring_spec():
    spec = MeasurementSpec(
        target="1.1.1.1",
        address_family=6,
        selection=ProbeIdSelection((1, 2)),
        interval=300,
        duration=3600,
    )
    assert spec.is_oneoff is False
    assert spec.as_configuration()["probe_ids"] == [1, 2]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"interval": 60, "duration": None},
        {"interval": None, "duration": 60},
        {"address_family": 5},
        {"packets": 17},
        {"target": ""},
    ],
)
def test_invalid_spec_is_rejected(kwargs):
    base = {
        "target": "8.8.8.8",
        "address_family": 4,
        "selection": CountrySelection("BR"),
    }
    with pytest.raises(ValueError):
        MeasurementSpec(**{**base, **kwargs})


@pytest.mark.parametrize("country", [None, 12, "", "B", "BRA", "B1", "BŔ", "BR,US"])
def test_invalid_country_code(country):
    with pytest.raises(ValueError, match="country_code inválido"):
        CountrySelection(country)


def test_stop_before_start_is_rejected():
    with pytest.raises(ValueError, match="stop inválido"):
        ResultFilters(start=20, stop=10)
