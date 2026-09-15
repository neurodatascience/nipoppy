# Convert MRI sourcedata to BIDS

In this tutorial, you will learn how to use Nipoppy and the BIDS converter [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/3.2.0/) to convert your imaging sourcedata to {term}`BIDS`.

Concretely, we will:
1. Initialize a Nipoppy study
2. Reorganize DICOM sourcedata
3. Install and set up the dcm2bids pipeline
4. Extract DICOM header information to create the `dcm2bids_config.json` file
5. Convert the DICOM sourcedata to NIfTI BIDS raw data

```{note}
If you have not installed Nipoppy yet, instructions are available [here](../../overview/installation).
```

## Step 0: Download the tutorial dataset

We will use the [tutorial dataset](https://github.com/nipoppy/tutorial-dataset) provided on the Nipoppy GitHub, which includes DICOM data of different modalities for 4 subjects (*Note: Data of one subject was copied in order to create multiple subjects with different modalities for training purposes. Hence, all data stems from one subject*).

There are multiple ways of downloading the dataset:

**1. via `git clone`**

SSH: `git clone git@github.com:nipoppy/tutorial-dataset.git`

HTTPS: `git clone https://github.com/nipoppy/tutorial-dataset.git`

**2. via the browser:**

- Go to [https://github.com/nipoppy/tutorial-dataset](https://github.com/nipoppy/tutorial-dataset)
- Click on the green button "Code" on the right upper corner on the repo site and select "Download ZIP"

**3. via the command line:**

```
wget -O tutorial-dataset.zip https://github.com/nipoppy/tutorial-dataset/archive/refs/heads/main.zip
```
Unzip once downloaded.

## Step 1: Initialize the Nipoppy study

**1.1.** Run the following command to create a Nipoppy study:

```console
$ nipoppy init --dataset nipoppy_study
```

This command creates a folder named `nipoppy_study` with subdirectories for raw data, processed (derivatives) data, pipeline configuration files, logs, etc. The `tree` command can be used to show the directory structure.

```console
$ tree -L 1 nipoppy_study
```

```{code-block}
:caption: Output
nipoppy_study/
├── bids
├── code
├── containers
├── derivatives
├── global_config.json
├── logs
├── manifest.tsv
├── pipelines
├── scratch
├── sourcedata
└── tabular
```

**1.2.** Please replace the `manifest.tsv` in `nipoppy_study` with the `manifest.tsv` provided in the tutorial dataset. This file is considered the ground truth for which participants and sessions are available for processing.

## Step 2: Reorganize the DICOM sourcedata

:::{dropdown} Good to know: why reorganization?
Usually, there is a gap between data state out of scanner vs. ready for bidsification. Source data is often messy in different ways, making it hard to use BIDSification tools directly. Nipoppy provides a unified way to deal with DICOM vs. Nifti sourcedata which simplifies BIDSification. It also helps fixing issues related to file naming which often appear in chaotic data dumps or due to typos. Additionally, the organization simplifies taring the DICOMs after bidsification. All this is implemented in one simple command, namely [`nipoppy reorg`](../../reference/cli_reference/reorg.rst).
:::


**2.1.** We need to move the **content** of the `tutorial-dataset/reorg` directory to the `sourcedata/imaging/pre_reorg` directory of our `nipoppy_study` study, i.e.:

```console
mv tutorial-dataset/reorg/* nipoppy_study/sourcedata/imaging/pre_reorg
```

Running `tree nipoppy_study/sourcedata/imaging/pre_reorg/ | head` we can see come of the content of the `pre_reorg` folder:

```
├── ED01
│   └── BL
│       ├── DTI_30_DIRs_AP_15
│       │   ├── IM-0003-0001.dcm
│       │   ├── IM-0003-0002.dcm
│       │   ├── IM-0003-0003.dcm
│       │   ├── IM-0003-0004.dcm
│       │   ├── IM-0003-0005.dcm
│       │   ├── IM-0003-0006.dcm
...
```

We need to track this modification in our study by running

```console
nipoppy track-curation --dataset nipoppy_study
```

before we can have an overview of the study status with

```console
nipoppy status --dataset nipoppy_study
```

```{code-block}
:caption: Partial output
     Participant counts by session at each Nipoppy checkpoint
            ╷             ╷
 session_id │ in_manifest │ in_pre_reorg
════════════╪═════════════╪════════════════
    01      │      4      │      4
            ╵             ╵
```

**2.2.** We run

```console
nipoppy reorg --dataset nipoppy_study
```

Our data was symlinked and reorganized into the `post_reorg` directory. We can see so by running

```console
tree nipoppy_study/sourcedata/imaging/post_reorg/ | head
```

```{code-block}
:caption: Output
├── README.md
├── sub-ED01
│   └── ses-BL
│       ├── 82519e8_IM-0003-0001.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0001.dcm
│       ├── 82519e8_IM-0003-0002.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0002.dcm
│       ├── 82519e8_IM-0003-0003.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0003.dcm
│       ├── 82519e8_IM-0003-0004.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0004.dcm
│       ├── 82519e8_IM-0003-0005.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0005.dcm
│       ├── 82519e8_IM-0003-0006.dcm -> ../../../pre_reorg/ED01/BL/DTI_30_DIRs_AP_15/IM-0003-0006.dcm
```

and by running `nipoppy status`:

```{code-block}
:caption: Partial output
     Participant counts by session at each Nipoppy checkpoint
            ╷             ╷
 session_id │ in_manifest │ in_post_reorg
════════════╪═════════════╪════════════════
    01      │      4      │      4
            ╵             ╵
```

## Step 3: Install and set up the dcm2bids pipeline

**3.1.** The `nipoppy init` command created the configuration file at `nipoppy_study/global_config.json`. This file may need to be updated with information specific to your computing environment. Initially, it will look like this:

```{literalinclude} ../../_inserts/sample_study_config.json5
---
linenos: True
language: json
emphasize-lines: 6,11
---
```

By default, this file does not contain any pipeline-specific information, since the study does not have any pipelines installed yet. Still, there are fields that may need to be modified depending on your setup:
- If Apptainer is not available on your system, you will need to change `CONTAINER_CONFIG` -> `COMMAND` to
    - `"singularity"` if you have Singularity installed
    - `"docker"` if you have Docker installed
    - `"null"` if you have dcm2bids installed locally ("baremetal" install)
- If your group uses a shared directory for storing container image files, you can replace the value of `"[[NIPOPPY_DPATH_CONTAINERS]]"` by the full path to that shared directory. For example:
    ```json
    "SUBSTITUTIONS": {
        "_comment": "Self-references like NIPOPPY_DPATH_CONTAINERS are resolved from the layout at runtime, making them layout-aware",
        "[[NIPOPPY_DPATH_CONTAINERS]]": "<PATH_TO_SHARED_DIRECTORY>",
        "[[HPC_ACCOUNT_NAME]]": ""
    },
    ```
    - Alternatively, you can create a symlink from {{dpath_containers}} to that directory (then this line in the configuration can be deleted) (recommended).

**3.2.** We can use following command to check which pipelines can be run with the study:

```console
$ nipoppy pipeline list --dataset nipoppy_study
```

The output says that there are no available pipelines to be run:
```
INFO     No available bidsification pipelines
INFO     No available processing pipelines
INFO     No available extraction pipelines
```

That is because a newly initialized Nipoppy study does not contain any pipelines. Pipeline configuration files are available on the [Zenodo data repository](https://zenodo.org/search?q=metadata.subjects.subject%3A%22Nipoppy%22&l=list&p=1&s=10&sort=bestmatch) and can be searched for directly from your terminal using the command `nipoppy pipeline search`. The [configuration files for dcm2bids](https://zenodo.org/records/16876754) can be downloaded by running the following:
```{code-block} console
$ nipoppy pipeline install --dataset nipoppy_study {{zenodo_id_dcm2bids_3_2_0}}
```

When running `nipoppy pipeline install`, if using a container engine, you will be asked if you would like to download the dcm2bids container. If you do not already have a download of the container, type `y` and press `Enter` to do so. The download/building process may take ~10 minutes. Apptainer or Singularity container images will be downloaded as `dcm2bids_3.2.0.sif` inside the container store directory (i.e., `nipoppy_study/containers` or the custom path you set in the `global_config.json` file). Docker images are managed centrally and so will not be downloaded to the study.

**3.3.** When we open the `nipoppy_study/global_config.json`, we can see that the pipeline expects some more configuration (indicated by the null placeholder):

```{code-block} json
:emphasize-lines: 5
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {
            "dcm2bids": {
                "3.2.0": {
                    "DCM2BIDS_CONFIG_FILE": null
                }
            }
        },
        "PROCESSING": {},
        "EXTRACTION": {}
    },
```

We need to replace the `null` next to the `DCM2BIDS_CONFIG_FILE` field with file path to the `dcm2bids_config.json` file that we will create in the next step. We recommend to keep this file in the `code` directory in your nipoppy study, like so:

```{code-block} json
:emphasize-lines: 5
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {
            "dcm2bids": {
                "3.2.0": {
                    "DCM2BIDS_CONFIG_FILE": "[[NIPOPPY_DPATH_CODE]]/dcm2bids_config.json"
                }
            }
        },
        "PROCESSING": {},
        "EXTRACTION": {}
    },
```

```{note}
Without setting this path now, the next `nipoppy bidsify prepare` step will crash.
```

## Step 4: Extract DICOM header information to create the `dcm2bids_config.json`

dcm2bids is a multi-step pipeline in Nipoppy. The steps are detailed in {{dpath_pipelines}}`/bidsification/dcm2bids-3.2.0/config.json`:


**4.1.** We run
```console
nipoppy bidsify --dataset nipoppy_study --pipeline dcm2bids --pipeline-version 3.2.0 --pipeline-step prepare
```

In our scratch directory we should see something like this now:
```
scratch/
├── dcm2bids_helper
│   ├── 013_post_reorg_T1_mprage_1mm_20180706110327.json
│   ├── 013_post_reorg_T1_mprage_1mm_20180706110327.nii.gz
│   ├── 015_post_reorg_DTI_30_DIRs_A-P_20180706110327.bval
│   ├── 015_post_reorg_DTI_30_DIRs_A-P_20180706110327.bvec
│   ├── 015_post_reorg_DTI_30_DIRs_A-P_20180706110327.json
│   ├── 015_post_reorg_DTI_30_DIRs_A-P_20180706110327.nii.gz
│   ├── 018_post_reorg_restingstate_20180706110327.json
│   └── 018_post_reorg_restingstate_20180706110327.nii.gz
```

The "prepare" step uses the `dcm2bids_helper` command to turn one participant's DICOMs into NIfTI files with their accompanying JSON metadata files. Our task is now to find unique metadata or descriptions in each modality's JSON file, so that dcm2bids knows how to group a set of acquisitions and how to label them according to {term}`BIDS`. In other words, we need to link the metadata to BIDS-specific vocabulary.

Unique entries in the JSON files can be `SeriesDescription`, `EchoTime`, `ProtocolName`, `ImageType` etc. Whatever makes the files acquired under one condition different from other files acquired under different conditions. Also, we need to tell dcm2bids to which BIDS datatype this acquisition refers to and which BIDS suffix this file is going to have, so you need some knowledge of the [BIDS specification](https://bids-specification.readthedocs.io/en/stable/) for this task.

In our case, the `dcm2bids_config.json` can look like this:

```{code-block} json
{
    "descriptions": [
      {
        "datatype": "anat",
        "suffix": "T1w",
        "criteria": {
          "SeriesDescription": "T1_mprage_1mm"
        }
      },
      {
        "datatype": "func",
        "suffix": "bold",
        "custom_entities": "task-rest",
        "criteria": {
          "SeriesDescription": "restingstate",
        "sidecar_changes": {
          "TaskName": "rest"
          }
        }
      },
      {
      "datatype": "dwi",
      "suffix": "dwi",
      "criteria": {
        "SeriesDescription": "DTI_30_DIRs_A-P"
        }
      }
    ]
  }
```

**4.2.** We create a `dcm2bids_config.json` with the above content and place it in the `code` directory in our `nipoppy_study` study.

## Step 5: Convert the DICOM sourcedata to NIfTI BIDS raw data

**5.1.** We are now ready to run the "convert" step

```console
nipoppy bidsify --dataset nipoppy_study --pipeline dcm2bids --pipeline-version 3.2.0 --pipeline-step convert
```

After successful conversion, the output of `nipoppy status` should tell us that we have all our participants `in_bids`:

```{code-block}
:caption: Partial output
     Participant counts by session at each Nipoppy checkpoint
            ╷             ╷
 session_id │ in_manifest │ in_bids
════════════╪═════════════╪═════════
    01      │      4      │      4
            ╵             ╵
```
