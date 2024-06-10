"""Tests for the manifest."""

from contextlib import nullcontext
from pathlib import Path

import pytest

from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.doughnut import Doughnut, generate_doughnut, update_doughnut
from nipoppy.utils import StrOrPathLike

from .conftest import DPATH_TEST_DATA, check_doughnut, prepare_dataset


@pytest.fixture
def data():
    return {
        Doughnut.col_participant_id: ["01", "01", "02", "02"],
        Doughnut.col_visit: ["BL", "M12", "BL", "M12"],
        Doughnut.col_session: ["ses-BL", "ses-M12", "ses-BL", "ses-M12"],
        Doughnut.col_datatype: ["anat", "anat", "anat", "anat"],
        Doughnut.col_participant_dicom_dir: ["01", "01", "02", "02"],
        Doughnut.col_dicom_id: ["01", "01", "02", "02"],
        Doughnut.col_bids_id: ["01", "01", "02", "02"],
        Doughnut.col_downloaded: [True, True, True, False],
        Doughnut.col_organized: [True, False, True, False],
        Doughnut.col_bidsified: [True, False, False, False],
    }


@pytest.mark.parametrize(
    "fpath",
    [
        DPATH_TEST_DATA / "doughnut1.csv",
        DPATH_TEST_DATA / "doughnut2.csv",
    ],
)
@pytest.mark.parametrize("validate", [True, False])
def test_load(fpath, validate):
    assert isinstance(Doughnut.load(fpath, validate=validate), Doughnut)


@pytest.mark.parametrize(
    "fpath,is_valid",
    [
        (DPATH_TEST_DATA / "doughnut1.csv", True),
        (DPATH_TEST_DATA / "doughnut2.csv", True),
        (DPATH_TEST_DATA / "doughnut_invalid1.csv", False),
        (DPATH_TEST_DATA / "doughnut_invalid2.csv", False),
    ],
)
def test_validate(fpath, is_valid):
    df_doughnut = Doughnut.load(fpath, validate=False)
    with pytest.raises(ValueError) if not is_valid else nullcontext():
        assert isinstance(Doughnut.validate(df_doughnut), Doughnut)


@pytest.mark.parametrize(
    "col", [Doughnut.col_downloaded, Doughnut.col_organized, Doughnut.col_bidsified]
)
def test_check_status_col(col):
    assert Doughnut._check_status_col(col) == col


def test_check_status_col_invalid():
    with pytest.raises(ValueError, match="Invalid status column"):
        Doughnut._check_status_col("invalid_col")


@pytest.mark.parametrize("value", [True, False])
def test_check_status_value(value):
    assert Doughnut._check_status_value(value) == value


def test_check_status_value_invalid():
    with pytest.raises(ValueError, match="Invalid status value"):
        assert Doughnut._check_status_value("123")


@pytest.mark.parametrize(
    "participant,session,col,expected_status",
    [
        ("01", "ses-BL", Doughnut.col_downloaded, True),
        ("01", "ses-BL", Doughnut.col_organized, True),
        ("01", "ses-BL", Doughnut.col_bidsified, True),
        ("02", "ses-M12", Doughnut.col_downloaded, False),
        ("02", "ses-M12", Doughnut.col_organized, False),
        ("02", "ses-M12", Doughnut.col_bidsified, False),
    ],
)
def test_get_status(data, participant, session, col, expected_status):
    assert Doughnut(data).get_status(participant, session, col) == expected_status


@pytest.mark.parametrize(
    "participant,session,col,status",
    [
        ("01", "ses-BL", Doughnut.col_downloaded, False),
        ("01", "ses-BL", Doughnut.col_organized, False),
        ("01", "ses-BL", Doughnut.col_bidsified, False),
        ("02", "ses-M12", Doughnut.col_downloaded, True),
        ("02", "ses-M12", Doughnut.col_organized, True),
        ("02", "ses-M12", Doughnut.col_bidsified, True),
    ],
)
def test_set_status(data, participant, session, col, status):
    doughnut = Doughnut(data)
    doughnut.set_status(participant, session, col, status)
    assert doughnut.get_status(participant, session, col) == status


@pytest.mark.parametrize(
    "status_col,participant,session,expected_count",
    [
        ("downloaded", None, None, 3),
        ("organized", None, None, 2),
        ("bidsified", None, None, 1),
        ("downloaded", "01", None, 2),
        ("organized", None, "ses-M12", 0),
        ("bidsified", "01", "ses-BL", 1),
    ],
)
def test_get_participant_sessions_helper(
    data, status_col, participant, session, expected_count
):
    doughnut = Doughnut(data)
    count = 0
    for _ in doughnut._get_participant_sessions_helper(
        status_col=status_col, participant=participant, session=session
    ):
        count += 1
    assert count == expected_count


@pytest.mark.parametrize(
    (
        "participants_and_sessions_manifest1"
        ",participants_and_sessions_manifest2"
        ",participants_and_sessions_downloaded"
        ",participants_and_sessions_organized"
        ",participants_and_sessions_bidsified"
        ",dpath_downloaded_relative"
        ",dpath_organized_relative"
        ",dpath_bidsified_relative"
    ),
    [
        (
            {"01": ["ses-BL", "ses-M12"], "02": ["ses-BL", "ses-M12"]},
            {
                "01": ["ses-BL", "ses-M12"],
                "02": ["ses-BL", "ses-M12"],
                "03": ["ses-BL", "ses-M12"],
            },
            {"01": ["ses-BL", "ses-M12"], "02": ["ses-BL"]},
            {"01": ["ses-BL"], "02": ["ses-BL"], "03": ["ses-BL"]},
            {"01": ["ses-BL", "ses-M12"], "03": ["ses-M12"]},
            "downloaded",
            "organized",
            "bidsified",
        ),
        (
            {"PD01": ["ses-BL"], "PD02": ["ses-BL"]},
            {"PD01": ["ses-BL", "ses-M12"], "PD02": ["ses-BL", "ses-M12"]},
            {"PD01": ["ses-BL", "ses-M12"], "PD02": ["ses-BL", "ses-M12"]},
            {"PD01": ["ses-BL"], "PD02": ["ses-BL", "ses-M12"]},
            {"PD01": ["ses-BL"], "PD02": ["ses-BL"]},
            Path("scratch", "raw_dicom"),
            Path("dicom"),
            Path("bids"),
        ),
    ],
)
@pytest.mark.parametrize("empty", [True, False])
@pytest.mark.parametrize("str_paths", [False, True])
def test_generate_and_update(
    participants_and_sessions_manifest1: dict[str, list[str]],
    participants_and_sessions_manifest2: dict[str, list[str]],
    participants_and_sessions_downloaded: dict[str, list[str]],
    participants_and_sessions_organized: dict[str, list[str]],
    participants_and_sessions_bidsified: dict[str, list[str]],
    dpath_downloaded_relative: StrOrPathLike,
    dpath_organized_relative: StrOrPathLike,
    dpath_bidsified_relative: StrOrPathLike,
    empty: bool,
    str_paths: bool,
    tmp_path: Path,
):
    dpath_root = tmp_path / "my_dataset"
    dpath_downloaded = dpath_root / dpath_downloaded_relative
    dpath_organized = dpath_root / dpath_organized_relative
    dpath_bidsified = dpath_root / dpath_bidsified_relative

    if str_paths:
        dpath_downloaded = str(dpath_downloaded)
        dpath_organized = str(dpath_organized)
        dpath_bidsified = str(dpath_bidsified)

    # create the manifest
    manifest1 = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions_manifest1,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
    )

    # generate the doughnut
    doughnut1 = generate_doughnut(
        manifest=manifest1,
        dicom_dir_map=DicomDirMap.load_or_generate(
            manifest=manifest1, fpath_dicom_dir_map=None, participant_first=True
        ),
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
        empty=empty,
    )
    # the doughnut should have the same number of records as the manifest
    assert len(doughnut1) == len(manifest1)

    check_doughnut(
        doughnut=doughnut1,
        participants_and_sessions_manifest=participants_and_sessions_manifest1,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        empty=empty,
    )

    # create a new manifest
    manifest2 = prepare_dataset(participants_and_sessions_manifest2)
    doughnut2 = update_doughnut(
        doughnut=doughnut1,
        manifest=manifest2,
        dicom_dir_map=DicomDirMap.load_or_generate(
            manifest=manifest2, fpath_dicom_dir_map=None, participant_first=True
        ),
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
        empty=empty,
    )
    assert len(doughnut2) == len(manifest2)

    check_doughnut(
        doughnut=doughnut2,
        participants_and_sessions_manifest=participants_and_sessions_manifest2,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        empty=empty,
    )


def test_generate_missing_paths(tmp_path: Path):
    participants_and_sessions = {
        "01": ["ses-BL", "ses-M12"],
        "02": ["ses-BL", "ses-M12"],
    }

    dpath_root = tmp_path / "my_dataset"
    dpath_downloaded = dpath_root / "downloaded"
    dpath_organized = None
    dpath_bidsified = dpath_root / "bids"

    manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions,
        participants_and_sessions_downloaded=participants_and_sessions,
        participants_and_sessions_organized=participants_and_sessions,
        participants_and_sessions_bidsified=participants_and_sessions,
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
    )

    doughnut = generate_doughnut(
        manifest=manifest,
        dicom_dir_map=DicomDirMap.load_or_generate(
            manifest=manifest, fpath_dicom_dir_map=None, participant_first=True
        ),
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
        empty=False,
    )

    assert doughnut[Doughnut.col_downloaded].all()
    assert (~doughnut[Doughnut.col_organized]).all()
    assert doughnut[Doughnut.col_bidsified].all()
