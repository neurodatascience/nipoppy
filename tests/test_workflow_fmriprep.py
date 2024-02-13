from __future__ import annotations

import json
from pathlib import Path

import pytest
from .conftest import global_configs_for_testing

import nipoppy.workflow.logger as my_logger
import nipoppy.workflow.proc_pipe.fmriprep.run_fmriprep as fmriprep_module
from nipoppy.workflow.proc_pipe.fmriprep.run_fmriprep import run, run_fmriprep


def create_dummy_fs_license(pth: Path) -> None:
    pth = pth / "freesurfer"
    pth.mkdir(parents=True, exist_ok=True)
    license_file = pth / "license.txt"
    license_file.write_text("dummy content")


def dummy_bids_filter_file() -> Path:
    """TODO probably don't want the bids filter file to be in the module directory"""
    pth = Path(fmriprep_module.__file__).parent
    return pth / "bids_filter.json"


def create_dummy_bids_filter() -> None:
    with open(dummy_bids_filter_file(), "w") as f:
        json.dump({"dummy": "dummy"}, f)


def delete_dummy_bids_filter() -> None:
    dummy_bids_filter_file().unlink(missing_ok=True)


@pytest.mark.parametrize("use_bids_filter", [True, False])
@pytest.mark.parametrize("anat_only", [True, False])
def test_run(tmp_path, use_bids_filter, anat_only):
    create_dummy_fs_license(tmp_path)

    # TODO because this is set up and torn down after each test
    # we probably want to turn this into fixture
    create_dummy_bids_filter()

    participant_id = "01"

    session_id = "01"

    log_file = tmp_path / "fmriprep.log"
    logger = my_logger.get_logger(log_file)

    run(
        participant_id=participant_id,
        global_configs=global_configs_for_testing(tmp_path),
        session_id=session_id,
        output_dir=tmp_path,
        use_bids_filter=use_bids_filter,
        anat_only=anat_only,
        logger=logger,
    )

    delete_dummy_bids_filter()


@pytest.mark.parametrize("use_bids_filter", [True, False])
@pytest.mark.parametrize("anat_only", [True, False])
def test_run_fmriprep(tmp_path, use_bids_filter, anat_only):
    log_file = tmp_path / "fmriprep.log"

    bids_dir = "bids_dir"
    proc_dir = "fmriprep_proc"
    fmriprep_dir = tmp_path / "fmriprep_dir"
    fs_dir = "fs_dir"
    templateflow_dir = "templateflow_dir"
    participant_id = "01"
    singularity_container = "fmriprep.sif"

    cmd = run_fmriprep(
        participant_id=participant_id,
        bids_dir=bids_dir,
        proc_dir=proc_dir,
        fmriprep_dir=fmriprep_dir,
        fs_dir=fs_dir,
        templateflow_dir=templateflow_dir,
        SINGULARITY_CONTAINER=singularity_container,
        use_bids_filter=use_bids_filter,
        anat_only=anat_only,
        logger=my_logger.get_logger(log_file=log_file),
    )
    # fmt: off
    expected_cmd = [
        'singularity', 'run', 
            '-B', f'{bids_dir}:{bids_dir}',
            '-B', f'{fmriprep_dir}/output//fmriprep_home_{participant_id}/:/home/fmriprep', 
            '--home', '/home/fmriprep', 
            '--cleanenv', 
            '-B', f'{fmriprep_dir}/output/:/output', 
            '-B', f'{proc_dir}:/fmriprep_proc',  
            '-B', f'{templateflow_dir}:/templateflow', 
            '-B', f'{fmriprep_dir}:/work', 
            '-B', f'{fs_dir}:/fsdir/', 
                singularity_container, bids_dir, '/output', 'participant', 
                    '--participant-label', participant_id, 
                    '-w', '/work', 
                    '--output-spaces', 'MNI152NLin2009cAsym:res-2', 'anat', 'fsnative', 
                    '--fs-subjects-dir', '/fsdir/', 
                    '--skip_bids_validation', 
                    '--bids-database-dir', '/fmriprep_proc/bids_db_fmriprep', 
                    '--fs-license-file', '/fsdir/license.txt', 
                    '--return-all-components', 
                    '-v', 
                    '--write-graph', 
                    '--notrack', 
                    '--omp-nthreads', '4', 
                    '--nthreads', '8', 
                    '--mem_mb', '4000']
    # fmt: on

    if use_bids_filter:
        expected_cmd += ["--bids-filter-file", "/fmriprep_proc/bids_filter_fmriprep.json"]

    if anat_only:
        expected_cmd += ["--anat-only"]

    assert cmd == expected_cmd
