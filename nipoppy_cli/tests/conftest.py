"""Utilities for tests."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pytest
import pytest_mock
from fids.fids import create_fake_bids_dataset

from nipoppy.config.main import Config
from nipoppy.tabular.doughnut import Doughnut
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import StrOrPathLike, strip_session

FPATH_CONFIG = "global_config.json"
FPATH_MANIFEST = "manifest.csv"
DPATH_TEST_DATA = Path(__file__).parent / "data"

ATTR_TO_DPATH_MAP = {
    "dpath_bids": "bids",
    "dpath_derivatives": "derivatives",
    "dpath_sourcedata": "sourcedata",
    "dpath_downloads": "downloads",
    "dpath_proc": "proc",
    "dpath_releases": "releases",
    "dpath_containers": "proc/containers",
    "dpath_descriptors": "proc/descriptors",
    "dpath_invocations": "proc/invocations",
    "dpath_tracker_configs": "proc/tracker_configs",
    "dpath_pybids": "proc/pybids",
    "dpath_bids_db": "proc/pybids/bids_db",
    "dpath_bids_ignore_patterns": "proc/pybids/ignore_patterns",
    "dpath_scratch": "scratch",
    "dpath_raw_dicom": "scratch/raw_dicom",
    "dpath_logs": "scratch/logs",
    "dpath_tabular": "tabular",
    "dpath_assessments": "tabular/assessments",
    "dpath_demographics": "tabular/demographics",
}

ATTR_TO_REQUIRED_FPATH_MAP = {
    "fpath_config": FPATH_CONFIG,
    "fpath_manifest": FPATH_MANIFEST,
}

ATTR_TO_FPATH_MAP = {
    **ATTR_TO_REQUIRED_FPATH_MAP,
    "fpath_doughnut": "scratch/raw_dicom/doughnut.csv",
    "fpath_imaging_bagel": "derivatives/bagel.csv",
}

MOCKED_DATETIME = datetime.datetime(2024, 4, 4, 12, 34, 56, 789000)


@pytest.fixture()
def datetime_fixture(
    mocker: pytest_mock.MockerFixture,
):
    """Mock the datetime module so that it produces predictable outputs.

    See https://stackoverflow.com/a/75591976 for mocking datetime.datetime.now
    """
    mocked_datetime = mocker.patch("nipoppy.utils.datetime")
    mocked_datetime.datetime.now.return_value = MOCKED_DATETIME
    yield mocked_datetime


def get_config(
    dataset_name="my_dataset",
    sessions=None,
    visits=None,
    bids_pipelines=None,
    proc_pipelines=None,
    container_config=None,
):
    """Create a valid Config object with all required parameters."""
    # everything empty by default
    if sessions is None:
        sessions = []
    if visits is None:
        visits = []
    if bids_pipelines is None:
        bids_pipelines = []
    if proc_pipelines is None:
        proc_pipelines = []
    if container_config is None:
        container_config = {}

    return Config(
        DATASET_NAME=dataset_name,
        VISITS=visits,
        SESSIONS=sessions,
        BIDS_PIPELINES=bids_pipelines,
        PROC_PIPELINES=proc_pipelines,
        CONTAINER_CONFIG=container_config,
    )


def create_empty_dataset(dpath_root: Path):
    """Create an empty dataset with all required directory and files."""
    for dpath in ATTR_TO_DPATH_MAP.values():
        (dpath_root / dpath).mkdir(parents=True, exist_ok=True)
    for fpath in ATTR_TO_REQUIRED_FPATH_MAP.values():
        (dpath_root / fpath).touch()


def _process_participants_sessions(
    participants_and_sessions: Optional[dict[str, list[str]]] = None,
    participants: Optional[list[str]] = None,
    sessions: Optional[list[str] | dict[str, list[str]]] = None,
):
    """Process participant/session arguments."""
    if participants_and_sessions is None:
        if participants is None:
            participants = ["01", "02"]
        if sessions is None:
            sessions = ["ses-BL", "ses-M12"]
        participants_and_sessions = {
            participant: sessions for participant in participants
        }
    return participants_and_sessions


def _fake_dicoms(
    dpath: StrOrPathLike,
    participants_and_sessions: Optional[dict[str, list[str]]] = None,
    participants: Optional[list[str]] = None,
    sessions: Optional[list[str]] = None,
    n_images: int = 3,
    min_n_files_per_image: int = 1,
    max_n_files_per_image: int = 5,
    min_n_subdir_levels: int = 1,
    max_n_subdir_levels: int = 2,
    participant_first: bool = True,
    max_dname_dicom: int = 1000000,
    rng_seed: int = 3791,
):
    """Generate a fake dataset with raw DICOM files."""
    participants_and_sessions = _process_participants_sessions(
        participants_and_sessions, participants, sessions
    )

    if n_images < 1:
        raise ValueError("n_images must be at least 1")
    if min_n_files_per_image < 1:
        raise ValueError("min_n_files_per_image must be at least 1")
    if max_n_files_per_image < min_n_files_per_image:
        raise ValueError("max_n_files_per_image must be at least min_n_files_per_image")
    if min_n_subdir_levels < 0:
        raise ValueError("min_n_subdir_levels must be at least 0")
    if max_n_subdir_levels < min_n_subdir_levels:
        raise ValueError("max_n_subdir_levels must be at least min_n_subdir_levels")

    rng = np.random.default_rng(rng_seed)

    dpath = Path(dpath)
    dpath.mkdir(parents=True, exist_ok=True)

    for participant, participant_sessions in participants_and_sessions.items():
        for session in participant_sessions:
            if participant_first:
                dpath_dicom_parent = dpath / participant / session
            else:
                dpath_dicom_parent = dpath / session / participant

            for i_image in range(n_images):
                n_subdir_levels = rng.integers(
                    min_n_subdir_levels, max_n_subdir_levels, endpoint=True
                )
                n_files = rng.integers(
                    min_n_files_per_image, max_n_files_per_image, endpoint=True
                )

                dpath_dicom = dpath_dicom_parent
                dnames_dicom = []
                for _ in range(n_subdir_levels):
                    dname_dicom = str(rng.integers(max_dname_dicom))
                    dpath_dicom = dpath_dicom / dname_dicom
                    dnames_dicom.append(dname_dicom)

                dpath_dicom.mkdir(parents=True, exist_ok=True)
                for i_file in range(n_files):
                    i_file_str = str(i_file).zfill(len(str(n_files)))
                    fpath_dicom = dpath_dicom / f"{i_image}-{i_file_str}.dcm"
                    fpath_dicom.touch()


def fake_dicoms_downloaded(
    dpath: StrOrPathLike,
    participants_and_sessions: Optional[dict[str, list[str]]] = None,
    participants: Optional[list[str]] = None,
    sessions: Optional[list[str]] = None,
    n_images: int = 3,
    min_n_files_per_image: int = 1,
    max_n_files_per_image: int = 5,
    min_n_subdir_levels: int = 1,
    max_n_subdir_levels: int = 2,
    participant_first: bool = True,
    max_dname_dicom: int = 1000000,
    rng_seed: int = 3791,
):
    """Create fake set of downloaded (unorganized) DICOM files."""
    _fake_dicoms(
        dpath=dpath,
        participants_and_sessions=participants_and_sessions,
        participants=participants,
        sessions=sessions,
        n_images=n_images,
        min_n_files_per_image=min_n_files_per_image,
        max_n_files_per_image=max_n_files_per_image,
        min_n_subdir_levels=min_n_subdir_levels,
        max_n_subdir_levels=max_n_subdir_levels,
        participant_first=participant_first,
        max_dname_dicom=max_dname_dicom,
        rng_seed=rng_seed,
    )


def fake_dicoms_organized(
    dpath: StrOrPathLike,
    participants_and_sessions: Optional[dict[str, list[str]]] = None,
    participants: Optional[list[str]] = None,
    sessions: Optional[list[str]] = None,
    n_images: int = 3,
    min_n_files_per_image: int = 1,
    max_n_files_per_image: int = 5,
    participant_first: bool = True,
    max_dname_dicom: int = 1000000,
    rng_seed: int = 3791,
):
    """Create fake set of organized DICOM files."""
    _fake_dicoms(
        dpath=dpath,
        participants_and_sessions=participants_and_sessions,
        participants=participants,
        sessions=sessions,
        n_images=n_images,
        min_n_files_per_image=min_n_files_per_image,
        max_n_files_per_image=max_n_files_per_image,
        min_n_subdir_levels=0,
        max_n_subdir_levels=0,
        participant_first=participant_first,
        max_dname_dicom=max_dname_dicom,
        rng_seed=rng_seed,
    )


def prepare_dataset(
    participants_and_sessions_manifest: dict[str, list[str]],
    participants_and_sessions_downloaded: Optional[dict[str, list[str]]] = None,
    participants_and_sessions_organized: Optional[dict[str, list[str]]] = None,
    participants_and_sessions_bidsified: Optional[dict[str, list[str]]] = None,
    dpath_downloaded: Optional[StrOrPathLike] = None,
    dpath_organized: Optional[StrOrPathLike] = None,
    dpath_bidsified: Optional[StrOrPathLike] = None,
):
    """Create dummy imaging files for testing the DICOM-to-BIDS conversion process."""
    # create the manifest
    data_manifest = []
    for participant in participants_and_sessions_manifest:
        for session in participants_and_sessions_manifest[participant]:
            data_manifest.append(
                {
                    Manifest.col_participant_id: participant,
                    Manifest.col_session: session,
                    Manifest.col_visit: session,
                    Manifest.col_datatype: [],
                }
            )
    manifest = Manifest(data_manifest)

    # create fake downloaded DICOMs
    if (
        participants_and_sessions_downloaded is not None
        and dpath_downloaded is not None
    ):
        fake_dicoms_downloaded(
            dpath_downloaded,
            participants_and_sessions_downloaded,
        )

    # create fake organized DICOMs
    if participants_and_sessions_organized is not None and dpath_organized is not None:
        fake_dicoms_organized(
            dpath_organized,
            participants_and_sessions_organized,
        )

    # create fake BIDS dataset
    if participants_and_sessions_bidsified is not None and dpath_bidsified is not None:
        for participant, sessions in participants_and_sessions_bidsified.items():
            create_fake_bids_dataset(
                Path(dpath_bidsified),
                subjects=participant,
                sessions=[strip_session(session) for session in sessions],
                datatypes=["anat"],
            )

    return manifest


def check_doughnut(
    doughnut: Doughnut,
    participants_and_sessions_manifest,
    participants_and_sessions_downloaded,
    participants_and_sessions_organized,
    participants_and_sessions_bidsified,
    empty,
):
    """Check that a doughnut has the corrected statuses."""
    if empty:
        for col in [
            doughnut.col_downloaded,
            doughnut.col_organized,
            doughnut.col_bidsified,
        ]:
            assert (~doughnut[col]).all()
    else:
        for participant in participants_and_sessions_manifest:
            for session in participants_and_sessions_manifest[participant]:
                for col, participants_and_sessions_true in {
                    doughnut.col_downloaded: participants_and_sessions_downloaded,
                    doughnut.col_organized: participants_and_sessions_organized,
                    doughnut.col_bidsified: participants_and_sessions_bidsified,
                }.items():
                    status: pd.Series = doughnut.loc[
                        (doughnut[doughnut.col_participant_id] == participant)
                        & (doughnut[doughnut.col_session] == session),
                        col,
                    ]

                    assert len(status) == 1
                    status = status.iloc[0]

                    assert status == (
                        participant in participants_and_sessions_true
                        and session in participants_and_sessions_true[participant]
                    )
