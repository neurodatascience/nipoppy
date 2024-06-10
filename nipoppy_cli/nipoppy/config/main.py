"""Dataset configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from pydantic import ConfigDict, Field, model_validator
from typing_extensions import Self

from nipoppy.config.container import SchemaWithContainerConfig
from nipoppy.config.pipeline import PipelineConfig
from nipoppy.layout import DEFAULT_LAYOUT_INFO
from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.utils import (
    BIDS_SESSION_PREFIX,
    StrOrPathLike,
    apply_substitutions_to_json,
    check_session,
    check_session_strict,
    load_json,
)


class Config(SchemaWithContainerConfig):
    """Schema for dataset configuration."""

    DATASET_NAME: str = Field(description="Name of the dataset")
    VISITS: list[str] = Field(description="List of visits available in the study")
    SESSIONS: Optional[list[str]] = Field(
        default=None,  # will be a list after validation
        description=(
            "List of BIDS-compliant sessions available in the study"
            f', prefixed with "{BIDS_SESSION_PREFIX}"'
            " (inferred from VISITS if not given)"
        ),
    )
    DICOM_DIR_MAP_FILE: Optional[Path] = Field(
        default=None,
        description=(
            "Path to a CSV file mapping participant IDs to DICOM directories"
            ", to be used in the DICOM reorg step. Note: this field and "
            "DICOM_DIR_PARTICIPANT_FIRST cannot both be specified"
            f'. The CSV should have three columns: "{DicomDirMap.col_participant_id}"'
            f' , "{DicomDirMap.col_session}"'
            f', and "{DicomDirMap.col_participant_dicom_dir}"'
        ),
    )
    DICOM_DIR_PARTICIPANT_FIRST: Optional[bool] = Field(
        default=None,
        description=(
            "Whether subdirectories under the raw dicom directory (default: "
            f"{DEFAULT_LAYOUT_INFO.dpath_raw_dicom}) follow the pattern "
            "<PARTICIPANT>/<SESSION> (default) or <SESSION>/<PARTICIPANT>. Note: "
            "this field and and DICOM_DIR_MAP_FILE cannot both be specified"
        ),
    )
    SUBSTITUTIONS: dict[str, str] = Field(
        default={},
        description=(
            "Top-level mapping for replacing placeholder expressions in the rest "
            "of the config file. Note: the replacement only happens if the config "
            "is loaded from a file with :func:`nipoppy.config.main.Config.load`"
        ),
    )
    BIDS_PIPELINES: list[PipelineConfig] = Field(
        default=[], description="Configurations for BIDS conversion, if applicable"
    )
    PROC_PIPELINES: list[PipelineConfig] = Field(
        description="Configurations for processing pipelines"
    )
    CUSTOM: dict = Field(
        default={},
        description="Free field that can be used for any purpose",
    )

    model_config = ConfigDict(extra="forbid")

    def _check_sessions_have_prefix(self) -> Self:
        """Check that sessions have the BIDS prefix."""
        for session in self.SESSIONS:
            check_session_strict(session)
        return self

    def _check_dicom_dir_options(self) -> Self:
        """Check that only one DICOM directory mapping option is given."""
        if (
            self.DICOM_DIR_MAP_FILE is not None
            and self.DICOM_DIR_PARTICIPANT_FIRST is not None
        ):
            raise ValueError(
                "Cannot specify both DICOM_DIR_MAP_FILE and DICOM_DIR_PARTICIPANT_FIRST"
                f". Got DICOM_DIR_MAP_FILE={self.DICOM_DIR_MAP_FILE} and "
                f"DICOM_DIR_PARTICIPANT_FIRST={self.DICOM_DIR_PARTICIPANT_FIRST}"
            )

        return self

    def _check_no_duplicate_pipeline(self) -> Self:
        """Check that BIDS_PIPELINES and PROC_PIPELINES do not have common pipelines."""
        pipeline_infos = set()
        for pipeline_config in self.BIDS_PIPELINES + self.PROC_PIPELINES:
            pipeline_info = (pipeline_config.NAME, pipeline_config.VERSION)
            if pipeline_info in pipeline_infos:
                raise ValueError(
                    f"Found multiple configurations for pipeline {pipeline_info}"
                    "Make sure pipeline name and versions are unique across "
                    f"BIDS_PIPELINES and PROC_PIPELINES."
                )
            pipeline_infos.add(pipeline_info)

        return self

    def propagate_container_config(self) -> Self:
        """Propagate the container config to all pipelines."""

        def _propagate(pipeline_configs: list[PipelineConfig]):
            for pipeline_config in pipeline_configs:
                pipeline_container_config = pipeline_config.get_container_config()
                if pipeline_container_config.INHERIT:
                    pipeline_container_config.merge(
                        self.CONTAINER_CONFIG, overwrite_command=True
                    )
                for pipeline_step in pipeline_config.STEPS:
                    step_container_config = pipeline_step.get_container_config()
                    if step_container_config.INHERIT:
                        step_container_config.merge(
                            pipeline_container_config, overwrite_command=True
                        )

        _propagate(self.BIDS_PIPELINES)
        _propagate(self.PROC_PIPELINES)

        return self

    @model_validator(mode="before")
    @classmethod
    def check_input(cls, data: Any):
        """Validate the raw input."""
        key_sessions = "SESSIONS"
        key_visits = "VISITS"
        if isinstance(data, dict):
            # if sessions are not given, infer from visits
            if key_sessions not in data:
                data[key_sessions] = [
                    check_session(visit) for visit in data[key_visits]
                ]

        return data

    @model_validator(mode="after")
    def validate_and_process(self) -> Self:
        """Validate and process the configuration."""
        self._check_sessions_have_prefix()
        self._check_dicom_dir_options()
        self._check_no_duplicate_pipeline()
        return self

    def get_pipeline_version(self, pipeline_name: str) -> str:
        """Get the first version associated with a pipeline.

        Parameters
        ----------
        pipeline_name : str
            Name of the pipeline, as specified in the config

        Returns
        -------
        str
            The pipeline version
        """
        # assume there are no duplicates
        # technically BIDS_PIPELINES and PROC_PIPELINES can share a pipeline name
        # and have different versions, but this is unlikely (and probably a mistake)
        for pipeline_config in self.PROC_PIPELINES + self.BIDS_PIPELINES:
            if pipeline_config.NAME == pipeline_name:
                return pipeline_config.VERSION

        raise ValueError(f"No config found for pipeline with NAME={pipeline_name}")

    def get_pipeline_config(
        self,
        pipeline_name: str,
        pipeline_version: str,
    ) -> PipelineConfig:
        """Get the config for a BIDS or processing pipeline."""
        # pooling them together since there should not be any duplicates
        for pipeline_config in self.PROC_PIPELINES + self.BIDS_PIPELINES:
            if (
                pipeline_config.NAME == pipeline_name
                and pipeline_config.VERSION == pipeline_version
            ):
                return pipeline_config

        raise ValueError(
            "No config found for pipeline with "
            f"NAME={pipeline_name}, "
            f"VERSION={pipeline_version}"
        )

    def save(self, fpath: StrOrPathLike, **kwargs):
        """Save the config to a JSON file.

        Parameters
        ----------
        fpath : nipoppy.utils.StrOrPathLike
            Path to the JSON file to write
        """
        fpath: Path = Path(fpath)
        if "indent" not in kwargs:
            kwargs["indent"] = 4
        fpath.parent.mkdir(parents=True, exist_ok=True)
        with open(fpath, "w") as file:
            file.write(self.model_dump_json(**kwargs))

    def apply_substitutions_to_json(self, json_obj: dict | list) -> dict | list:
        """Apply substitutions to a JSON object."""
        return apply_substitutions_to_json(json_obj, self.SUBSTITUTIONS)

    @classmethod
    def load(cls, path: StrOrPathLike, apply_substitutions=True) -> Self:
        """Load a dataset configuration from a file."""
        substitutions_key = "SUBSTITUTIONS"
        config_dict = load_json(path)
        substitutions = config_dict.get(substitutions_key, {})
        if apply_substitutions and substitutions:
            # apply user-defined substitutions to all fields except SUBSTITUTIONS itself
            config = cls(**apply_substitutions_to_json(config_dict, substitutions))
            config.SUBSTITUTIONS = substitutions
        else:
            config = cls(**config_dict)

        return config
