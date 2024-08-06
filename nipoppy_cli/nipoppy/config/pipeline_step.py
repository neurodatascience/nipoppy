"""Pipeline step configuration."""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Optional

from pydantic import ConfigDict, Field

from nipoppy.config.container import SchemaWithContainerConfig
from nipoppy.tabular.doughnut import Doughnut


class BasePipelineStepConfig(SchemaWithContainerConfig, ABC):
    """Schema for processing pipeline step configuration."""

    NAME: Optional[str] = Field(
        default=None,
        description="Step name, required if the pipeline has multiple steps",
    )
    DESCRIPTOR_FILE: Optional[Path] = Field(
        default=None,
        description=(
            "Path to the JSON descriptor file. Only needed for custom pipelines "
        ),
    )
    INVOCATION_FILE: Optional[Path] = Field(
        default=None,
        description=("Path to the JSON invocation file"),
    )


class ProcPipelineStepConfig(BasePipelineStepConfig):
    """Schema for processing pipeline step configuration."""

    PYBIDS_IGNORE_FILE: Optional[Path] = Field(
        default=None,
        description=(
            "Path to file containing a list of regex patterns (strings) to ignore "
            "when building the PyBIDS layout"
        ),
    )
    model_config = ConfigDict(extra="forbid")


class BidsPipelineStepConfig(BasePipelineStepConfig):
    """Schema for BIDS pipeline step configuration."""

    UPDATE_DOUGHNUT: Optional[bool] = Field(
        default=False,
        description=(
            f"Whether or not the {Doughnut.col_in_bids} column "
            "in the doughnut file should be updated"
        ),
    )
    model_config = ConfigDict(extra="forbid")
