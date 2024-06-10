"""Tests for the dataset init workflow."""

from pathlib import Path

import pytest

from nipoppy.utils import (
    DPATH_DESCRIPTORS,
    DPATH_INVOCATIONS,
    DPATH_LAYOUTS,
    DPATH_TRACKER_CONFIGS,
)
from nipoppy.workflows.dataset_init import InitWorkflow

from .conftest import ATTR_TO_DPATH_MAP, FPATH_CONFIG, FPATH_MANIFEST


@pytest.fixture(params=["my_dataset", "dataset_dir"])
def dpath_root(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    return tmp_path / request.param


def test_run(dpath_root: Path):
    workflow = InitWorkflow(dpath_root=dpath_root)
    workflow.run()

    # check that all directories have been created
    for path in ATTR_TO_DPATH_MAP.values():
        assert Path(dpath_root, path).exists()
        assert Path(dpath_root, path, "README.md").exists()

    # check that sample config files have been copied
    assert Path(dpath_root, FPATH_CONFIG).exists()
    assert Path(dpath_root, FPATH_MANIFEST).exists()

    # check that descriptor files have been copied
    for fpath in DPATH_DESCRIPTORS.iterdir():
        assert Path(
            dpath_root, ATTR_TO_DPATH_MAP["dpath_descriptors"], fpath.name
        ).exists()

    # check that sample invocation files have been copied
    for fpath in DPATH_INVOCATIONS.iterdir():
        assert Path(
            dpath_root, ATTR_TO_DPATH_MAP["dpath_invocations"], fpath.name
        ).exists()

    # check that sample tracker config files have been copied
    for fpath in DPATH_TRACKER_CONFIGS.iterdir():
        assert Path(
            dpath_root, ATTR_TO_DPATH_MAP["dpath_tracker_configs"], fpath.name
        ).exists()


def test_run_error(dpath_root: Path):
    dpath_root.mkdir(parents=True)
    workflow = InitWorkflow(dpath_root=dpath_root)
    with pytest.raises(FileExistsError, match="Dataset directory already exists"):
        workflow.run()


def test_custom_layout(dpath_root: Path):
    workflow = InitWorkflow(
        dpath_root=dpath_root, fpath_layout=DPATH_LAYOUTS / "layout-0.1.0.json"
    )
    workflow.run()

    # check some of the paths from the old spec exist
    assert (dpath_root / "proc").exists()
    assert (dpath_root / "dicom").exists()


@pytest.mark.parametrize("attr", ["config", "manifest", "doughnut"])
def test_config_attrs_error(attr):
    with pytest.raises(
        RuntimeError,
        match="The config property .* is not available*",
    ):
        getattr(InitWorkflow(dpath_root="my_dataset"), attr)
