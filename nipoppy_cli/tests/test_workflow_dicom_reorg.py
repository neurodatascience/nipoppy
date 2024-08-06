"""Tests for DicomReorgWorkflow."""

import logging
import shutil
from pathlib import Path

import pytest

from nipoppy.tabular.dicom_dir_map import DicomDirMap
from nipoppy.tabular.doughnut import Doughnut
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import participant_id_to_bids_participant, session_id_to_bids_session
from nipoppy.workflows.dicom_reorg import DicomReorgWorkflow, is_derived_dicom

from .conftest import DPATH_TEST_DATA, create_empty_dataset, get_config, prepare_dataset


@pytest.mark.parametrize(
    "fpath,expected_result",
    [
        (DPATH_TEST_DATA / "dicom-not_derived.dcm", False),
        (DPATH_TEST_DATA / "dicom-derived.dcm", True),
    ],
)
def test_is_derived_dicom(fpath, expected_result):
    assert is_derived_dicom(fpath) == expected_result


@pytest.mark.parametrize(
    "participant_id,session_id,fpaths,participant_first",
    [
        ("01", "1", ["01/1/file1.dcm", "01/1/file2.dcm"], True),
        (
            "02",
            "2",
            ["2/02/001.dcm", "2/02/002.dcm", "2/02/003.dcm"],
            False,
        ),
    ],
)
def test_get_fpaths_to_reorg(
    participant_id, session_id, fpaths, participant_first, tmp_path: Path
):
    dpath_root = tmp_path / "my_dataset"

    manifest = prepare_dataset(
        participants_and_sessions_manifest={participant_id: [session_id]}
    )

    workflow = DicomReorgWorkflow(dpath_root=dpath_root)
    workflow.dicom_dir_map = DicomDirMap.load_or_generate(
        manifest=manifest, fpath_dicom_dir_map=None, participant_first=participant_first
    )
    for fpath in fpaths:
        fpath_full: Path = workflow.layout.dpath_raw_imaging / fpath
        fpath_full.parent.mkdir(parents=True, exist_ok=True)
        fpath_full.touch()

    assert len(
        workflow.get_fpaths_to_reorg(
            participant_id=participant_id,
            session_id=session_id,
        )
    ) == len(fpaths)


def test_get_fpaths_to_reorg_error_not_found(tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    participant_id = "XXX"
    session_id = "X"

    workflow = DicomReorgWorkflow(dpath_root=dpath_root)
    manifest = prepare_dataset(
        participants_and_sessions_manifest={participant_id: [session_id]}
    )
    workflow.dicom_dir_map = DicomDirMap.load_or_generate(
        manifest=manifest, fpath_dicom_dir_map=None, participant_first=True
    )

    with pytest.raises(FileNotFoundError, match="Raw DICOM directory not found"):
        workflow.get_fpaths_to_reorg("XXX", "X")


@pytest.mark.parametrize(
    "mapping_func,expected",
    [
        (lambda fname, participant_id, session_id: fname, "123456.dcm"),
        (lambda fname, participant_id, session_id: "dicoms.tar.gz", "dicoms.tar.gz"),
        (
            lambda fname, participant_id, session_id: (
                f"{participant_id}-{session_id}.tar.gz"
            ),
            "01-1.tar.gz",
        ),
    ],
)
def test_apply_fname_mapping(mapping_func, expected, tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=dpath_root)
    workflow.apply_fname_mapping = mapping_func

    fname = "123456.dcm"
    participant_id = "01"
    session_id = "1"
    assert workflow.apply_fname_mapping(fname, participant_id, session_id) == expected


@pytest.mark.parametrize(
    "fname_source,expected",
    [
        ("123456.dcm", "123456.dcm"),
        (Path("123456.dcm"), Path("123456.dcm")),
        ("dicoms.tar.gz", "dicoms.tar.gz"),
    ],
)
def test_apply_fname_mapping_default(fname_source, expected, tmp_path: Path):
    dpath_root = tmp_path / "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=dpath_root)

    assert (
        workflow.apply_fname_mapping(
            fname_source=fname_source, participant_id="", session_id=""
        )
        == expected
    )


def test_run_single_error_file_exists(tmp_path: Path):
    participant_id = "01"
    session_id = "1"
    dataset_name = "my_dataset"

    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name)

    manifest = prepare_dataset(
        participants_and_sessions_manifest={participant_id: [session_id]}
    )
    workflow.dicom_dir_map = DicomDirMap.load_or_generate(
        manifest=manifest, fpath_dicom_dir_map=None, participant_first=True
    )

    # create the same file in both the downloaded and organized directories
    fname = "test.dcm"
    for fpath in [
        workflow.layout.dpath_raw_imaging / participant_id / session_id / fname,
        workflow.layout.dpath_sourcedata
        / participant_id_to_bids_participant(participant_id)
        / session_id_to_bids_session(session_id)
        / fname,
    ]:
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.touch()

    with pytest.raises(FileExistsError, match="Cannot move file"):
        workflow.run_single(participant_id, session_id)


def test_run_single_invalid_dicom(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    participant_id = "01"
    session_id = "1"
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name, check_dicoms=True)

    manifest = prepare_dataset(
        participants_and_sessions_manifest={participant_id: [session_id]}
    )
    workflow.dicom_dir_map = DicomDirMap.load_or_generate(
        manifest=manifest, fpath_dicom_dir_map=None, participant_first=True
    )

    # use derived DICOM file
    fpath_dicom = (
        workflow.layout.dpath_raw_imaging / participant_id / session_id / "test.dcm"
    )
    fpath_dicom.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DPATH_TEST_DATA / "dicom-derived.dcm", fpath_dicom)

    try:
        workflow.run_single(participant_id, session_id)
    except Exception:
        pass

    assert any(
        [
            "Derived DICOM file detected" in record.message
            and record.levelno == logging.WARNING
            for record in caplog.records
        ]
    )


def test_run_single_error_dicom_read(tmp_path: Path):
    participant_id = "01"
    session_id = "1"
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name, check_dicoms=True)

    manifest = prepare_dataset(
        participants_and_sessions_manifest={participant_id: [session_id]}
    )
    workflow.dicom_dir_map = DicomDirMap.load_or_generate(
        manifest=manifest, fpath_dicom_dir_map=None, participant_first=True
    )

    # create an invalid DICOM file
    fname = "test.dcm"
    fpath = workflow.layout.dpath_raw_imaging / participant_id / session_id / fname
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.touch()

    with pytest.raises(RuntimeError, match="Error checking DICOM file"):
        workflow.run_single(participant_id, session_id)


def test_copy_files_default(tmp_path: Path):
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name)
    assert workflow.copy_files is False


def test_check_dicoms_default(tmp_path: Path):
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name)
    assert workflow.check_dicoms is False


@pytest.mark.parametrize(
    (
        "participants_and_sessions_downloaded"
        ",participants_and_sessions_organized"
        ",expected"
    ),
    [
        (
            {
                "S01": ["1", "2", "3"],
                "S02": ["1", "2"],
                "S03": ["3"],
            },
            {
                "S03": ["3"],
            },
            [
                ("S01", "1"),
                ("S01", "2"),
                ("S01", "3"),
                ("S02", "1"),
                ("S02", "2"),
            ],
        ),
        (
            {
                "S01": ["1", "2", "3"],
                "S02": ["1", "2", "3"],
                "S03": ["1", "2", "3"],
            },
            {
                "S01": ["1", "3"],
            },
            [
                ("S01", "2"),
                ("S02", "1"),
                ("S02", "2"),
                ("S02", "3"),
                ("S03", "1"),
                ("S03", "2"),
                ("S03", "3"),
            ],
        ),
    ],
)
def test_get_participants_sessions_to_run(
    participants_and_sessions_downloaded,
    participants_and_sessions_organized,
    expected,
    tmp_path: Path,
):
    participants_and_sessions_manifest = {
        "S01": ["1", "2", "3"],
        "S02": ["1", "2", "3"],
        "S03": ["1", "2", "3"],
    }
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name)
    create_empty_dataset(workflow.layout.dpath_root)

    manifest: Manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions_manifest,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        dpath_downloaded=workflow.layout.dpath_raw_imaging,
        dpath_organized=workflow.layout.dpath_sourcedata,
    )

    config = get_config(
        dataset_name=dataset_name,
        visit_ids=list(manifest[Manifest.col_visit_id].unique()),
    )

    manifest.save_with_backup(workflow.layout.fpath_manifest)
    config.save(workflow.layout.fpath_config)

    assert [tuple(x) for x in workflow.get_participants_sessions_to_run()] == expected


def test_run_setup(tmp_path: Path):
    dataset_name = "my_dataset"
    participants_and_sessions1 = {"01": ["1"]}
    participants_and_sessions2 = {"01": ["1", "2"], "02": ["1"]}
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name)

    create_empty_dataset(workflow.layout.dpath_root)

    manifest1 = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions1,
    )
    manifest1.save_with_backup(workflow.layout.fpath_manifest)

    config = get_config(
        dataset_name=dataset_name,
        visit_ids=list(manifest1[Manifest.col_visit_id].unique()),
    )
    config.save(workflow.layout.fpath_config)

    # generate first doughnut with the smaller manifest
    doughnut1 = DicomReorgWorkflow(dpath_root=tmp_path / dataset_name).doughnut

    # update manifest
    manifest2 = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions2,
    )
    manifest2.save_with_backup(workflow.layout.fpath_manifest)
    workflow.manifest = manifest2

    # check that doughnut was regenerated
    workflow.run_setup()

    assert not workflow.doughnut.equals(doughnut1)
    assert len(workflow.doughnut) == len(manifest2)


@pytest.mark.parametrize(
    "participants_and_sessions_manifest,participants_and_sessions_downloaded",
    [
        (
            {
                "S01": ["1", "2", "3"],
                "S02": ["1", "2", "3"],
                "S03": ["1", "2", "3"],
            },
            {
                "S01": ["1", "2", "3"],
                "S02": ["1", "2"],
                "S03": ["3"],
            },
        ),
        (
            {
                "P01": ["BL"],
                "P02": ["V01"],
                "P03": ["V03"],
            },
            {
                "P01": ["BL"],
                "P02": ["BL", "V01"],
                "P03": ["BL", "V03"],
            },
        ),
    ],
)
@pytest.mark.parametrize("copy_files", [True, False])
def test_run_main(
    participants_and_sessions_manifest: dict,
    participants_and_sessions_downloaded: dict,
    copy_files: bool,
    tmp_path: Path,
):
    dataset_name = "my_dataset"
    workflow = DicomReorgWorkflow(
        dpath_root=tmp_path / dataset_name, copy_files=copy_files
    )

    manifest: Manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions_manifest,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        dpath_downloaded=workflow.layout.dpath_raw_imaging,
    )

    config = get_config(
        dataset_name=dataset_name,
        visit_ids=list(manifest[Manifest.col_visit_id].unique()),
    )

    manifest.save_with_backup(workflow.layout.fpath_manifest)
    config.save(workflow.layout.fpath_config)

    workflow.run_main()

    for participant_id, session_ids in participants_and_sessions_manifest.items():
        for session_id in session_ids:
            dpath_to_check: Path = (
                workflow.layout.dpath_sourcedata
                / participant_id_to_bids_participant(participant_id)
                / session_id_to_bids_session(session_id)
            )

            if (
                participant_id in participants_and_sessions_downloaded
                and session_id in participants_and_sessions_downloaded[participant_id]
            ):
                # check that directory exists
                assert dpath_to_check.exists()

                # make sure it is not empty
                # and that symlinks are created if requested
                count = 0
                for fpath in dpath_to_check.iterdir():
                    if copy_files:
                        assert not fpath.is_symlink()
                    else:
                        assert fpath.is_symlink()
                    count += 1
                assert count > 0

                # check that the doughnut has been updated
                assert workflow.doughnut.get_status(
                    participant_id=participant_id,
                    session_id=session_id,
                    col=workflow.doughnut.col_in_sourcedata,
                )

            else:
                assert not dpath_to_check.exists()


@pytest.mark.parametrize(
    "doughnut",
    [
        Doughnut(),
        Doughnut(
            data={
                Doughnut.col_participant_id: ["01"],
                Doughnut.col_visit_id: ["1"],
                Doughnut.col_session_id: ["1"],
                Doughnut.col_datatype: "['anat']",
                Doughnut.col_participant_dicom_dir: ["01"],
                Doughnut.col_in_raw_imaging: [True],
                Doughnut.col_in_sourcedata: [True],
                Doughnut.col_in_bids: [True],
            }
        ).validate(),
    ],
)
def test_cleanup(doughnut: Doughnut, tmp_path: Path):
    workflow = DicomReorgWorkflow(dpath_root=tmp_path / "my_dataset")
    workflow.doughnut = doughnut

    workflow.run_cleanup()

    assert workflow.layout.fpath_doughnut.exists()
    assert Doughnut.load(workflow.layout.fpath_doughnut).equals(doughnut)
