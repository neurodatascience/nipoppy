"""Boutiques configuration model and utility functions."""

from pydantic import ConfigDict, Field

from nipoppy.config.container import SchemaWithContainerConfig

BOUTIQUES_CUSTOM_KEY = "custom"  # as defined by Boutiques schema
BOUTIQUES_CONFIG_KEY = "nipoppy"


class BoutiquesConfig(SchemaWithContainerConfig):
    """Schema for custom configuration within a Boutiques descriptor."""

    CONTAINER_SUBCOMMAND: str = Field(
        default="run", description="Subcommand for Apptainer/Singularity call"
    )
    # dpath_participant_session_result (for tarring/zipping/extracting)
    # run_on (for choosing which participants/sessions to run on)
    # with_pybids (for pybids)

    model_config = ConfigDict(extra="forbid")


def get_boutiques_config_from_descriptor(descriptor: dict) -> BoutiquesConfig:
    """Return the Boutiques configuration object from a descriptor."""
    try:
        data = descriptor[BOUTIQUES_CUSTOM_KEY][BOUTIQUES_CONFIG_KEY]
    except Exception:
        raise RuntimeError(
            "The Boutiques descriptor does not have a"
            f" {BOUTIQUES_CUSTOM_KEY}/{BOUTIQUES_CONFIG_KEY} field: {descriptor}"
        )
    return BoutiquesConfig(**data)
