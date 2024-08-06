"""Tests for the utils module."""

import json
import re
from contextlib import nullcontext
from pathlib import Path
from typing import Optional

import pandas as pd
import pytest
from fids import fids

from nipoppy.layout import DatasetLayout
from nipoppy.utils import (
    add_path_suffix,
    add_path_timestamp,
    add_pybids_ignore_patterns,
    apply_substitutions_to_json,
    check_participant_id,
    check_session_id,
    get_pipeline_tag,
    load_json,
    participant_id_to_bids_participant,
    process_template_str,
    save_df_with_backup,
    save_json,
    session_id_to_bids_session,
)

from .conftest import datetime_fixture  # noqa F401
from .conftest import DPATH_TEST_DATA


@pytest.mark.parametrize(
    "participant_id,expected", [("123", "sub-123"), ("sub01", "sub-sub01")]
)
def test_participant_id_to_bids_participant(participant_id, expected):
    assert participant_id_to_bids_participant(participant_id) == expected


@pytest.mark.parametrize(
    "session,expected",
    [("BL", "ses-BL"), ("M12", "ses-M12"), (None, None)],
)
def test_session_id_to_bids_session(session, expected):
    assert session_id_to_bids_session(session) == expected


@pytest.mark.parametrize(
    "participant_id,raise_error,is_valid,expected",
    [
        ("sub-01", False, True, "01"),
        ("01", False, True, "01"),
        (None, False, True, None),
        ("sub-01", True, False, None),
        ("01", True, True, "01"),
        (None, True, True, None),
    ],
)
def test_check_participant_id(participant_id, raise_error, is_valid, expected):
    with (
        pytest.raises(ValueError, match="Participant ID should not start with")
        if not is_valid
        else nullcontext()
    ):
        assert check_participant_id(participant_id, raise_error=raise_error) == expected


@pytest.mark.parametrize(
    "session_id,raise_error,is_valid,expected",
    [
        ("ses-BL", False, True, "BL"),
        ("M12", False, True, "M12"),
        (None, False, True, None),
        ("ses-1", True, False, None),
        ("1", True, True, "1"),
        (None, True, True, None),
    ],
)
def test_check_session_id(session_id, raise_error, is_valid, expected):
    with (
        pytest.raises(ValueError, match="Session ID should not start with")
        if not is_valid
        else nullcontext()
    ):
        assert check_session_id(session_id, raise_error=raise_error) == expected


@pytest.mark.parametrize(
    "dpath_bids_db,ignore_patterns,expected_count",
    [
        (None, None, 13),
        ("bids_db", [re.compile("^(?!/sub-(02))")], 9),
        ("bids_db", [re.compile(".*?/ses-(?!3)")], 3),
        ("bids_db", [re.compile("^(?!/sub-(01))"), re.compile(".*?/ses-(?!3)")], 0),
        ("bids_db", [re.compile(".*/anat/")], 3),
        ("bids_db", ["sub-01"], 9),
    ],
)
@pytest.mark.parametrize("resolve_paths", [True, False])
def test_create_bids_db(
    dpath_bids_db, ignore_patterns, expected_count, resolve_paths, tmp_path: Path
):
    from nipoppy.utils import create_bids_db

    dpath_bids = tmp_path / "bids"
    if dpath_bids_db is not None:
        dpath_bids_db: Path = tmp_path / dpath_bids_db

    fids.create_fake_bids_dataset(
        output_dir=dpath_bids, subjects=["01"], sessions=["1", "2"], datatypes=["anat"]
    )
    fids.create_fake_bids_dataset(
        output_dir=dpath_bids,
        subjects=["02"],
        sessions=["1", "2", "3"],
        datatypes=["anat", "func"],
    )

    bids_layout = create_bids_db(
        dpath_bids=dpath_bids,
        dpath_bids_db=dpath_bids_db,
        ignore_patterns=ignore_patterns,
        resolve_paths=resolve_paths,
    )
    assert len(bids_layout.get(extension="nii.gz")) == expected_count
    if dpath_bids_db is not None:
        assert dpath_bids_db.exists()


@pytest.mark.parametrize(
    "orig_patterns,new_patterns,expected",
    [
        ([], [], []),
        ([re.compile("a")], "b", [re.compile("a"), re.compile("b")]),
        ([re.compile("a")], ["b"], [re.compile("a"), re.compile("b")]),
        (
            [re.compile("a")],
            ["b", "c"],
            [re.compile("a"), re.compile("b"), re.compile("c")],
        ),
        ([re.compile("a")], "a", [re.compile("a")]),
        ([re.compile("a")], ["b"], [re.compile("a"), re.compile("b")]),
    ],
)
def test_add_pybids_ignore_patterns(orig_patterns, new_patterns, expected):
    add_pybids_ignore_patterns(current=orig_patterns, new=new_patterns)
    assert orig_patterns == expected


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
    with pytest.raises(json.JSONDecodeError, match="Error loading JSON file"):
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


@pytest.mark.parametrize("dname_backups", [None, ".tests"])
@pytest.mark.parametrize(
    "fname,dname_backups_processed",
    [("test.csv", ".tests"), ("test2.csv", ".test2s")],
)
def test_save_df_with_backup(
    fname: str,
    dname_backups: Optional[str],
    dname_backups_processed: str,
    tmp_path: Path,
):
    fpath_symlink = tmp_path / fname
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    fpath_backup = save_df_with_backup(df, fpath_symlink, dname_backups)

    if dname_backups is None:
        dname_backups = dname_backups_processed

    assert fpath_symlink.exists()
    assert fpath_backup.exists()
    assert fpath_backup.parent == fpath_symlink.parent / dname_backups


def test_save_df_with_backup_broken_symlink(tmp_path: Path):
    fpath_symlink = tmp_path / "test.csv"
    fpath_symlink.symlink_to("non_existent_file.csv")
    df = pd.DataFrame()

    # should not raise an error
    assert save_df_with_backup(df, fpath_symlink) is not None


@pytest.mark.parametrize(
    "template_str,resolve_paths,objs,kwargs,expected",
    [
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
    ],
)
def test_process_template_str(template_str, resolve_paths, objs, kwargs, expected):
    assert (
        process_template_str(
            template_str, resolve_paths=resolve_paths, objs=objs, **kwargs
        )
        == expected
    )


@pytest.mark.parametrize("template_str", ["[[NIPOPPY_123]]", "[[NIPOPPY_-]]"])
def test_process_template_str_error_identifier(template_str):
    with pytest.raises(ValueError, match="Invalid identifier name"):
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
    ],
)
def test_apply_substitutions_to_json(json_obj, substitutions, expected_output):
    assert apply_substitutions_to_json(json_obj, substitutions) == expected_output
