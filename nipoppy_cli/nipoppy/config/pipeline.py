"""Pipeline configuration."""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Optional, Union

from pydantic import ConfigDict, Field, model_validator

from nipoppy.config.container import ContainerInfo, SchemaWithContainerConfig
from nipoppy.config.pipeline_step import (
    BasePipelineStepConfig,
    BidsPipelineStepConfig,
    ProcPipelineStepConfig,
)


class BasePipelineConfig(SchemaWithContainerConfig, ABC):
    """Base schema for processing/BIDS pipeline configuration."""

    NAME: str = Field(description="Name of the pipeline")
    VERSION: str = Field(description="Version of the pipeline")
    DESCRIPTION: Optional[str] = Field(
        default=None, description="Free description field"
    )
    CONTAINER_INFO: ContainerInfo = Field(
        default=ContainerInfo(),
        description="Information about the container image file",
    )
    STEPS: list[Union[ProcPipelineStepConfig, BidsPipelineStepConfig]] = Field(
        default=[],
        description="List of pipeline step configurations",
    )

    @model_validator(mode="after")
    def validate_after(self):
        """
        Validate the pipeline configuration after creation.

        Specifically:
        - If STEPS has more than one item, make sure that each step has a unique name.
        """
        if len(self.STEPS) > 1:
            step_names = []
            for step in self.STEPS:
                if step.NAME is None:
                    raise ValueError(
                        "Found at least one step with undefined NAME field"
                        f" for pipeline {self.NAME} {self.VERSION}"
                        ". Pipeline steps must have names except "
                        "if there is only one step"
                    )
                if step.NAME in step_names:
                    raise ValueError(
                        f'Found at least two steps with NAME "{step.NAME}"'
                        f" for pipeline {self.NAME} {self.VERSION}"
                        ". Step names must be unique"
                    )
                step_names.append(step.NAME)

        return self

    def get_fpath_container(self) -> Path:
        """Return the path to the pipeline's container."""
        return self.CONTAINER_INFO.FILE

    def get_step_config(
        self, step_name: Optional[str] = None
    ) -> BasePipelineStepConfig:
        """
        Return the configuration for the given step.

        If step_name is None, return the configuration for the first step.
        """
        if len(self.STEPS) == 0:
            raise ValueError(
                f"No steps specified for pipeline {self.NAME} {self.VERSION}"
            )
        elif step_name is None:
            return self.STEPS[0]
        for step in self.STEPS:
            if step.NAME == step_name:
                return step
        raise ValueError(
            f"Step {step_name} not found in pipeline {self.NAME} {self.VERSION}"
        )

    def get_invocation_file(self, step_name: Optional[str] = None) -> Path | None:
        """
        Return the path to the invocation file for the given step.

        Is step is None, return the invocation file for the first step.
        """
        return self.get_step_config(step_name).INVOCATION_FILE

    def get_descriptor_file(self, step_name: Optional[str] = None) -> Path | None:
        """
        Return the path to the descriptor file for the given step.

        If step is None, return the descriptor file for the first step.
        """
        return self.get_step_config(step_name).DESCRIPTOR_FILE


class BidsPipelineConfig(BasePipelineConfig):
    """Schema for BIDS pipeline configuration."""

    model_config = ConfigDict(extra="forbid")

    def get_update_doughnut(self, step_name: Optional[str] = None) -> Path | None:
        """
        Return the update doughnut flag for the given step.

        If step is None, return the flag for the first step.
        """
        return self.get_step_config(step_name).UPDATE_DOUGHNUT


class ProcPipelineConfig(BasePipelineConfig):
    """Schema for processing pipeline configuration."""

    TRACKER_CONFIG_FILE: Optional[Path] = Field(
        default=None,
        description=(
            "Path to the tracker configuration file associated with the pipeline"
            ". This file must contain a list of tracker configurations"
            ", each of which must be a dictionary with a NAME field (string)"
            " and a PATHS field (non-empty list of strings)"
        ),
    )

    model_config = ConfigDict(extra="forbid")

    def get_pybids_ignore_file(self, step_name: Optional[str] = None) -> Path | None:
        """
        Return the list of regex patterns to ignore when building the PyBIDS layout.

        If step is None, return the patterns for the first step.
        """
        return self.get_step_config(step_name).PYBIDS_IGNORE_FILE
