"""Pipeline store functions."""

import json
import logging
from pathlib import Path

from pydantic_core import ValidationError

from nipoppy.config.hpc import HpcConfig
from nipoppy.config.pipeline import (
    BasePipelineConfig,
    BIDSificationPipelineConfig,
    ExtractionPipelineConfig,
    ProcessingPipelineConfig,
)
from nipoppy.config.pipeline_step import ProcPipelineStepConfig
from nipoppy.config.schema import ensure_schema_version_exists
from nipoppy.config.tracker import TrackerConfig
from nipoppy.env import ConfigType, PipelineTypeEnum, StrOrPathLike
from nipoppy.exceptions import ConfigError, FileOperationError
from nipoppy.layout import DatasetLayout, LayoutError
from nipoppy.logger import get_logger
from nipoppy.utils.utils import TEMPLATE_REPLACE_PATTERN, load_json
from nipoppy.workflows.base import _run_command

logger = get_logger()

PIPELINE_TYPE_TO_CLASS = {
    PipelineTypeEnum.BIDSIFICATION: BIDSificationPipelineConfig,
    PipelineTypeEnum.EXTRACTION: ExtractionPipelineConfig,
    PipelineTypeEnum.PROCESSING: ProcessingPipelineConfig,
}


class PipelineValidationError(LayoutError): ...  # noqa E701


# TODO we should probably refactor the config loaders to extract the check for
# file existence and JSON validity into reusable functions
def _load_pipeline_config_file(
    fpath_config: Path, strict: bool = False
) -> BasePipelineConfig:
    """Load the main pipeline configuration file."""
    fpath_config: Path = Path(fpath_config)
    if not fpath_config.exists():
        raise FileOperationError(
            f"Pipeline configuration file not found: {fpath_config}"
        )

    config_dict = load_json(fpath_config, allow_json5=True)

    try:
        config = BasePipelineConfig(**config_dict)
        config = PIPELINE_TYPE_TO_CLASS[config.PIPELINE_TYPE](**config_dict)
    except ValidationError as exception:
        raise ConfigError(
            f"Pipeline configuration file {fpath_config} is invalid:\n{exception}"
        )

    ensure_schema_version_exists(fpath_config, ConfigType.PIPELINE, strict=strict)

    return config


def _check_descriptor_file(fpath_descriptor: StrOrPathLike, strict: bool = False):
    """Validate a Boutiques descriptor file."""
    fpath_descriptor: Path = Path(fpath_descriptor)
    if not fpath_descriptor.exists():
        raise FileOperationError(f"Descriptor file not found: {fpath_descriptor}")

    descriptor_dict = load_json(fpath_descriptor)

    descriptor_str = json.dumps(descriptor_dict)
    process, (stdout, stderr) = _run_command(
        ["bosh", "validate", str(fpath_descriptor)],
        check=False,
        log_command=False,
        log_output=False,
        capture_output=True,
    )
    if process.returncode != 0:
        raise ConfigError(
            f"Descriptor file {fpath_descriptor} is invalid:\n{stdout}\n{stderr}"
        )

    if TEMPLATE_REPLACE_PATTERN.search(descriptor_str) is not None:
        error_message = f"Descriptor file {fpath_descriptor} contains Nipoppy-specific template variables. "  # noqa E501
        if strict:
            raise ConfigError(
                error_message
                + 'Please remove these variables, add a "container-image" field, and update "command-line" to include the pipeline executable. '  # noqa E501
                + "See example here: https://zenodo.org/records/16876772?preview_file=descriptor.json."  # noqa E501
            )
        else:
            logger.warning(
                error_message
                + "This will be deprecated in the future: you should update this file following steps listed in https://nipoppy.readthedocs.io/en/0.4.1/changelog.html#release-0-4-1."  # noqa E501
            )


def _check_invocation_file(fpath_invocation: Path, fpath_descriptor: Path) -> None:
    """Validate a Boutiques invocation file."""
    fpath_invocation: Path = Path(fpath_invocation)
    if not fpath_invocation.exists():
        raise FileOperationError(f"Invocation file not found: {fpath_invocation}")

    invocation_dict = load_json(fpath_invocation, allow_json5=True)

    process, (stdout, stderr) = _run_command(
        [
            "bosh",
            "invocation",
            "--invocation",
            json.dumps(invocation_dict),
            str(fpath_descriptor),
        ],
        check=False,
        log_command=False,
        log_output=False,
        capture_output=True,
    )
    if process.returncode != 0:
        raise ConfigError(
            f"Invocation file {fpath_invocation} is invalid:\n{stdout}\n{stderr}"
        )


def _check_hpc_config_file(fpath_hpc_config: Path) -> None:
    """Validate an HPC config file."""
    fpath_hpc_config: Path = Path(fpath_hpc_config)
    if not fpath_hpc_config.exists():
        raise FileOperationError(f"HPC config file not found: {fpath_hpc_config}")

    hpc_config_dict = load_json(fpath_hpc_config, allow_json5=True)

    try:
        HpcConfig(**hpc_config_dict)
    except ValidationError as exception:
        raise ConfigError(
            f"HPC config file {fpath_hpc_config} is invalid:\n{exception}"
        )


def _check_tracker_config_file(
    fpath_tracker_config: Path, strict: bool = False
) -> None:
    """Validate a tracker config file."""
    fpath_tracker_config: Path = Path(fpath_tracker_config)
    if not fpath_tracker_config.exists():
        raise FileOperationError(
            f"Tracker config file not found: {fpath_tracker_config}"
        )

    tracker_config_dict = load_json(fpath_tracker_config, allow_json5=True)

    try:
        TrackerConfig(**tracker_config_dict)
    except ValidationError as exception:
        raise ConfigError(
            f"Tracker config file {fpath_tracker_config} is invalid:\n{exception}"
        )

    ensure_schema_version_exists(
        fpath_tracker_config, ConfigType.TRACKER, strict=strict
    )


def _check_pybids_ignore_file(fpath_pybids_ignore: Path) -> None:
    """Validate a PyBIDS ignore patterns file."""
    fpath_pybids_ignore: Path = Path(fpath_pybids_ignore)
    if not fpath_pybids_ignore.exists():
        raise FileOperationError(
            f"PyBIDS ignore patterns file not found: {fpath_pybids_ignore}"
        )

    load_json(fpath_pybids_ignore, allow_json5=True)


def _check_pipeline_files(
    pipeline_config: BasePipelineConfig,
    dpath_bundle: StrOrPathLike,
    *,
    strict: bool = False,
    log_level: int = logging.DEBUG,
) -> list[Path]:
    """
    Validate the files that the pipeline config points to.

    For each step in the pipeline configuration, validate:

    - the descriptor file (if present)
    - the invocation file (if present)
    - the HPC config file (if present)
    - the tracker config file (if present and pipeline is a processing pipeline)
    - the PyBIDS ignore patterns file (if present and pipeline is a processing pipeline)

    If strict is True, raise error instead of warning in descriptor check.

    Also, collect all file paths for these files for further checks.
    """
    dpath_bundle = Path(dpath_bundle)

    # collect paths
    fpaths = []

    for step in pipeline_config.STEPS:
        logger.log(level=log_level, msg=f"Validating files for step: {step.NAME}")

        if step.DESCRIPTOR_FILE is not None:
            logger.log(
                level=log_level,
                msg=f"\tChecking descriptor file: {step.DESCRIPTOR_FILE}",
            )
            fpath_descriptor = dpath_bundle / step.DESCRIPTOR_FILE
            _check_descriptor_file(fpath_descriptor, strict=strict)
            fpaths.append(fpath_descriptor)

            if step.INVOCATION_FILE is not None:
                logger.log(
                    level=log_level,
                    msg=f"\tChecking invocation file: {step.INVOCATION_FILE}",
                )
                fpath_invocation = dpath_bundle / step.INVOCATION_FILE
                _check_invocation_file(fpath_invocation, fpath_descriptor)
                fpaths.append(fpath_invocation)

        if step.HPC_CONFIG_FILE is not None:
            logger.log(
                level=log_level,
                msg=f"\tChecking HPC config file: {step.HPC_CONFIG_FILE}",
            )
            fpath_hpc_config = dpath_bundle / step.HPC_CONFIG_FILE
            _check_hpc_config_file(fpath_hpc_config)
            fpaths.append(fpath_hpc_config)

        if isinstance(step, ProcPipelineStepConfig):
            if step.TRACKER_CONFIG_FILE is not None:
                logger.log(
                    level=log_level,
                    msg=f"\tChecking tracker config file: {step.TRACKER_CONFIG_FILE}",
                )
                fpath_tracker_config = dpath_bundle / step.TRACKER_CONFIG_FILE
                _check_tracker_config_file(fpath_tracker_config, strict=strict)
                fpaths.append(fpath_tracker_config)

            if step.PYBIDS_IGNORE_FILE is not None:
                logger.log(
                    level=log_level,
                    msg=(
                        "\tChecking PyBIDS ignore patterns file:",
                        step.PYBIDS_IGNORE_FILE,
                    ),
                )
                fpath_pybids_ignore = dpath_bundle / step.PYBIDS_IGNORE_FILE
                _check_pybids_ignore_file(fpath_pybids_ignore)
                fpaths.append(fpath_pybids_ignore)

    return fpaths


def _check_self_contained(
    dpath_bundle: StrOrPathLike,
    fpaths: list[StrOrPathLike],
) -> None:
    """Check that all files are within the bundle directory."""
    dpath_bundle: Path = Path(dpath_bundle).resolve()
    logger.debug("Checking that all files are within the bundle directory")
    for fpath in fpaths:
        if dpath_bundle not in Path(fpath).resolve().parents:
            raise PipelineValidationError(
                f"Path {fpath} is not within the bundle directory {dpath_bundle}"
            )


def _check_no_subdirectories(dpath_bundle: StrOrPathLike):
    dpath_bundle: Path = Path(dpath_bundle)
    logger.debug(
        "Checking that there are no subdirectories inside the bundle directory"
    )
    for path in dpath_bundle.iterdir():
        if path.is_dir():
            raise PipelineValidationError(
                f"Bundle directory should not contain any subdirectories, found {path}"
            )


def check_pipeline_bundle(
    dpath_bundle: StrOrPathLike,
    log_level: int = logging.DEBUG,
    *,
    strict: bool = False,
) -> BasePipelineConfig:
    """
    Load a pipeline bundle's main configuration file and validate it.

    If strict is True, raise error instead of warning in descriptor check.
    """
    dpath_bundle = Path(dpath_bundle).resolve()
    fpath_config: Path = dpath_bundle / DatasetLayout.fname_pipeline_config

    # try to load the configuration file
    config = _load_pipeline_config_file(fpath_config, strict=strict)

    # core file content validation
    fpaths = _check_pipeline_files(
        config, dpath_bundle, log_level=log_level, strict=strict
    )

    # make sure that all files are within the bundle directory
    _check_self_contained(dpath_bundle, fpaths)

    # make sure that there are no subdirectories inside the bundle directory
    _check_no_subdirectories(dpath_bundle)

    return config
