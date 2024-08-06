"""Tests for the DoughnutWorkflow."""

from pathlib import Path

import pytest

from nipoppy.tabular.doughnut import Doughnut
from nipoppy.tabular.manifest import Manifest
from nipoppy.utils import save_json
from nipoppy.workflows.doughnut import DoughnutWorkflow

from .conftest import (
    ATTR_TO_DPATH_MAP,
    ATTR_TO_FPATH_MAP,
    check_doughnut,
    create_empty_dataset,
    get_config,
    prepare_dataset,
)


@pytest.mark.parametrize(
    (
        "participants_and_sessions_manifest1"
        ",participants_and_sessions_manifest2"
        ",participants_and_sessions_downloaded"
        ",participants_and_sessions_organized"
        ",participants_and_sessions_bidsified"
    ),
    [
        (
            {"01": ["BL", "M12"], "02": ["BL", "M12"]},
            {
                "01": ["BL", "M12"],
                "02": ["BL", "M12"],
                "03": ["BL", "M12"],
            },
            {"01": ["BL", "M12"], "02": ["BL"]},
            {"01": ["BL"], "02": ["BL"], "03": ["BL"]},
            {"01": ["BL", "M12"], "03": ["M12"]},
        ),
        (
            {"PD01": ["BL"], "PD02": ["BL"]},
            {"PD01": ["BL", "M12"], "PD02": ["BL", "M12"]},
            {"PD01": ["BL", "M12"], "PD02": ["BL", "M12"]},
            {"PD01": ["BL"], "PD02": ["BL", "M12"]},
            {"PD01": ["BL"], "PD02": ["BL"]},
        ),
    ],
)
@pytest.mark.parametrize("empty", [True, False])
def test_run(
    participants_and_sessions_manifest1: dict[str, list[str]],
    participants_and_sessions_manifest2: dict[str, list[str]],
    participants_and_sessions_downloaded: dict[str, list[str]],
    participants_and_sessions_organized: dict[str, list[str]],
    participants_and_sessions_bidsified: dict[str, list[str]],
    empty: bool,
    tmp_path: Path,
):
    dpath_root = tmp_path / "my_dataset"

    dpath_downloaded = dpath_root / ATTR_TO_DPATH_MAP["dpath_raw_imaging"]
    dpath_organized = dpath_root / ATTR_TO_DPATH_MAP["dpath_sourcedata"]
    dpath_bidsified = dpath_root / ATTR_TO_DPATH_MAP["dpath_bids"]
    fpath_manifest = dpath_root / ATTR_TO_FPATH_MAP["fpath_manifest"]
    fpath_config = dpath_root / ATTR_TO_FPATH_MAP["fpath_config"]
    fpath_doughnut = dpath_root / ATTR_TO_FPATH_MAP["fpath_doughnut"]

    create_empty_dataset(dpath_root)
    manifest1 = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions_manifest1,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
    )
    manifest1.save_with_backup(fpath_manifest)

    # prepare config file
    config = get_config(
        visit_ids=list(manifest1[Manifest.col_visit_id].unique()),
    )
    save_json(config.model_dump(mode="json"), fpath_config)

    # generate the doughnut
    DoughnutWorkflow(dpath_root=dpath_root, empty=empty).run()
    doughnut1 = Doughnut.load(fpath_doughnut)

    assert len(doughnut1) == len(manifest1)
    check_doughnut(
        doughnut=doughnut1,
        participants_and_sessions_manifest=participants_and_sessions_manifest1,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        empty=empty,
    )

    # update the manifest
    manifest2 = prepare_dataset(participants_and_sessions_manifest2)
    manifest2.save_with_backup(fpath_manifest)

    # update the doughnut
    DoughnutWorkflow(dpath_root=dpath_root, empty=empty).run()
    doughnut2 = Doughnut.load(fpath_doughnut)

    assert len(doughnut2) == len(manifest2)
    check_doughnut(
        doughnut=doughnut2,
        participants_and_sessions_manifest=participants_and_sessions_manifest2,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        empty=empty,
    )


@pytest.mark.parametrize(
    (
        "participants_and_sessions_manifest"
        ",participants_and_sessions_downloaded"
        ",participants_and_sessions_organized"
        ",participants_and_sessions_bidsified"
    ),
    [
        (
            {"01": ["BL", "M12"], "02": ["BL", "M12"]},
            {"01": ["BL", "M12"], "02": ["BL"]},
            {"01": ["BL"], "02": ["BL"], "03": ["BL"]},
            {"01": ["BL", "M12"], "03": ["M12"]},
        ),
        (
            {"PD01": ["BL", "M12"], "PD02": ["BL"]},
            {"PD01": ["BL", "M12"], "PD02": ["BL", "M12"]},
            {"PD01": ["BL"], "PD02": ["BL", "M12"]},
            {"PD01": ["BL"], "PD02": ["BL"]},
        ),
    ],
)
@pytest.mark.parametrize("empty", [True, False])
def test_run_regenerate(
    participants_and_sessions_manifest: dict[str, list[str]],
    participants_and_sessions_downloaded: dict[str, list[str]],
    participants_and_sessions_organized: dict[str, list[str]],
    participants_and_sessions_bidsified: dict[str, list[str]],
    empty: bool,
    tmp_path: Path,
):
    dpath_root = tmp_path / "my_dataset"
    create_empty_dataset(dpath_root)

    dpath_downloaded = dpath_root / ATTR_TO_DPATH_MAP["dpath_raw_imaging"]
    dpath_organized = dpath_root / ATTR_TO_DPATH_MAP["dpath_sourcedata"]
    dpath_bidsified = dpath_root / ATTR_TO_DPATH_MAP["dpath_bids"]
    fpath_manifest = dpath_root / ATTR_TO_FPATH_MAP["fpath_manifest"]
    fpath_config = dpath_root / ATTR_TO_FPATH_MAP["fpath_config"]
    fpath_doughnut = dpath_root / ATTR_TO_FPATH_MAP["fpath_doughnut"]

    manifest = prepare_dataset(
        participants_and_sessions_manifest=participants_and_sessions_manifest,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        dpath_downloaded=dpath_downloaded,
        dpath_organized=dpath_organized,
        dpath_bidsified=dpath_bidsified,
    )
    manifest.save_with_backup(fpath_manifest)

    # prepare config file
    config = get_config(
        visit_ids=list(manifest[Manifest.col_visit_id].unique()),
    )
    save_json(config.model_dump(mode="json"), fpath_config)

    # to be overwritten
    doughnut_records = []
    for _, manifest_record in manifest.iterrows():
        participant_id = manifest_record[Manifest.col_participant_id]
        doughnut_records.append(
            {
                Doughnut.col_participant_id: participant_id,
                Doughnut.col_visit_id: manifest_record[Manifest.col_visit_id],
                Doughnut.col_session_id: manifest_record[Manifest.col_session_id],
                Doughnut.col_datatype: manifest_record[Manifest.col_datatype],
                Doughnut.col_participant_dicom_dir: participant_id,
                Doughnut.col_in_raw_imaging: True,
                Doughnut.col_in_sourcedata: True,
                Doughnut.col_in_bids: True,
            }
        )
    doughnut_old = Doughnut(doughnut_records)
    assert doughnut_old.save_with_backup(fpath_doughnut) is not None

    # regenerate the doughnut
    DoughnutWorkflow(dpath_root=dpath_root, empty=empty, regenerate=True).run()
    doughnut = Doughnut.load(fpath_doughnut)

    assert len(doughnut) == len(manifest)
    check_doughnut(
        doughnut=doughnut,
        participants_and_sessions_manifest=participants_and_sessions_manifest,
        participants_and_sessions_downloaded=participants_and_sessions_downloaded,
        participants_and_sessions_organized=participants_and_sessions_organized,
        participants_and_sessions_bidsified=participants_and_sessions_bidsified,
        empty=empty,
    )
