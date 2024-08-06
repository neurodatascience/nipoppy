"""Tests for dataset layout class."""

import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from nipoppy.layout import DatasetLayout, PathInfo
from nipoppy.utils import DPATH_LAYOUTS, FPATH_DEFAULT_LAYOUT

from .conftest import (
    ATTR_TO_DPATH_MAP,
    ATTR_TO_REQUIRED_FPATH_MAP,
    DPATH_TEST_DATA,
    create_empty_dataset,
)


@pytest.fixture(params=["my_dataset", "dataset_dir"])
def dpath_root(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    return tmp_path / request.param


def create_invalid_dataset(dpath_root: Path, paths_to_delete: list[str]):
    create_empty_dataset(dpath_root)
    for path in paths_to_delete:
        path_to_delete = dpath_root / path
        if path_to_delete.is_file():
            path_to_delete.unlink()
        else:
            shutil.rmtree(path_to_delete, ignore_errors=True)


def test_config_path_infos():
    config = DatasetLayout("my_dataset").config
    assert all([isinstance(path_info, PathInfo) for path_info in config.path_infos])


def test_init_default(dpath_root):
    layout = DatasetLayout(dpath_root=dpath_root)
    for attr, path in {**ATTR_TO_DPATH_MAP, **ATTR_TO_REQUIRED_FPATH_MAP}.items():
        assert getattr(layout, attr) == Path(dpath_root) / path


@pytest.mark.parametrize(
    "fpath_spec",
    [
        None,
        FPATH_DEFAULT_LAYOUT,
        DPATH_LAYOUTS / "layout-0.1.0.json",
        DPATH_TEST_DATA / "layout1.json",
        DPATH_TEST_DATA / "layout2.json",
    ],
)
def test_init_custom_layout(dpath_root, fpath_spec):
    DatasetLayout(dpath_root=dpath_root, fpath_config=fpath_spec)


@pytest.mark.parametrize(
    "fpath_spec",
    [
        DPATH_TEST_DATA / "layout_invalid1.json",
        DPATH_TEST_DATA / "layout_invalid2.json",
    ],
)
def test_init_invalid_layout(dpath_root, fpath_spec):
    with pytest.raises(ValidationError):
        DatasetLayout(dpath_root=dpath_root, fpath_config=fpath_spec)


def test_init_config_not_found(dpath_root):
    with pytest.raises(FileNotFoundError, match="Layout config file not found"):
        DatasetLayout(dpath_root=dpath_root, fpath_config="fake_path")


@pytest.mark.parametrize(
    "dpath_root,path,expected",
    [
        ("my_dataset", "relative/path", Path("my_dataset/relative/path")),
        ("my_dataset", Path("relative/path"), Path("my_dataset/relative/path")),
        (Path("my_dataset"), "relative/path", Path("my_dataset/relative/path")),
        ("dataset_root", "other/path", Path("dataset_root/other/path")),
    ],
)
def test_get_full_path(dpath_root: Path, path, expected):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert layout.get_full_path(path) == expected


def test_dpaths(dpath_root: Path):
    layout = DatasetLayout(dpath_root=dpath_root)
    dpaths = layout.dpaths
    for path in ATTR_TO_DPATH_MAP.values():
        assert Path(dpath_root / path) in dpaths


def test_fpaths(dpath_root: Path):
    layout = DatasetLayout(dpath_root=dpath_root)
    fpaths = layout.fpaths
    for path in ATTR_TO_REQUIRED_FPATH_MAP.values():
        assert Path(dpath_root / path) in fpaths


@pytest.mark.parametrize(
    "paths_to_delete",
    [
        [],
        ["sourcedata", "downloads"],
        ["bids", "derivatives"],
        [
            "proc",
            "proc/containers",
            "proc/descriptors",
            "proc/invocations",
            "proc/scripts",
            "global_config.json",
            "proc/pybids",
            "proc/pybids/bids_db",
            "proc/pybids/ignore_patterns",
        ],
        [
            "scratch",
            "scratch/logs",
            "scratch/raw_dicom",
        ],
        [
            "tabular",
            "manifest.csv",
            "tabular/assessments",
            "tabular/demographics",
        ],
    ],
)
def test_find_missing_paths(dpath_root: Path, paths_to_delete: list[str]):
    create_invalid_dataset(dpath_root, paths_to_delete)
    layout = DatasetLayout(dpath_root=dpath_root)
    assert len(layout._find_missing_paths()) == len(paths_to_delete)


def test_validate(dpath_root: Path):
    create_empty_dataset(dpath_root)
    assert DatasetLayout(dpath_root=dpath_root).validate()


def test_validate_no_doughnut_or_bagel(dpath_root: Path):
    create_empty_dataset(dpath_root)
    assert DatasetLayout(dpath_root=dpath_root).validate()


def test_dpath_descriptions():
    fpath_spec = DPATH_TEST_DATA / "layout1.json"
    layout = DatasetLayout(dpath_root="my_dataset", fpath_config=fpath_spec)
    assert layout.dpath_descriptions == [(Path("my_dataset/bids"), "BIDS data")]


@pytest.mark.parametrize(
    "paths_to_delete",
    [
        ["sourcedata", "downloads"],
        ["bids", "derivatives"],
        ["proc", "proc/global_config.json"],
        [
            "proc",
            "proc/containers",
            "proc/descriptors",
            "proc/invocations",
            "proc/scripts",
            "proc/global_config.json",
            "proc/pybids",
            "proc/pybids/bids_db",
            "proc/pybids/ignore_patterns",
        ],
        [
            "tabular",
            "tabular/manifest.csv",
            "tabular/assessments",
            "tabular/demographics",
        ],
    ],
)
def test_validate_error(dpath_root: Path, paths_to_delete: list[str]):
    create_invalid_dataset(dpath_root, paths_to_delete)
    layout = DatasetLayout(dpath_root=dpath_root)
    with pytest.raises(FileNotFoundError, match="Missing"):
        layout.validate()


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,expected",
    [
        ("my_pipeline", "v1", "derivatives/my_pipeline/v1"),
        ("pipeline", "v2", "derivatives/pipeline/v2"),
    ],
)
def test_get_dpath_pipeline(
    dpath_root: Path, pipeline_name, pipeline_version, expected
):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert (
        layout.get_dpath_pipeline(
            pipeline_name=pipeline_name, pipeline_version=pipeline_version
        )
        == dpath_root / expected
    )


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,participant_id,session_id,expected",
    [
        (
            "my_pipeline",
            "v1",
            None,
            None,
            "derivatives/my_pipeline/v1/work/my_pipeline-v1",
        ),
        (
            "pipeline",
            "v2",
            "3000",
            None,
            "derivatives/pipeline/v2/work/pipeline-v2-3000",
        ),
        (
            "pipeline",
            "v2",
            "01",
            "1",
            "derivatives/pipeline/v2/work/pipeline-v2-01-1",
        ),
    ],
)
def test_get_dpath_pipeline_work(
    dpath_root: Path,
    pipeline_name,
    pipeline_version,
    participant_id,
    session_id,
    expected,
):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert (
        layout.get_dpath_pipeline_work(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            participant_id=participant_id,
            session_id=session_id,
        )
        == dpath_root / expected
    )


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,expected",
    [
        ("my_pipeline", "v1", "derivatives/my_pipeline/v1/output"),
        ("pipeline", "v2", "derivatives/pipeline/v2/output"),
    ],
)
def test_get_dpath_pipeline_output(
    dpath_root: Path, pipeline_name, pipeline_version, expected
):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert (
        layout.get_dpath_pipeline_output(
            pipeline_name=pipeline_name, pipeline_version=pipeline_version
        )
        == dpath_root / expected
    )


@pytest.mark.parametrize(
    "pipeline_name,pipeline_version,participant_id,session_id,expected",
    [
        ("my_pipeline", "v1", None, None, "proc/pybids/bids_db/my_pipeline-v1"),
        ("pipeline", "v2", "01", "1", "proc/pybids/bids_db/pipeline-v2-01-1"),
    ],
)
def test_get_dpath_bids_db(
    dpath_root: Path,
    pipeline_name,
    pipeline_version,
    participant_id,
    session_id,
    expected,
):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert (
        layout.get_dpath_bids_db(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            participant_id=participant_id,
            session_id=session_id,
        )
        == dpath_root / expected
    )


def test_doughnut_parent_directory(dpath_root: Path):
    layout = DatasetLayout(dpath_root=dpath_root)
    assert layout.fpath_doughnut.parent == layout.dpath_raw_imaging
