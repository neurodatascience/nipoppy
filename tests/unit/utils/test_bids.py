"""Tests for the utils.bids module."""

import re
from contextlib import nullcontext
from pathlib import Path

import pytest
from fids import fids

from nipoppy.exceptions import NipoppyError
from nipoppy.utils.bids import (
    add_pybids_ignore_patterns,
    check_participant_id,
    check_session_id,
    create_bids_db,
    participant_id_to_bids_participant_id,
    session_id_to_bids_session_id,
)


@pytest.mark.parametrize(
    "participant_id,expected", [("123", "sub-123"), ("sub01", "sub-sub01")]
)
def test_participant_id_to_bids_participant_id(participant_id, expected):
    assert participant_id_to_bids_participant_id(participant_id) == expected


@pytest.mark.parametrize(
    "session,expected",
    [("BL", "ses-BL"), ("M12", "ses-M12"), (None, None)],
)
def test_session_id_to_bids_session_id(session, expected):
    assert session_id_to_bids_session_id(session) == expected


@pytest.mark.parametrize(
    "participant_id,raise_error,is_valid,expected",
    [
        ("sub-01", False, True, "01"),
        ("01", False, True, "01"),
        (None, False, True, None),
        ("sub-01", True, False, None),
        ("01", True, True, "01"),
        (None, True, True, None),
        ("P-01", True, False, None),
        ("sub_01", False, False, None),
        ("", False, False, None),
        ("sub-", False, False, None),
    ],
)
def test_check_participant_id(participant_id, raise_error, is_valid, expected):
    with (
        pytest.raises(NipoppyError, match="Invalid participant ID")
        if not is_valid
        else nullcontext()
    ):
        output = check_participant_id(participant_id, raise_error=raise_error)
        if is_valid:
            assert output == expected


@pytest.mark.parametrize(
    "session_id,raise_error,is_valid,expected",
    [
        ("ses-BL", False, True, "BL"),
        ("M12", False, True, "M12"),
        (None, False, True, None),
        ("ses-1", True, False, None),
        ("1", True, True, "1"),
        (None, True, True, None),
        ("-01", True, False, None),
        ("1_", False, False, None),
        ("", False, False, None),
        ("ses-", False, False, None),
    ],
)
def test_check_session_id(session_id, raise_error, is_valid, expected):
    with (
        pytest.raises(NipoppyError, match="Invalid session ID")
        if not is_valid
        else nullcontext()
    ):
        output = check_session_id(session_id, raise_error=raise_error)
        if is_valid:
            assert output == expected


@pytest.mark.parametrize(
    "dpath_pybids_db,ignore_patterns,expected_count",
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
    dpath_pybids_db, ignore_patterns, expected_count, resolve_paths, tmp_path: Path
):
    dpath_bids = tmp_path / "bids"
    if dpath_pybids_db is not None:
        dpath_pybids_db: Path = tmp_path / dpath_pybids_db

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
        dpath_pybids_db=dpath_pybids_db,
        ignore_patterns=ignore_patterns,
        resolve_paths=resolve_paths,
    )
    assert len(bids_layout.get(extension="nii.gz")) == expected_count
    if dpath_pybids_db is not None:
        assert dpath_pybids_db.exists()


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
