"""Tracker configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrackerConfig(BaseModel):
    """Schema for tracker configuration."""

    NAME: str = Field(
        description="Unique name",
    )
    PATHS: list[Path] = Field(
        description=(
            "List of at least one path to track. A path can include template "
            "strings for participant/session IDs and/or glob expressions"
        ),
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_after(self):
        """
        Validate the configuration after instantiation.

        Specifically:
        - Make sure PATHS is not an empty list
        """
        if len(self.PATHS) == 0:
            raise ValueError(
                f"The tracker config must contain at least one path, got {self}"
            )
        return self


def check_tracker_configs(
    tracker_configs: list[TrackerConfig],
) -> list[TrackerConfig]:
    """
    Validate a list of tracker configs.

    Specifically:
    - Make sure all tracker configs have unique names
    """
    names = set()
    for tracker_config in tracker_configs:
        if tracker_config.NAME in names:
            raise ValueError(
                "All tracker configs must have unique names"
                f", got multiple instances with NAME={tracker_config.NAME}"
            )
        names.add(tracker_config.NAME)
    return tracker_configs
