#!/usr/bin/env python

import argparse
import json
import glob
import shutil
import subprocess
from joblib import Parallel, delayed
from pathlib import Path
from typing import Iterable

import numpy as np
from bids.layout import parse_file_entities

import nipoppy.workflow.catalog as catalog
import nipoppy.workflow.logger as my_logger
from nipoppy.workflow.utils import (
    COL_CONV_STATUS,
    COL_DICOM_ID,
    DNAME_BACKUPS_DOUGHNUT,
    FNAME_DOUGHNUT, 
    load_doughnut,
    save_backup,
    session_id_to_bids_session,
)


def run_dcm2bids(dicom_id, global_configs, session_id, stage, overlays, logger):
    logger.info(f"\n***Processing participant: {dicom_id}***")
    DATASET_ROOT = global_configs["DATASET_ROOT"]
    SINGULARITY_PATH = global_configs["SINGULARITY_PATH"]
    CONTAINER_STORE = global_configs["CONTAINER_STORE"]
    DCM2BIDS_CONTAINER = global_configs["BIDS"]["dcm2bids"]["CONTAINER"]
    DCM2BIDS_VERSION = global_configs["BIDS"]["dcm2bids"]["VERSION"]
    DCM2BIDS_CONTAINER = DCM2BIDS_CONTAINER.format(DCM2BIDS_VERSION)
    SINGULARITY_DCM2BIDS = f"{CONTAINER_STORE}/{DCM2BIDS_CONTAINER}"
    SINGULARITY_WD = "/scratch"
    SINGULARITY_DICOM_DIR = f"{SINGULARITY_WD}/dicom/ses-{session_id}"
    SINGULARITY_BIDS_DIR = f"{SINGULARITY_WD}/bids"
    CONFIG_FILE=f"{SINGULARITY_WD}/proc/dcm2bids_config.json"

    logger.info(f"Using SINGULARITY_DCM2BIDS: {SINGULARITY_DCM2BIDS}")

    flag_overlay = ''
    flag_bind = ''
    if overlays is not None:

        logger.info(f"Using overlay(s): {overlays}")
        for overlay in overlays:
            flag_overlay += f'--overlay {overlay} '

        for dname in ['bids', 'tabular', 'proc']:
            flag_bind += f'--bind {DATASET_ROOT}/{dname}:{SINGULARITY_WD}/{dname} '
    else:
        flag_bind = f'--bind {DATASET_ROOT}:{SINGULARITY_WD}'

    # Singularity CMD 
    SINGULARITY_CMD=f"{SINGULARITY_PATH} run {flag_overlay} {flag_bind} {SINGULARITY_DCM2BIDS} "

    # dcm2bids CMD
    if stage == 1:
        logger.info("Running dcm2bids_helper")
        dcm2bids_CMD = f" dcm2bids_helper \
            -d {SINGULARITY_DICOM_DIR}/{dicom_id} \
            -o {SINGULARITY_BIDS_DIR}/helper "

    elif stage == 2:
        logger.info("Running dcm2bids")
        dcm2bids_CMD = f" dcm2bids \
            -d {SINGULARITY_DICOM_DIR}/{dicom_id} \
            -p {dicom_id} \
            -s {session_id} \
            -c {CONFIG_FILE} \
            -o {SINGULARITY_BIDS_DIR} "

    else:
        logger.error(f"Incorrect dcm2bids stage: {stage}")

    CMD_ARGS = SINGULARITY_CMD + dcm2bids_CMD 
    CMD = CMD_ARGS.split()

    logger.info(f"CMD:\n{CMD_ARGS}")
    dcm2bids_proc_success = True
    try:
        subprocess.run(CMD, check=True) # raises CalledProcessError if non-zero return code
    except Exception as e:
        logger.error(f"bids run failed with exceptions: {e}")
        dcm2bids_proc_success = False

    return dcm2bids_proc_success

def run(global_configs, session_id, stage=2, overlays=None, n_jobs=2, dicom_id=None, logger=None, fpaths_to_copy=None):
    """ Runs the bids conv tasks 
    """
    session = session_id_to_bids_session(session_id)
    DATASET_ROOT = global_configs["DATASET_ROOT"]
    log_dir = f"{DATASET_ROOT}/scratch/logs/"

    if fpaths_to_copy is None:
        fpaths_to_copy = []

    if logger is None:
        log_file = f"{log_dir}/bids_conv.log"
        logger = my_logger.get_logger(log_file)

    logger.info("-"*50)
    logger.info(f"Using DATASET_ROOT: {DATASET_ROOT}")
    logger.info(f"Running dcm2bids stage: {stage}")
    logger.info(f"Number of parallel jobs: {n_jobs}")

    fpath_doughnut = Path(DATASET_ROOT, 'scratch', 'raw_dicom', FNAME_DOUGHNUT)
    bids_dir = f"{DATASET_ROOT}/bids/"

    df_doughnut = load_doughnut(fpath_doughnut)

    # participants to process with dcm2bids
    if dicom_id is None:
        dcm2bids_df = catalog.get_new_dicoms(fpath_doughnut, session_id, logger)
    else:
        # filter by DICOM ID if needed
        logger.info(f'Only running for participant: {dicom_id}')
        dcm2bids_df = df_doughnut.loc[df_doughnut[COL_DICOM_ID] == dicom_id]
    
    dcm2bids_participants = set(dcm2bids_df["dicom_id"].values)
    n_dcm2bids_participants = len(dcm2bids_participants)

    if n_dcm2bids_participants > 0:
        logger.info(f"\nStarting bids conversion for {n_dcm2bids_participants} participant(s)")
    
        if stage == 2:
            for fpath in fpaths_to_copy:
                fpath = Path(fpath)
                logger.info(f"Copying {fpath} to {DATASET_ROOT}/proc/{fpath.name} (to be seen by Singularity container)")
                shutil.copyfile(fpath, f"{DATASET_ROOT}/proc/{fpath.name}")

        if n_jobs > 1:
            ## Process in parallel! (Won't write to logs)
            dcm2bids_results = Parallel(n_jobs=n_jobs)(delayed(run_dcm2bids)(
                dicom_id, global_configs, session_id, stage, overlays, logger
                ) for dicom_id in dcm2bids_participants)

        else:
            # Useful for debugging
            dcm2bids_results = []
            for dicom_id in dcm2bids_participants:
                res = run_dcm2bids(dicom_id, global_configs, session_id, stage, overlays, logger) 
            dcm2bids_results.append(res)

        # Check successful dcm2bids runs
        n_dcm2bids_success = np.sum(dcm2bids_results)
        logger.info(f"Successfully ran dcm2bids (Stage 1 or Stage 2) for {n_dcm2bids_success} out of {n_dcm2bids_participants} participants")

        # Check successful bids (NOTE: will count partial conversion as successful)
        participants_with_bids = {
            parse_file_entities(dpath)['subject']
            for dpath in
            glob.glob(f"{bids_dir}/sub-*/{session}")
        }

        new_participants_with_bids = dcm2bids_participants & participants_with_bids
        
        logger.info("-"*50)

        if stage == 1:
            # Generate empty config file
            logger.info(f"Creating dcm2bids_config.json in {DATASET_ROOT}/proc (to be seen by Singularity container)")
            
            config_content = {
                "descriptions": []
            }

            with open(f"{DATASET_ROOT}/proc/dcm2bids_config.json", 'w') as config_file:
                json.dump(config_content, config_file, indent='\t')

            logger.info("Stage 1 done! Still need to run Stage 2")

        else:

            logger.info(f"Current successfully converted BIDS participants for session {session}: {len(participants_with_bids)}")
            logger.info(f"BIDS conversion completed for the {len(new_participants_with_bids)} out of {len(dcm2bids_participants)} new participants")
            
            if len(new_participants_with_bids) > 0:
                dcm2bids_df.loc[dcm2bids_df[COL_DICOM_ID].isin(new_participants_with_bids), COL_CONV_STATUS] = True
                df_doughnut.loc[dcm2bids_df.index] = dcm2bids_df
                save_backup(df_doughnut, fpath_doughnut, DNAME_BACKUPS_DOUGHNUT)

    else:
        logger.info(f"No new participants found for bids conversion...")

    logger.info("-"*50)
    logger.info("")

if __name__ == '__main__':
    # argparse
    HELPTEXT = """
    Script to perform DICOM to BIDS conversion using dcm2bids
    """
    parser = argparse.ArgumentParser(description=HELPTEXT)

    parser.add_argument('--global_config', type=str, help='path to global configs for a given nipoppy dataset', required=True)
    parser.add_argument('--session_id', type=str, help='session id for the participant', required=True)
    parser.add_argument('--stage', type=int, default=2, help='dcm2bids stage - either 1 to help generate a config file (a template is created at <DATASET_ROOT>/proc/dcm2bids_config.json), or 2 if a config file has already been created (at the same location), default: 2)')
    parser.add_argument('--overlay', type=str, nargs='+', help='path(s) to Squashfs overlay(s)')
    parser.add_argument('--n_jobs', type=int, default=2, help='number of parallel processes (default: 2)')
    parser.add_argument('--dicom_id', type=str, help='dicom id for a single participant to run (default: run on all participants in the doughnut file)')
    parser.add_argument('--copy_files', nargs='+', type=str, help='path(s) to file(s) to copy to /scratch/proc in the container')

    args = parser.parse_args()

    global_config_file = args.global_config
    session_id = args.session_id
    stage = args.stage
    overlays = args.overlay
    n_jobs = args.n_jobs
    dicom_id = args.dicom_id
    fpaths_to_copy = args.copy_files

    # Read global configs
    with open(global_config_file, 'r') as f:
        global_configs = json.load(f)

    # use absolute path
    if overlays is not None:
        if isinstance(overlays, str):
            overlays = [overlays]
        if not isinstance(overlays, Iterable):
            raise RuntimeError('overlays must be a string or iterable of strings')
        overlays = [Path(o).resolve() for o in overlays]

    run(global_configs, session_id, stage=stage, overlays=overlays, n_jobs=n_jobs, dicom_id=dicom_id, fpaths_to_copy=fpaths_to_copy)
