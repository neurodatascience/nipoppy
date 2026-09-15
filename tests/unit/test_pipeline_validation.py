"""Tests for the nipoppy.pipeline_validation module."""

import logging
from contextlib import nullcontext
from pathlib import Path

import pytest
import pytest_mock

from nipoppy.config.pipeline import (
    BasePipelineConfig,
    BIDSificationPipelineConfig,
    ExtractionPipelineConfig,
    ProcessingPipelineConfig,
)
from nipoppy.config.schema import get_current_schema_version
from nipoppy.env import ConfigType, PipelineTypeEnum
from nipoppy.exceptions import ConfigError, FileOperationError, JSONError
from nipoppy.pipeline_validation import (
    _check_descriptor_file,
    _check_hpc_config_file,
    _check_invocation_file,
    _check_no_subdirectories,
    _check_pipeline_files,
    _check_pybids_ignore_file,
    _check_self_contained,
    _check_tracker_config_file,
    _load_pipeline_config_file,
    check_pipeline_bundle,
)
from tests.conftest import DPATH_TEST_DATA


@pytest.fixture()
def valid_config_data():
    """Minimal data for a valid BasePipelineConfig."""
    return {
        "NAME": "test_pipeline",
        "VERSION": "test_version",
        "SCHEMA_VERSION": get_current_schema_version(ConfigType.PIPELINE),
    }


def test_load_pipeline_config_file():
    assert isinstance(
        _load_pipeline_config_file(DPATH_TEST_DATA / "pipeline_config-valid.json5"),
        BasePipelineConfig,
    )


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [
        ("fake_path.json", FileOperationError, "Pipeline configuration file not found"),
        (
            DPATH_TEST_DATA / "pipeline_config-invalid1.json",
            ConfigError,
            "Pipeline configuration file .* is invalid",
        ),
        (
            DPATH_TEST_DATA / "pipeline_config-invalid2.json",
            ConfigError,
            "Pipeline configuration file .* is invalid",
        ),
        (
            DPATH_TEST_DATA / "pipeline_config-invalid3.json",
            ConfigError,
            "Pipeline configuration file .* is invalid",
        ),
    ],
)
def test_load_pipeline_config_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _load_pipeline_config_file(fpath)


def test_check_descriptor_file(caplog: pytest.LogCaptureFixture):
    _check_descriptor_file(DPATH_TEST_DATA / "descriptor-valid.json")
    assert len(caplog.records) == 0


def test_check_descriptor_file_deprecation_warning(caplog: pytest.LogCaptureFixture):

    _check_descriptor_file(DPATH_TEST_DATA / "descriptor-deprecated.json")

    assert any(
        [
            record.levelno == logging.WARNING
            and "This will be deprecated in the future" in record.message
            for record in caplog.records
        ]
    )


def test_check_descriptor_file_deprecation_error():

    with pytest.raises(
        ConfigError,
        match="Descriptor file .* contains Nipoppy-specific template variables",
    ):
        _check_descriptor_file(
            DPATH_TEST_DATA / "descriptor-deprecated.json", strict=True
        )


def test_check_descriptor_file_remains_strict_json(tmp_path: Path):
    fpath = tmp_path / "descriptor.json"
    fpath.write_text('{"name": "x",}')  # trailing comma makes it invalid JSON

    with pytest.raises(JSONError):
        _check_descriptor_file(fpath)


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [
        ("fake_path.json", FileOperationError, "Descriptor file not found"),
        (
            DPATH_TEST_DATA / "descriptor-invalid.json",
            ConfigError,
            "Descriptor file .* is invalid",
        ),
    ],
)
def test_check_descriptor_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _check_descriptor_file(fpath)


def test_check_invocation_file(caplog: pytest.LogCaptureFixture):
    _check_invocation_file(
        DPATH_TEST_DATA / "invocation-valid.json5",
        DPATH_TEST_DATA / "descriptor-valid.json",
    )

    assert len(caplog.records) == 0


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [
        ("fake_path.json", FileOperationError, "Invocation file not found"),
        (
            DPATH_TEST_DATA / "invocation-invalid.json",
            ConfigError,
            "Invocation file .* is invalid",
        ),
    ],
)
def test_check_invocation_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _check_invocation_file(fpath, DPATH_TEST_DATA / "descriptor-valid.json")


def test_check_hpc_config_file():
    _check_hpc_config_file(DPATH_TEST_DATA / "hpc_config-valid.json5")


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [
        ("fake_path.json", FileOperationError, "HPC config file not found"),
        (
            DPATH_TEST_DATA / "hpc_config-invalid.json",
            ConfigError,
            "HPC config file .* is invalid",
        ),
    ],
)
def test_check_hpc_config_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _check_hpc_config_file(fpath)


def test_check_tracker_config_file():
    _check_tracker_config_file(DPATH_TEST_DATA / "tracker_config-valid.json5")


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [
        ("fake_path.json", FileOperationError, "Tracker config file not found"),
        (
            DPATH_TEST_DATA / "tracker_config-invalid.json",
            ConfigError,
            "Tracker config file .* is invalid",
        ),
    ],
)
def test_check_tracker_config_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _check_tracker_config_file(fpath)


def test_check_pybids_ignore_file():
    _check_pybids_ignore_file(DPATH_TEST_DATA / "pybids_ignore-valid.json5")


@pytest.mark.parametrize(
    "fpath,exception_class,exception_message",
    [("fake_path.json", FileOperationError, "PyBIDS ignore patterns file not found")],
)
def test_check_pybids_ignore_file_invalid(fpath, exception_class, exception_message):
    with pytest.raises(exception_class, match=exception_message):
        _check_pybids_ignore_file(fpath)


@pytest.mark.parametrize(
    "pipeline_config_data,pipeline_class,n_files_expected,strict",
    [
        ({"STEPS": [{}]}, BasePipelineConfig, 0, False),
        (
            {
                "STEPS": [
                    {
                        "INVOCATION_FILE": "invocation-valid.json5",
                        "DESCRIPTOR_FILE": "descriptor-valid.json",
                        "HPC_CONFIG_FILE": "hpc_config-valid.json5",
                    },
                ],
                "PIPELINE_TYPE": PipelineTypeEnum.BIDSIFICATION,
            },
            BIDSificationPipelineConfig,
            3,
            False,
        ),
        (
            {
                "STEPS": [
                    {
                        "INVOCATION_FILE": "invocation-valid.json5",
                        "DESCRIPTOR_FILE": "descriptor-valid.json",
                        "HPC_CONFIG_FILE": "hpc_config-valid.json5",
                        "TRACKER_CONFIG_FILE": "tracker_config-valid.json5",
                        "PYBIDS_IGNORE_FILE": "pybids_ignore-valid.json5",
                    },
                ],
                "PIPELINE_TYPE": PipelineTypeEnum.PROCESSING,
            },
            ProcessingPipelineConfig,
            5,
            True,
        ),
        (
            {
                "PROC_DEPENDENCIES": [{"NAME": "test", "VERSION": "v1"}],
                "STEPS": [
                    {
                        "NAME": "step1",
                        "INVOCATION_FILE": "invocation-valid.json5",
                        "DESCRIPTOR_FILE": "descriptor-valid.json",
                        "HPC_CONFIG_FILE": "hpc_config-valid.json5",
                    },
                    {
                        "NAME": "step2",
                        "INVOCATION_FILE": "invocation-valid.json5",
                        "DESCRIPTOR_FILE": "descriptor-valid.json",
                        "HPC_CONFIG_FILE": "hpc_config-valid.json5",
                    },
                    {
                        "NAME": "step3",
                        "INVOCATION_FILE": "invocation-valid.json5",
                        "DESCRIPTOR_FILE": "descriptor-valid.json",
                    },
                ],
                "PIPELINE_TYPE": PipelineTypeEnum.EXTRACTION,
            },
            ExtractionPipelineConfig,
            8,
            True,
        ),
    ],
)
def test_check_pipeline_files(
    pipeline_config_data,
    pipeline_class,
    n_files_expected,
    valid_config_data,
    strict,
    mocker: pytest_mock.MockFixture,
):
    mocked_check_descriptor_file = mocker.patch(
        "nipoppy.pipeline_validation._check_descriptor_file",
        wraps=_check_descriptor_file,
    )

    pipeline_config = pipeline_class(**pipeline_config_data, **valid_config_data)
    files = _check_pipeline_files(pipeline_config, DPATH_TEST_DATA, strict=strict)

    # check that the function returns the expected number of files
    assert isinstance(files, list)
    assert n_files_expected == len(files)

    if n_files_expected > 0:
        mocked_check_descriptor_file.assert_called()
        assert mocked_check_descriptor_file.call_args[1].get("strict") == strict


@pytest.mark.no_xdist
def test_check_pipeline_files_logging(
    valid_config_data,
    caplog: pytest.LogCaptureFixture,
):
    log_level = logging.DEBUG
    caplog.set_level(log_level)

    pipeline_config = BasePipelineConfig(
        **valid_config_data,
        STEPS=[{}],
    )
    _check_pipeline_files(pipeline_config, DPATH_TEST_DATA)

    assert len(caplog.records) > 0
    assert all([record.levelno == log_level for record in caplog.records])


@pytest.mark.parametrize(
    "dpath_bundle,fpaths,valid",
    [
        ("bundle_dir", ["bundle_dir/file1.txt", "bundle_dir/file2.txt"], True),
        ("bundle_dir", ["bundle_dir/file1.txt", "bundle_dir/sub_dir/file2.txt"], True),
        ("bundle_dir", ["bundle_dir/file1.txt", "file2.txt"], False),
        ("bundle_dir", ["bundle_dir/file1.txt", "other_dir/file2.txt"], False),
        ("bundle_dir", ["bundle_dir/../file1.txt"], False),
    ],
)
def test_check_self_contained(dpath_bundle, fpaths, valid):
    with (
        nullcontext()
        if valid
        else pytest.raises(
            ValueError, match="Path .* is not within the bundle directory"
        )
    ):
        _check_self_contained(dpath_bundle, fpaths)


@pytest.mark.no_xdist
def test_check_self_container_logging(caplog: pytest.LogCaptureFixture):
    log_level = logging.DEBUG
    caplog.set_level(log_level)

    dpath_bundle = "bundle_dir"
    fpaths = ["bundle_dir/file1.txt", "bundle_dir/file2.txt"]
    _check_self_contained(dpath_bundle, fpaths)

    assert len(caplog.records) > 0
    assert all([record.levelno == log_level for record in caplog.records])


@pytest.mark.parametrize(
    "dpaths_to_create,fpaths_to_create,valid",
    [
        (["sub_dir1"], [], False),
        ([], ["file1.txt"], True),
        ([], [], True),
    ],
)
def test_check_no_subdirectories(
    tmp_path: Path, dpaths_to_create, fpaths_to_create, valid
):
    dpath_bundle = tmp_path / "bundle_dir"
    dpath_bundle.mkdir()

    for dpath in dpaths_to_create:
        (dpath_bundle / dpath).mkdir(parents=True, exist_ok=True)
    for fpath in fpaths_to_create:
        (dpath_bundle / fpath).touch()

    with (
        pytest.raises(
            ValueError, match="Bundle directory should not contain any subdirectories"
        )
        if not valid
        else nullcontext()
    ):
        _check_no_subdirectories(dpath_bundle)


@pytest.mark.no_xdist
def test_check_no_subdirectories_logging(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    log_level = logging.DEBUG
    caplog.set_level(log_level)

    dpath_bundle = tmp_path / "bundle_dir"
    dpath_bundle.mkdir()
    _check_no_subdirectories(dpath_bundle)

    assert len(caplog.records) > 0
    assert all([record.levelno == log_level for record in caplog.records])


@pytest.mark.parametrize(
    "log_level,strict",
    [(logging.DEBUG, False), (logging.INFO, True), (logging.WARNING, False)],
)
def test_check_pipeline_bundle(
    log_level: int, strict: bool, valid_config_data, mocker: pytest_mock.MockFixture
):
    dpath_bundle = Path("bundle_dir").resolve()
    config = BasePipelineConfig(**valid_config_data)
    fpaths = [dpath_bundle / "file1.txt", dpath_bundle / "file2.txt"]

    mocked_load_pipeline_config_file = mocker.patch(
        "nipoppy.pipeline_validation._load_pipeline_config_file",
        return_value=config,
    )
    mocked_check_pipeline_files = mocker.patch(
        "nipoppy.pipeline_validation._check_pipeline_files",
        return_value=fpaths,
    )
    mocked_check_self_contained = mocker.patch(
        "nipoppy.pipeline_validation._check_self_contained"
    )
    mocked_check_no_subdirectories = mocker.patch(
        "nipoppy.pipeline_validation._check_no_subdirectories"
    )

    check_pipeline_bundle(dpath_bundle, log_level=log_level, strict=strict)

    mocked_load_pipeline_config_file.assert_called_once_with(
        dpath_bundle / "config.json", strict=strict
    )
    mocked_check_pipeline_files.assert_called_once_with(
        config, dpath_bundle, log_level=log_level, strict=strict
    )
    mocked_check_self_contained.assert_called_once_with(dpath_bundle, fpaths)
    mocked_check_no_subdirectories.assert_called_once_with(dpath_bundle)
