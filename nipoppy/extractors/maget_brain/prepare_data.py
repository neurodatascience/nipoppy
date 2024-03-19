import nibabel as nib
import glob
import os
import sys
import argparse
import json
import pandas as pd
from pathlib import Path

def get_masked_image(img_path, mask_path, masked_img_path):
    ''' Applies brain binary mask to nii.gz image'''

    # load main image
    img = nib.load(img_path)
    img_data = img.get_fdata()

    # load anothor image to mask
    mask = nib.load(mask_path)
    mask_data = mask.get_fdata()

    # do masking 
    masked_img_data = mask_data * img_data

    #save the new file out  
    masked_img = nib.Nifti1Image(masked_img_data, header=img.header, affine=img.affine)
    nib.save(masked_img, masked_img_path)  

# argparse
HELPTEXT = """
Extractor script to prepare data for maget_brain
"""
parser = argparse.ArgumentParser(description=HELPTEXT)
parser.add_argument('--global_config', type=str, required=True, help='path to global config file for your nipoppy dataset')
parser.add_argument('--session_id', type=str, required=True, help='current session or visit ID for the dataset')
parser.add_argument('--run_id', type=str, default=None, help='run id for the scan')

args = parser.parse_args()
session_id = args.session_id
run_id = args.run_id

# read global configs
global_config_file = args.global_config
with open(global_config_file, 'r') as f:
    global_configs = json.load(f)

DATASET_ROOT = global_configs["DATASET_ROOT"]
fmriprep_version = global_configs["PROC_PIPELINES"]["fmriprep"]["VERSION"]
maget_version = global_configs["PROC_PIPELINES"]["maget_brain"]["VERSION"]

fmriprep_dir = f"{DATASET_ROOT}/derivatives/fmriprep/{fmriprep_version}/output/"
maget_dir = f"{DATASET_ROOT}/derivatives/maget_brain/{maget_version}/output/"
maget_preproc_T1w_nii_dir = f"{maget_dir}/ses-{session_id}/preproc_T1w_nii/"
maget_proc_list_file = f"{maget_preproc_T1w_nii_dir}proc_participant.csv"

# Check / create maget subdirs
Path(maget_preproc_T1w_nii_dir).mkdir(parents=True, exist_ok=True)

# get all the subject ids from the doughnut
doughnut_csv = f"{DATASET_ROOT}/scratch/raw_dicom/doughnut.csv"
doughnut_df = pd.read_csv(doughnut_csv)
bids_id_list = doughnut_df["bids_id"].unique()

proc_participants = [] # To be replaced when maget-brain tracker is written...
for bids_id in bids_id_list:
    if run_id == None:
        img_file_name = f"{bids_id}_ses-{session_id}_desc-preproc_T1w.nii.gz"
        mask_file_name = f"{bids_id}_ses-{session_id}_desc-brain_mask.nii.gz"
        masked_img_file_name = f"{bids_id}_ses-{session_id}_desc-masked_preproc_T1w.nii.gz"

    else:
        img_file_name = f"{bids_id}_ses-{session_id}_run-{run_id}_desc-preproc_T1w.nii.gz"
        mask_file_name = f"{bids_id}_ses-{session_id}_run-{run_id}_desc-brain_mask.nii.gz"
        masked_img_file_name = f"{bids_id}_ses-{session_id}_run-{run_id}_desc-masked_preproc_T1w.nii.gz"

    img_path = f"{fmriprep_dir}/{bids_id}/ses-{session_id}/anat/{img_file_name}"
    mask_path = f"{fmriprep_dir}/{bids_id}/ses-{session_id}/anat/{mask_file_name}"
    masked_img_path = f"{maget_preproc_T1w_nii_dir}/{masked_img_file_name}"
    
    # Check if the masked image exists
    if os.path.isfile(masked_img_path):
        print(f"Participant segmentation already exist: {bids_id}")
    else:
        try:
            get_masked_image(img_path, mask_path, masked_img_path)
            proc_participants.append(bids_id)
        except Exception as e:
            print(e)
        
pd.DataFrame(data=proc_participants).to_csv(maget_proc_list_file, header=False, index=False)