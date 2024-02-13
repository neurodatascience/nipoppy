import argparse
import json
import subprocess
import os
from pathlib import Path
import nipoppy.workflow.logger as my_logger
import shutil
import logging

#Author: nikhil153
#Date: 31-Mar-2023 (last update)
fname = __file__
CWD = os.path.dirname(os.path.abspath(fname))

# env vars relative to the container.
SINGULARITY_FS_DIR = "/fsdir/"
SINGULARITY_TEMPLATEFLOW_DIR = "/templateflow"
SINGULARITY_FS_LICENSE = "/fsdir/license.txt"
os.environ['SINGULARITYENV_SUBJECTS_DIR'] = SINGULARITY_FS_DIR
os.environ['SINGULARITYENV_FS_LICENSE'] = SINGULARITY_FS_LICENSE
os.environ['SINGULARITYENV_TEMPLATEFLOW_HOME'] = SINGULARITY_TEMPLATEFLOW_DIR

MEM_MB = 4000

def run_fmriprep(participant_id: str,
                 bids_dir,
                 proc_dir,
                 fmriprep_dir,
                 fs_dir,
                 templateflow_dir,
                 SINGULARITY_CONTAINER: str,
                 use_bids_filter: bool,
                 anat_only: bool,
                 logger: logging.Logger):
    """ Launch fmriprep container"""

    fmriprep_out_dir = f"{fmriprep_dir}/output/"
    fmriprep_home_dir = f"{fmriprep_out_dir}/fmriprep_home_{participant_id}/"
    Path(f"{fmriprep_home_dir}").mkdir(parents=True, exist_ok=True)

    # BIDS DB created for fmriprep by run_nipoppy.py
    bids_db_dir = f"/fmriprep_proc/bids_db_fmriprep"

    # Singularity CMD 
    SINGULARITY_CMD=f"singularity run \
        -B {bids_dir}:{bids_dir} \
        -B {fmriprep_home_dir}:/home/fmriprep --home /home/fmriprep --cleanenv \
        -B {fmriprep_out_dir}:/output \
        -B {proc_dir}:/fmriprep_proc \
        -B {templateflow_dir}:{SINGULARITY_TEMPLATEFLOW_DIR} \
        -B {fmriprep_dir}:/work \
        -B {fs_dir}:{SINGULARITY_FS_DIR} \
        {SINGULARITY_CONTAINER}"

    # Compose fMRIPrep command
    fmriprep_CMD=f" {bids_dir} /output participant --participant-label {participant_id} \
        -w /work \
        --output-spaces MNI152NLin2009cAsym:res-2 anat fsnative \
        --fs-subjects-dir {SINGULARITY_FS_DIR} \
        --skip_bids_validation \
        --bids-database-dir {bids_db_dir} \
        --fs-license-file {SINGULARITY_FS_LICENSE} \
        --return-all-components -v \
        --write-graph --notrack \
        --omp-nthreads 4 --nthreads 8 --mem_mb {MEM_MB}"

    # Field map (TODO)
    # --use-syn-sdc --force-syn --ignore fieldmaps \

    # Append optional args
    if use_bids_filter:
        logger.info("Using bids_filter.json")
        bids_filter_str = f"--bids-filter-file /fmriprep_proc/bids_filter_fmriprep.json"
        fmriprep_CMD = f"{fmriprep_CMD} {bids_filter_str}"

    if anat_only:
        logger.info("Using anat_only workflow")
        anat_only_str = "--anat-only"
        fmriprep_CMD = f"{fmriprep_CMD} {anat_only_str}"

    CMD_ARGS = SINGULARITY_CMD + fmriprep_CMD 
    CMD = CMD_ARGS.split()

    logger.info("Running fmriprep...")
    logger.info("-"*50)
    logger.info(f"CMD:\n{CMD}")
    logger.info("-"*50)
    try:
        fmriprep_proc = subprocess.run(CMD)
    except Exception as e:
        logger.error(f"fmriprep run failed with exceptions: {e}")
    
    logger.info(f"Successfully completed fmriprep run for participant: {participant_id}")
    logger.info("-"*75)
    logger.info("")
    return CMD

def run(participant_id: str,
        global_configs,
        session_id: str,
        output_dir: str,
        use_bids_filter: bool,
        anat_only: bool,
        logger=None):
    """ Runs fmriprep command
    """
    DATASET_ROOT = global_configs["DATASET_ROOT"]
    TEMPLATEFLOW_DIR = global_configs["TEMPLATEFLOW_DIR"]
    CONTAINER_STORE = global_configs["CONTAINER_STORE"]
    FMRIPREP_CONTAINER = global_configs["PROC_PIPELINES"]["fmriprep"]["CONTAINER"]
    FMRIPREP_VERSION = global_configs["PROC_PIPELINES"]["fmriprep"]["VERSION"]
    FS_VERSION = global_configs["PROC_PIPELINES"]["freesurfer"]["VERSION"]
    FMRIPREP_CONTAINER = FMRIPREP_CONTAINER.format(FMRIPREP_VERSION)

    SINGULARITY_FMRIPREP = f"{CONTAINER_STORE}{FMRIPREP_CONTAINER}"

    log_dir = f"{DATASET_ROOT}/scratch/logs/"

    if logger is None:
        log_file = f"{log_dir}/fmriprep.log"
        logger = my_logger.get_logger(log_file)

    logger.info("-"*75)
    logger.info(f"Using DATASET_ROOT: {DATASET_ROOT}")
    logger.info(f"Using participant_id: {participant_id}, session_id:{session_id}")
    logger.info(f"Optional args: --anat_only={anat_only}, --use_bids_filter={use_bids_filter}")

    if output_dir is None:
        output_dir = f"{DATASET_ROOT}/derivatives/"

    bids_dir = f"{DATASET_ROOT}/bids/"
    proc_dir = f"{DATASET_ROOT}/proc/"
    fmriprep_dir = f"{output_dir}/fmriprep/{FMRIPREP_VERSION}"

    # Check and create session_dirs for freesurfer since it won't happen automatically
    fs_dir = f"{output_dir}/freesurfer/{FS_VERSION}/output/ses-{session_id}"
    Path(fs_dir).mkdir(parents=True, exist_ok=True)

    # Copy FS license in the session specific output dir (to be seen by Singularity container)
    FS_license = f"{output_dir}/freesurfer/license.txt"
    shutil.copyfile(f"{FS_license}", f"{fs_dir}/license.txt")
    logger.info(f"Copying FS license to {fs_dir}/license.txt (to be seen by Singularity container)")

    # Copy bids_filter.json `<DATASET_ROOT>/bids/bids_filter.json`
    if use_bids_filter:
        logger.info(f"Copying ./bids_filter.json to {proc_dir}/bids_filter_fmriprep.json (to be seen by Singularity container)")
        Path(proc_dir).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f"{CWD}/bids_filter.json", f"{proc_dir}/bids_filter_fmriprep.json")

    # launch fmriprep
    run_fmriprep(participant_id,
                 bids_dir,
                 proc_dir,
                 fmriprep_dir,
                 fs_dir,
                 TEMPLATEFLOW_DIR,
                 SINGULARITY_FMRIPREP,
                 use_bids_filter,
                 anat_only,
                 logger)

if __name__ == '__main__':
    # argparse
    HELPTEXT = """
    Script to run fMRIPrep 
    """

    parser = argparse.ArgumentParser(description=HELPTEXT)

    parser.add_argument('--global_config', type=str, help='path to global configs for a given nipoppy dataset')
    parser.add_argument('--participant_id', type=str, help='participant id')
    parser.add_argument('--session_id', type=str, help='session id for the participant')
    parser.add_argument('--output_dir', type=str, default=None, 
                        help='specify custom output dir (if None --> <DATASET_ROOT>/derivatives)')
    parser.add_argument('--use_bids_filter', action='store_true', help='use bids filter or not')
    parser.add_argument('--anat_only', action='store_true', help='run only anatomical workflow or not')

    args = parser.parse_args()

    global_config_file = args.global_config
    participant_id = args.participant_id
    session_id = args.session_id
    output_dir = args.output_dir # Needed on BIC (QPN) due to weird permissions issues with mkdir
    use_bids_filter = args.use_bids_filter
    anat_only = args.anat_only

    # Read global configs
    with open(global_config_file, 'r') as f:
        global_configs = json.load(f)

    run(participant_id, global_configs, session_id, output_dir, use_bids_filter, anat_only)
