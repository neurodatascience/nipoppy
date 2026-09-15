"""Tests for the utils.utils module."""

import json
from pathlib import Path

import pandas as pd
import pytest

from nipoppy.exceptions import ConfigError, JSONError, NipoppyError
from nipoppy.layout import DatasetLayout
from nipoppy.utils.utils import (
    add_path_suffix,
    add_path_timestamp,
    apply_substitutions_to_json,
    get_pipeline_tag,
    is_nipoppy_project,
    load_json,
    process_template_str,
    save_df_with_backup,
    save_json,
)
from tests.conftest import (
    DPATH_TEST_DATA,
    create_empty_dataset,
    datetime_fixture,  # noqa F401
)


@pytest.mark.parametrize(
    "name,version,step,participant_id,session_id,expected",
    [
        ("my_pipeline", "1.0", None, None, None, "my_pipeline-1.0"),
        ("pipeline", "2.0", None, "3000", None, "pipeline-2.0-3000"),
        ("pipeline", "2.0", None, None, "BL", "pipeline-2.0-BL"),
        ("pipeline", "2.0", "step1", "3000", "BL", "pipeline-2.0-step1-3000-BL"),
    ],
)
def test_get_pipeline_tag(name, version, participant_id, step, session_id, expected):
    assert (
        get_pipeline_tag(
            pipeline_name=name,
            pipeline_version=version,
            pipeline_step=step,
            participant_id=participant_id,
            session_id=session_id,
        )
        == expected
    )


def test_load_json():
    assert isinstance(load_json(DPATH_TEST_DATA / "config1.json"), dict)


def test_load_json_invalid(tmp_path: Path):
    fpath_invalid = tmp_path / "invalid.json"
    fpath_invalid.write_text("invalid")
    with pytest.raises(JSONError):
        load_json(fpath_invalid)


def test_save_json(tmp_path: Path):
    json_object = {"a": 1, "b": 2}
    fpath = tmp_path / "test.json"
    save_json(json_object, fpath)
    assert fpath.exists()
    with fpath.open("r") as file:
        assert json.load(file) == json_object


@pytest.mark.parametrize(
    "path,suffix,sep,expected",
    [
        ("path/to/file.txt", "suffix", "-", Path("path/to/file-suffix.txt")),
        (Path("path/to/file.txt"), "suffix", "_", Path("path/to/file_suffix.txt")),
        (
            ".path/to/hidden/file.txt",
            "suffix",
            "-",
            Path(".path/to/hidden/file-suffix.txt"),
        ),
        (
            "file_without_extension",
            "suffix",
            "-",
            Path("file_without_extension-suffix"),
        ),
        (
            "archive.tar.gz",
            "backup",
            "-",
            Path("archive.tar-backup.gz"),
        ),
    ],
)
def test_add_path_suffix(path, suffix, sep, expected):
    assert add_path_suffix(path, suffix, sep) == expected


@pytest.mark.parametrize(
    "timestamp_format,expected",
    [
        ("%Y%m%d_%H%M", Path("/path/to/file-20240404_1234.txt")),
        ("%Y%m%d_%H%M_%S_%f", Path("/path/to/file-20240404_1234_56_789000.txt")),
    ],
)
def test_add_path_timestamp(timestamp_format, expected, datetime_fixture):  # noqa F811
    path = "/path/to/file.txt"
    assert add_path_timestamp(path=path, timestamp_format=timestamp_format) == expected


@pytest.mark.parametrize("use_relative_path", [True, False])
@pytest.mark.parametrize("dname_backups", [None, ".tests"])
@pytest.mark.parametrize(
    "fname,dname_backups_processed",
    [("test.tsv", ".tests"), ("curation_status.tsv", ".curation_statuses")],
)
def test_save_df_with_backup(
    fname: str,
    dname_backups: str | None,
    dname_backups_processed: str,
    use_relative_path: bool,
    tmp_path: Path,
):
    fpath_symlink = tmp_path / fname
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    fpath_backup = save_df_with_backup(
        df, fpath_symlink, dname_backups, use_relative_path
    )

    if dname_backups is None:
        dname_backups = dname_backups_processed

    assert fpath_symlink.exists()
    assert fpath_backup.exists()
    assert fpath_backup.parent == fpath_symlink.parent / dname_backups


def test_save_df_with_backup_broken_symlink(tmp_path: Path):
    fpath_symlink = tmp_path / "test.tsv"
    fpath_symlink.symlink_to("non_existent_file.tsv")
    df = pd.DataFrame()

    # should not raise an error
    assert save_df_with_backup(df, fpath_symlink) is not None


@pytest.mark.parametrize(
    "template_str,resolve_paths,objs,kwargs,expected",
    [
        ("", False, None, {}, ""),
        ("no_replace", False, None, {}, "no_replace"),
        (
            "[[NIPOPPY_DPATH_ROOT]]",
            False,
            [DatasetLayout("my_dataset")],
            {},
            "my_dataset",
        ),
        (
            "[[NIPOPPY_SOME_KWARG_PATH]]",
            False,
            [],
            {"some_kwarg_path": Path("a_path")},
            "a_path",
        ),
        (
            "[[NIPOPPY_SOME_KWARG_PATH]]",
            True,
            [],
            {"some_kwarg_path": Path("a_path")},
            str(Path("a_path").resolve()),
        ),
        (
            "[[NIPOPPY_DPATH_ROOT]]/sub/[[NIPOPPY_DPATH_ROOT]]",
            False,
            [DatasetLayout("my_dataset")],
            {},
            "my_dataset/sub/my_dataset",
        ),
    ],
)
def test_process_template_str(template_str, resolve_paths, objs, kwargs, expected):
    assert (
        process_template_str(
            template_str, resolve_paths=resolve_paths, objs=objs, **kwargs
        )
        == expected
    )


def test_process_template_str_warning():
    with pytest.warns(UserWarning, match="Replacing .* with None"):
        assert process_template_str("[[NIPOPPY_KWARG1]]", kwarg1=None) == "None"


@pytest.mark.parametrize("template_str", ["[[NIPOPPY_123]]", "[[NIPOPPY_-]]"])
def test_process_template_str_error_identifier(template_str):
    with pytest.raises(NipoppyError, match="Invalid identifier name"):
        process_template_str(template_str)


def test_process_template_str_error_replace():
    with pytest.warns(UserWarning, match="Unable to replace"):
        assert process_template_str("[[NIPOPPY_INVALID]]") == "[[NIPOPPY_INVALID]]"


@pytest.mark.parametrize(
    "json_obj,substitutions,expected_output",
    [
        ({"key1": "TO_REPLACE"}, {"TO_REPLACE": "value1"}, {"key1": "value1"}),
        ({"key1": ["TO_REPLACE"]}, {"TO_REPLACE": "value1"}, {"key1": ["value1"]}),
        ([{"key1": "TO_REPLACE"}], {"TO_REPLACE": "value1"}, [{"key1": "value1"}]),
        ({"key1": "value1"}, {}, {"key1": "value1"}),
        (
            {"key1": "A_B_A"},
            {"A": "X"},
            {"key1": "X_B_X"},
        ),
    ],
)
def test_apply_substitutions_to_json(json_obj, substitutions, expected_output):
    assert apply_substitutions_to_json(json_obj, substitutions) == expected_output


def test_apply_substitutions_to_json_invalid_value():
    with pytest.raises(ConfigError, match="Substitution value must be a string"):
        apply_substitutions_to_json({"key1": "TO_REPLACE"}, {"TO_REPLACE": None})


@pytest.mark.parametrize(
    "current_path, is_inside_project",
    [
        ("bids", True),
        (".", True),
        ("..", False),
    ],
)
def test_is_nipoppy_project(
    tmp_path: Path, current_path: Path, is_inside_project: bool
):
    """Test if the current path is a nipoppy project."""
    dataset_path = tmp_path / "dataset"
    create_empty_dataset(dataset_path)

    cwd_path = dataset_path / current_path
    if is_inside_project:
        assert is_nipoppy_project(cwd_path) == Path(dataset_path)
    else:
        assert is_nipoppy_project(cwd_path) is False
