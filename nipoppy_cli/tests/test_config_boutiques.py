"""Tests for Boutiques utilities."""

import pytest
from pydantic import ValidationError

from nipoppy.config.boutiques import (
    BoutiquesConfig,
    get_boutiques_config_from_descriptor,
)

FIELDS_BOUTIQUES = ["CONTAINER_CONFIG", "CONTAINER_SUBCOMMAND"]


def test_boutiques_config():
    # test that default values are set
    boutiques_config = BoutiquesConfig()
    for field in FIELDS_BOUTIQUES:
        assert hasattr(boutiques_config, field)
    assert len(boutiques_config.model_fields) == len(FIELDS_BOUTIQUES)


def test_boutiques_config_no_extra_fields():
    with pytest.raises(ValidationError):
        BoutiquesConfig(not_a_field="a")


@pytest.mark.parametrize(
    "descriptor",
    [
        {"custom": {"nipoppy": {}}},
        {"custom": {"nipoppy": {}}},
        {"custom": {"nipoppy": {"CONTAINER_CONFIG": {"ARGS": ["--cleanenv"]}}}},
    ],
)
def test_get_boutiques_config_from_descriptor(descriptor):
    assert isinstance(get_boutiques_config_from_descriptor(descriptor), BoutiquesConfig)


@pytest.mark.parametrize(
    "descriptor",
    [
        {},
        {"custom": {}},
        {"custom": {"NIPOPPY": {}}},
    ],
)
def test_get_boutiques_config_from_descriptor_error(descriptor):
    with pytest.raises(RuntimeError, match="The Boutiques descriptor does not have a"):
        get_boutiques_config_from_descriptor(descriptor)
