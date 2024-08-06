from __future__ import annotations

import logging
from pathlib import Path

import pytest

import nipoppy.workflow.logger as my_logger
from nipoppy.workflow.proc_pipe.mriqc.run_mriqc import run

from .conftest import global_config_for_testing


@pytest.mark.parametrize("logger", ["mriqc.log", None])
@pytest.mark.parametrize("output_dir", ["tmp_path", None])
@pytest.mark.parametrize("modalities", [["anat"], ["anat", "func"]])
def test_run(caplog, tmp_path, output_dir, modalities, logger):
    """Check that the proper command is generated."""
    caplog.set_level(logging.CRITICAL)

    participant_id = "01"

    session_id = "01"

    if logger is not None:
        log_file = tmp_path / logger
        logger = my_logger.get_logger(log_file)
    else:
        (tmp_path / "scratch" / "logs").mkdir(parents=True, exist_ok=True)

    global_configs = global_config_for_testing(tmp_path)
    if output_dir == "tmp_path":
        output_dir = tmp_path
        expected_output_dir = output_dir
    if output_dir is None:
        expected_output_dir = Path(global_configs["DATASET_ROOT"]) / "derivatives"

    cmd = run(
        participant_id=participant_id,
        global_configs=global_config_for_testing(tmp_path),
        session_id=session_id,
        output_dir=output_dir,
        modalities=modalities,
        logger=logger,
    )

    # fmt: off
    expected_cmd = ['singularity', 'run',
                        '-B', f'{str(tmp_path)}/bids/:{str(tmp_path)}/bids/:ro',
                        '-B', f'{str(tmp_path)}/proc/:/mriqc_proc',
                        '-B', f'{str(expected_output_dir)}/mriqc/23.1.0/output/:/out',
                        '-B', f'{str(expected_output_dir)}/mriqc/23.1.0/work/:/work',
                        '-B', ':/templateflow',
                        '--cleanenv',
                            'mriqc_23.1.0.sif', f'{str(tmp_path)}/bids/', '/out', 'participant',
                                '--participant-label', participant_id,
                                '--session-id', session_id,
                                '--modalities']
    expected_cmd.extend(modalities)
    expected_cmd.extend(['--no-sub',
                         '--work-dir', '/work',
                         '--bids-database-dir', '/mriqc_proc/bids_db_mriqc'])
    # fmt: on

    assert cmd == expected_cmd


def test_logger_error(tmp_path, caplog):
    """Check that a logging error is raised."""
    participant_id = "01"
    session_id = "01"
    output_dir = tmp_path
    modalities = ["anat", "func"]
    log_file = tmp_path / "mriqc.log"
    logger = my_logger.get_logger(log_file)

    caplog.set_level(logging.ERROR)

    run(
        participant_id=participant_id,
        global_configs=global_config_for_testing(tmp_path),
        session_id=session_id,
        output_dir=output_dir,
        modalities=modalities,
        logger=logger,
    )

    for record in caplog.records:
        if record.levelname == "ERROR":
            assert "mriqc run failed" in caplog.text
