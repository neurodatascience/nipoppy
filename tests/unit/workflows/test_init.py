"""Tests for the dataset init workflow."""

import os
import re
import shutil
import subprocess
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_mock
from fids import fids

from nipoppy.env import FAKE_SESSION_ID, PROGRAM_VERSION
from nipoppy.exceptions import FileOperationError, WorkflowError
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import fileops
from nipoppy.utils.utils import (
    DPATH_HPC,
    DPATH_LAYOUTS,
    FPATH_SAMPLE_CONFIG,
    FPATH_SAMPLE_MANIFEST,
    load_json,
)
from nipoppy.workflows.dataset_init import InitWorkflow


@pytest.fixture(params=["my_dataset", "dataset_dir"])
def dpath_root(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    return tmp_path / request.param


@pytest.fixture
def workflow(dpath_root: Path) -> InitWorkflow:
    return InitWorkflow(dpath_root=dpath_root)


@pytest.fixture(autouse=True)
def isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Ignore any existing user config by setting HOME to a temporary directory."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def fake_bids_root(tmp_path: Path) -> Generator[Path]:
    """Create a fake BIDS dataset (with session folders) for testing."""
    bids_dir_path = tmp_path / "bids"
    fids.create_fake_bids_dataset(
        output_dir=bids_dir_path,
        subjects=["01"],
        sessions=["1", "2"],
        datatypes=["anat", "func"],
    )

    yield bids_dir_path

    # restore write permission for user
    # u=rwx, g=rx, o=rx
    if bids_dir_path.exists():
        os.chmod(bids_dir_path, 0o755)


@dataclass
class _HandleBIDSSourceResult:
    source_files_before_init: list[Path]
    source_files_after_init: list[Path]
    target_files: list[Path]


def _setup_handle_bids_source(workflow: InitWorkflow, fake_bids_root: Path, mode: str):
    dpath_root = workflow.study.layout.dpath_root

    source_files_before_init = [
        x.relative_to(fake_bids_root) for x in fake_bids_root.glob("**/*")
    ]

    workflow.bids_source = fake_bids_root
    workflow.mode = mode

    workflow._handle_bids_source()

    source_files_after_init = [
        x.relative_to(fake_bids_root) for x in fake_bids_root.glob("**/*")
    ]
    target_files = [
        x.relative_to(dpath_root / "bids") for x in dpath_root.glob("bids/**/*")
    ]

    return _HandleBIDSSourceResult(
        source_files_before_init=source_files_before_init,
        source_files_after_init=source_files_after_init,
        target_files=target_files,
    )


def _assert_manifest_creation(
    workflow: InitWorkflow,
    participant_ids: list[str] | None = None,
    session_ids: list[str] | None = None,
):
    # default is for the fake BIDS dataset created in the fixture
    if participant_ids is None:
        participant_ids = ["01", "01"]
    if session_ids is None:
        session_ids = ["1", "2"]
    datatypes = [["anat", "func"] for _ in participant_ids]

    assert isinstance(workflow.study.manifest, Manifest)
    assert (
        workflow.study.manifest[Manifest.col_participant_id].to_list()
        == participant_ids
    )
    assert workflow.study.manifest[Manifest.col_visit_id].to_list() == session_ids
    assert workflow.study.manifest[Manifest.col_session_id].to_list() == session_ids
    assert workflow.study.manifest[Manifest.col_datatype].to_list() == datatypes


def _assert_layout_creation(workflow):
    # check that all directories have been created (using layout-aware paths)
    for dpath in workflow.study.layout.get_paths(directory=True, include_optional=True):
        assert dpath.exists(), f"Expected directory not found: {dpath}"
        if (
            workflow.bids_source is not None
            and dpath == workflow.study.layout.dpath_bids
        ):
            # BIDS source directory should be copied/moved/symlinked without
            # modifications to its contents.
            continue
        # Check README exists for directories with descriptions (except .nipoppy)
        if dpath != workflow.study.layout.dpath_nipoppy and not dpath.is_symlink():
            readme_path = dpath / "README.md"
            # Only check README if this directory has a description in the layout
            path_info = None
            for info in workflow.study.layout.config.path_infos:
                if workflow.study.layout._prepend_study_path(info.path) == dpath:
                    path_info = info
                    break
            if path_info and path_info.description:
                assert readme_path.exists(), f"Expected README not found: {readme_path}"

    # check that required files have been created
    for fpath in workflow.study.layout.get_paths(
        directory=False, include_optional=False
    ):
        assert fpath.exists(), f"Expected file not found: {fpath}"

    # check that no pipeline config files have been copied
    assert (
        len(
            list(
                workflow.study.layout.dpath_pipelines.glob(
                    f"**/{workflow.study.layout.fname_pipeline_config}"
                )
            )
        )
        == 0
    )

    # check that HPC config files have been copied
    for fname in DPATH_HPC.glob("*"):
        assert (workflow.study.layout.dpath_hpc / fname.name).exists()


def assert_config_matches(fpath_actual: Path, fpath_expected: Path):
    assert load_json(fpath_actual, allow_json5=True) == load_json(
        fpath_expected, allow_json5=True
    )


@pytest.mark.no_xdist
@pytest.mark.parametrize(
    "fname_layout",
    ["layout-default.json", "layout-bids-study.json", "layout-0.1.0.json"],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_run(
    dpath_root: Path,
    caplog: pytest.LogCaptureFixture,
    fname_layout: str,
    dry_run: bool,
):
    workflow = InitWorkflow(
        dpath_root=dpath_root,
        fpath_layout=DPATH_LAYOUTS / fname_layout,
        dry_run=dry_run,
    )
    workflow.run()

    if dry_run:
        assert not dpath_root.exists()
    else:
        _assert_layout_creation(workflow)
        assert (
            workflow.study.layout.fpath_manifest.read_text()
            == FPATH_SAMPLE_MANIFEST.read_text()
        )

    assert f"Successfully initialized a dataset at {workflow.dpath_root}" in caplog.text


@pytest.mark.no_xdist
def test_run_no_success_message_on_error(
    workflow: InitWorkflow,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
):
    error_message = "fake error"
    mocker.patch.object(workflow, "run_main", side_effect=RuntimeError(error_message))

    with pytest.raises(RuntimeError, match=error_message):
        workflow.run()

    assert "Successfully initialized a dataset" not in caplog.text


def test_create_config_file_defaults_to_sample_when_user_config_missing(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
):
    mocker.patch(
        "nipoppy.workflows.dataset_init.FPATH_USER_CONFIG",
        tmp_path / "missing_config.json",
    )
    workflow._create_config_file()

    assert_config_matches(workflow.study.layout.fpath_config, FPATH_SAMPLE_CONFIG)
    assert "Default config file copied" in caplog.text
    assert "It may need to be edited to match your dataset" in caplog.text


def test_create_config_file_uses_user_config(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
):
    fpath_user_config = tmp_path / "config.json"
    fpath_user_config.write_text('{"CUSTOM": {"label": "config"}}\n')

    mocker.patch("nipoppy.workflows.dataset_init.FPATH_USER_CONFIG", fpath_user_config)
    workflow._create_config_file()

    assert_config_matches(workflow.study.layout.fpath_config, fpath_user_config)
    assert "Default config file copied" not in caplog.text


def test_create_config_file_default_config_ignores_user_config(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
):
    fpath_user_config = tmp_path / "config.json"
    fpath_user_config.write_text('{"CUSTOM": {"label": "config"}}\n')

    workflow.default_config = True

    mocker.patch("nipoppy.workflows.dataset_init.FPATH_USER_CONFIG", fpath_user_config)
    workflow._create_config_file()

    assert_config_matches(workflow.study.layout.fpath_config, FPATH_SAMPLE_CONFIG)
    assert "Default config file copied" in caplog.text
    assert "It may need to be edited to match your dataset" in caplog.text


def test_create_config_file_warns_and_falls_back_for_invalid_user_config(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mocker: pytest_mock.MockerFixture,
):
    fpath_user_config = tmp_path / "config.json"
    fpath_user_config.write_text('{"NOT_A_CONFIG_FIELD": "config"}\n')

    mocker.patch("nipoppy.workflows.dataset_init.FPATH_USER_CONFIG", fpath_user_config)
    workflow._create_config_file()

    assert_config_matches(workflow.study.layout.fpath_config, FPATH_SAMPLE_CONFIG)
    assert f"{fpath_user_config} is invalid" in caplog.text
    assert "Falling back to the default config file" in caplog.text
    assert "Default config file copied" in caplog.text
    assert "It may need to be edited to match your dataset" in caplog.text


def test_create_config_file_preserves_json5_comments(
    workflow: InitWorkflow, recwarn: pytest.WarningsRecorder
):
    workflow._create_config_file()

    study_config_content = workflow.study.layout.fpath_config.read_text()
    assert (
        "// Nipoppy will apply string substitutions when this file is loaded"
        in study_config_content
    )
    assert "[[NIPOPPY_VERSION]]" not in study_config_content
    assert PROGRAM_VERSION in study_config_content
    assert not any("Unable to replace" in str(warning.message) for warning in recwarn)


def test_run_warns_when_sample_manifest_copied(
    workflow: InitWorkflow, caplog: pytest.LogCaptureFixture
):
    workflow.run()

    assert "Sample manifest file copied" in caplog.text
    assert "It should be edited to match your dataset" in caplog.text


def test_empty_dir(workflow: InitWorkflow, dpath_root: Path):
    dpath_root.mkdir(parents=True)
    dpath_root.joinpath(".DS_STORE").touch()  # Allow macOS file

    workflow.run()

    _assert_layout_creation(workflow)


def test_non_empty_dir(workflow: InitWorkflow, dpath_root: Path):
    dpath_root.mkdir(parents=True)
    dpath_root.joinpath("unexpected_file").touch()

    with pytest.raises(FileOperationError, match="Study root directory is non-empty"):
        workflow.run()


def test_non_empty_dir_forced(workflow: InitWorkflow, dpath_root: Path):
    dpath_root.mkdir(parents=True)
    dpath_root.joinpath("unexpected_file").touch()

    workflow.force = True
    workflow.run()

    _assert_layout_creation(workflow)


def test_init_twice_force(workflow: InitWorkflow):
    # run once
    workflow.run()

    # run again with force=True, should succeed and not raise an error
    workflow.force = True
    workflow.run()

    _assert_layout_creation(workflow)


def test_run_main_container_store(
    workflow: InitWorkflow, tmp_path: Path, mocker: pytest_mock.MockerFixture
):
    workflow.container_store = tmp_path / "container_store"

    mocked = mocker.patch.object(fileops, "symlink", wraps=fileops.symlink)

    workflow.run_main()
    mocked.assert_called_once_with(
        workflow.container_store,
        workflow.study.layout.dpath_containers,
        force=workflow.force,
        dry_run=workflow.dry_run,
    )


def test_handle_bids_source_force(workflow: InitWorkflow, fake_bids_root: Path):
    """Test --force with --bids-source when BIDS directory already exists."""
    # Create target with existing bids directory
    existing_bids = workflow.study.layout.dpath_bids
    existing_bids.mkdir(parents=True)
    (existing_bids / "old_file.txt").write_text("old content")

    # Test with force=True - should succeed
    workflow.bids_source = fake_bids_root
    workflow.mode = "copy"
    workflow.force = True
    workflow._handle_bids_source()

    # Verify old content was replaced
    assert existing_bids.exists()
    assert not (existing_bids / "old_file.txt").exists()


def test_handle_bids_source_force_symlink(
    workflow: InitWorkflow, fake_bids_root: Path, dpath_root: Path, tmp_path: Path
):
    """Test --force with --bids-source when BIDS symlink already exists."""
    # Create another target for the old symlink
    old_target = tmp_path / "old_bids"
    old_target.mkdir()
    (old_target / "old_file.txt").write_text("old content")

    # Create target with existing bids symlink
    dpath_root.mkdir(parents=True)
    existing_bids_symlink = workflow.study.layout.dpath_bids
    existing_bids_symlink.symlink_to(old_target)

    # Test with force=True - should succeed
    workflow.bids_source = fake_bids_root
    workflow.mode = "symlink"
    workflow.force = True
    workflow._handle_bids_source()

    # Verify old symlink was replaced
    assert existing_bids_symlink.is_symlink()
    assert existing_bids_symlink.resolve() == fake_bids_root.resolve()
    assert old_target.exists()  # Old target should remain


def test_is_file(workflow: InitWorkflow, dpath_root: Path):
    dpath_root.touch()

    with pytest.raises(FileOperationError, match="Study root path is an existing file"):
        workflow.run()


def test_custom_layout(dpath_root: Path):
    workflow = InitWorkflow(
        dpath_root=dpath_root, fpath_layout=DPATH_LAYOUTS / "layout-0.1.0.json"
    )
    workflow.run()

    # check some of the paths from the old spec exist
    assert (dpath_root / "proc").exists()
    assert (dpath_root / "dicom").exists()


def test_bids_dataset_description_created(dpath_root: Path):
    """Test that dataset_description.json is created with BIDS study layout."""
    workflow = InitWorkflow(
        dpath_root=dpath_root, fpath_layout=DPATH_LAYOUTS / "layout-bids-study.json"
    )
    workflow.run()

    # The BIDS study layout includes an optional dataset_description.json file
    assert (dpath_root / "dataset_description.json").exists()


def test_bidsignore_created(dpath_root: Path):
    """Test that .bidsignore is created with BIDS study layout."""
    workflow = InitWorkflow(
        dpath_root=dpath_root, fpath_layout=DPATH_LAYOUTS / "layout-bids-study.json"
    )
    workflow.run()

    # The BIDS study layout includes an optional .bidsignore file
    fpath_bidsignore = dpath_root / ".bidsignore"
    assert fpath_bidsignore.exists()

    # Verify it contains Nipoppy-specific directories that aren't part of BIDS
    content = fpath_bidsignore.read_text()
    assert "scratch" in content


@pytest.mark.skipif(
    shutil.which("bids-validator-deno") is None,
    reason="bids-validator-deno not installed",
)
def test_bids_study_layout_passes_validation(dpath_root: Path):
    """Test that BIDS study layout passes BIDS validation with no errors."""
    workflow = InitWorkflow(
        dpath_root=dpath_root, fpath_layout=DPATH_LAYOUTS / "layout-bids-study.json"
    )
    workflow.run()

    # Run BIDS validator
    result = subprocess.run(
        ["bids-validator-deno", str(dpath_root), "--datasetTypes", "study"],
        capture_output=True,
        text=True,
    )

    # Check that there are no errors (warnings are OK)
    assert result.returncode == 0


@pytest.mark.parametrize("mode", ["copy", "move", "symlink"])
@pytest.mark.parametrize(
    "fname_layout", ["layout-default.json", "layout-bids-study.json"]
)
def test_init_bids(
    dpath_root: Path,
    fake_bids_root: Path,
    mocker: pytest_mock.MockerFixture,
    caplog: pytest.LogCaptureFixture,
    mode: str,
    fname_layout: str,
):
    """Test init from an existing BIDS dataset.

    Make sure:
    - manifest is created with the right content
    - handle_bids_source is called
    - README has been created
    """
    workflow = InitWorkflow(
        dpath_root=dpath_root,
        bids_source=fake_bids_root,
        mode=mode,
        fpath_layout=DPATH_LAYOUTS / fname_layout,
    )

    mocked_handle_bids_source = mocker.patch.object(
        workflow, "_handle_bids_source", wraps=workflow._handle_bids_source
    )

    workflow.run()

    _assert_layout_creation(workflow)
    _assert_manifest_creation(workflow)
    mocked_handle_bids_source.assert_called_once()
    assert "Sample manifest file copied" not in caplog.text


@pytest.mark.parametrize("mode", ["copy", "move", "symlink"])
@pytest.mark.parametrize("nested", [False, True], ids=["empty", "nested-bids"])
def test_init_bids_empty_manifest(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    mode: str,
    nested: bool,
):
    bids_source = tmp_path / "bids"
    bids_source.mkdir()
    if nested:
        (bids_source / "bids" / "sub-01" / "ses-1" / "anat").mkdir(parents=True)

    workflow.bids_source = bids_source
    workflow.mode = mode

    with pytest.raises(
        WorkflowError,
        match=re.escape(
            "Cannot initialize an empty manifest: no subjects found in BIDS source "
            f"directory {str(bids_source)}. "
            "Expected sub-* directories directly inside it."
        ),
    ):
        workflow.run()

    assert workflow.study.layout.dpath_bids.is_dir()
    assert workflow.study.layout.dpath_bids.is_symlink() == (mode == "symlink")
    assert bids_source.exists() == (mode != "move")
    # Failing to create the manifest from a BIDS dataset should fail immediately.
    assert list(workflow.dpath_root.iterdir()) == [workflow.study.layout.dpath_bids]
    assert "Successfully initialized a dataset" not in caplog.text


def test_handle_bids_source_invalid_mode(workflow: InitWorkflow, fake_bids_root: Path):
    # mode is invalid, should raise an error
    workflow.bids_source = fake_bids_root
    workflow.mode = "invalid"
    with pytest.raises(ValueError, match="Invalid mode: invalid"):
        workflow._handle_bids_source()


def test_handle_bids_source_copy(workflow: InitWorkflow, fake_bids_root: Path):
    """Check that all the new files match those in the source directory."""
    files = _setup_handle_bids_source(workflow, fake_bids_root, mode="copy")

    for f in files.source_files_after_init:
        assert f in files.target_files


def test_handle_bids_source_move(workflow: InitWorkflow, fake_bids_root: Path):
    """Check that all the files are moved and the source is empty."""
    files = _setup_handle_bids_source(workflow, fake_bids_root, mode="move")

    for f in files.source_files_before_init:
        assert f in files.target_files

    assert len(files.source_files_after_init) == 0


def test_handle_bids_source_symlink(workflow: InitWorkflow, fake_bids_root: Path):
    """Check that all the files are linked to the source files."""
    dpath_root = workflow.study.layout.dpath_root

    files = _setup_handle_bids_source(workflow, fake_bids_root, mode="symlink")

    for f in files.source_files_before_init:
        assert f in files.source_files_after_init

    # only the directory is linked, not the files within
    assert (dpath_root / "bids").is_symlink()
    assert (dpath_root / "bids").readlink() == fake_bids_root


def test_init_bids_readonly(
    workflow: InitWorkflow, fake_bids_root: Path, caplog: pytest.LogCaptureFixture
):
    """Test with an existing BIDS dataset that is read-only and has no README."""
    # The default behaviour is to add a README in the BIDS directory is none exists, but
    # this can fail if --bids-source is read-only and the mode is "symlink", so in those
    # cases, no README should be created
    workflow.bids_source = fake_bids_root
    workflow.mode = "symlink"

    # u=r-x, g=r-x, o=r-x
    os.chmod(fake_bids_root, 0o555)

    workflow.run()

    assert not (workflow.study.layout.dpath_bids / "README.md").exists()


@pytest.mark.parametrize("mode", ["copy", "move", "symlink"])
def test_init_bids_dry_run(workflow: InitWorkflow, fake_bids_root: Path, mode: str):
    """Copy no file when running in dry mode."""
    dpath_root = workflow.study.layout.dpath_root
    workflow.bids_source = fake_bids_root
    workflow.mode = mode
    workflow.dry_run = True
    workflow.run()

    assert not dpath_root.exists()


@pytest.mark.no_xdist
def test_manifest_from_bids_dataset_no_sessions(
    workflow: InitWorkflow,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    """Test manifest creation from a BIDS dataset with no session-level folders.

    Make sure:
    - raise a warning if subject has no session.
    - manifest is created with the right content
    """
    bids_to_copy = tmp_path / "bids"
    fids.create_fake_bids_dataset(
        output_dir=bids_to_copy,
        subjects=["01"],
        sessions=None,  # no session-level folders
        datatypes=["anat", "func"],
    )
    workflow.bids_source = bids_to_copy
    workflow._handle_bids_source()
    workflow._init_manifest_from_bids_dataset()

    assert (
        f"Could not find session-level folder(s) for participant sub-01, using session {FAKE_SESSION_ID} in the manifest"
        in caplog.text
    )

    _assert_manifest_creation(
        workflow, participant_ids=["01"], session_ids=[FAKE_SESSION_ID]
    )
