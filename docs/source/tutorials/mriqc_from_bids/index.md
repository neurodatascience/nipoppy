# Run MRIQC on a BIDS dataset

In this tutorial, you will learn how to use the Nipoppy {term}`CLI` to run the [MRIQC](https://mriqc.readthedocs.io/en/23.1.0/) pipeline (version 23.1.0) on the [ds004101](https://openneuro.org/datasets/ds004101/versions/1.0.1) BIDS dataset available from OpenNeuro.

Concretely, we will:

1. **Initialize** a Nipoppy study from a BIDS dataset
2. **Install** and set up the MRIQC processing pipeline
2. **Run** MRIQC on a single participant and session
3. **Track** the output files to check if processing was successful

```{note}
If you have not installed Nipoppy yet, instructions are available [here](../../overview/installation).
```

## Step 0: Download the BIDS dataset

We will use the [**ds004101 dataset from OpenNeuro**](https://openneuro.org/datasets/ds004101/versions/1.0.1), which includes structural and functional MRI data for 9 subjects (2 sessions). The dataset can be downloaded by following instructions [here](https://openneuro.org/datasets/ds004101/versions/1.0.1/download). If you do not have DataLad or Node.js installed, you can use the shell script method:

- Click on the "Download shell script" link at the bottom of [this page](https://openneuro.org/datasets/ds004101/versions/1.0.1/download). This should download a file called `ds004101-1.0.1.sh` to your computer.
- Move `ds004101-1.0.1.sh` to the directory you will use for this tutorial.
- Open a Terminal window and go to the directory where you put the script. Then run:
  ```console
  $ bash ds004101-1.0.1.sh
  ```
- Depending on your internet connection, the above command may take a few minutes. Once it is done, you should have a new directory `ds004101-1.0.1` containing the BIDS dataset. Run `tree ds004101-1.0.1` to see the dataset content.

## Step 1: Initialize the Nipoppy study

Run the following command to create a Nipoppy study and populate it with the BIDS data:

```console
$ nipoppy init --dataset nipoppy_study --bids-source ds004101-1.0.1
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

Nipoppy automatically generated a {term}`manifest file` from the BIDS dataset. This file is considered the ground truth for which participants and sessions are available for processing.

```{code-block}
:caption: Content of `nipoppy_study/manifest.tsv`
participant_id  visit_id    session_id  datatype
09114           1pre        1pre        ['anat', 'func']
09114           2post       2post       ['fmap', 'func']
09160           1pre        1pre        ['anat', 'func']
09160           2post       2post       ['fmap', 'func']
09260           1pre        1pre        ['anat', 'fmap', 'func']
09260           2post       2post       ['fmap', 'func']
09300           1pre        1pre        ['anat', 'fmap', 'func']
09300           2post       2post       ['fmap', 'func']
09380           1pre        1pre        ['anat', 'fmap', 'func']
09380           2post       2post       ['fmap', 'func']
09381           1pre        1pre        ['anat', 'fmap', 'func']
09381           2post       2post       ['fmap', 'func']
10134           1pre        1pre        ['anat', 'fmap', 'func']
10134           2post       2post       ['fmap', 'func']
10332           1pre        1pre        ['anat', 'fmap', 'func']
10332           2post       2post       ['fmap', 'func']
10570           1pre        1pre        ['anat', 'fmap', 'func']
10570           2post       2post       ['fmap', 'func']
```

The `nipoppy status` prints out a summary of the study, including the number of participants who are in BIDS or have completed a pipeline.

```console
$ nipoppy status --dataset nipoppy_study
```

For now, the study only has BIDS data:

```{code-block}
:caption: Table in `nipoppy status` output
     Participant counts by session at each Nipoppy checkpoint
            ╷             ╷              ╷               ╷
 session_id │ in_manifest │ in_pre_reorg │ in_post_reorg │ in_bids
════════════╪═════════════╪══════════════╪═══════════════╪═════════
    1pre    │      9      │      0       │       0       │    9
   2post    │      9      │      0       │       0       │    9
            ╵             ╵              ╵               ╵
```

## Step 2: Modify the global configuration file

The `nipoppy init` command created the configuration file at `nipoppy_study/global_config.json`. This file may need to be updated with information specific to your computing environment. Initially, it will look like this:

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
    - `"null"` if you have MRIQC installed locally ("baremetal" install)
- If your group uses a shared directory for storing container image files, you can replace the value of `"[[NIPOPPY_DPATH_CONTAINERS]]"` by the full path to that shared directory. For example:
    ```json
    "SUBSTITUTIONS": {
        "_comment": "Self-references like NIPOPPY_DPATH_CONTAINERS are resolved from the layout at runtime, making them layout-aware",
        "[[NIPOPPY_DPATH_CONTAINERS]]": "<PATH_TO_SHARED_DIRECTORY>",
        "[[HPC_ACCOUNT_NAME]]": ""
    },
    ```
    - Alternatively, you can create a symlink from {{dpath_containers}} to that directory (then this line in the configuration can be deleted) (recommended).

## Step 3: Install the MRIQC pipeline into the study

The following command can be used to check which pipelines can be run with the study:
```console
$ nipoppy pipeline list --dataset nipoppy_study
```

The output says that there are no available pipelines to be run:
```
INFO     No available bidsification pipelines
INFO     No available processing pipelines
INFO     No available extraction pipelines
```

That is because a newly initialized Nipoppy study does not contain any pipelines. Pipeline configuration files are available on the [Zenodo data repository](https://zenodo.org/search?q=metadata.subjects.subject%3A%22Nipoppy%22&l=list&p=1&s=10&sort=bestmatch) and can be searched for directly from your terminal using the command `nipoppy pipeline search`. The [configuration files for MRIQC](https://zenodo.org/records/15306682) can be downloaded by running the following:
```{code-block} console
$ nipoppy pipeline install --dataset nipoppy_study {{zenodo_id_mriqc_23_1_0}}
```

When running `nipoppy pipeline install`, if using a container engine, you will be asked if you would like to download the MRIQC container. If you do not already have a download of the container, type `y` and press `Enter` to do so. The download/building process may take ~10 minutes. Apptainer or Singularity container images will be downloaded as `mriqc_23.1.0.sif` inside the container store directory (i.e., `nipoppy_study/containers` or the custom path you set in the `global_config.json` file). Docker images are managed centrally and so will not be downloaded to the study.

The pipeline installation process will add a `TEMPLATEFLOW_HOME` pipeline variable to the `nipoppy_study/global_config.json` file:

```
INFO     Adding 1 variable(s) to the global config file:
INFO             TEMPLATEFLOW_HOME       Path to the directory where TemplateFlow will store templates (can be empty)
```

Open `nipoppy_study/global_config.json` and set `TEMPLATEFLOW_HOME` to a meaningful location.

```{code-block} json
:emphasize-lines: 6
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {},
        "PROCESSING": {
            "mriqc": {
                "23.1.0": {
                    "TEMPLATEFLOW_HOME": null
                }
            }
        },
        "EXTRACTION": {}
    },
```

In general, we recommend using a shared directory within your research group for all Templateflow files, but you can also set it to something like `"[[NIPOPPY_DPATH_ROOT]]/templateflow"` (`[[NIPOPPY_DPATH_ROOT]]` will be resolved to the full path of the `nipoppy_study` directory at runtime). This directory will be created at runtime by Nipoppy if it does not exist -- you do not need to create it yourself.

## Step 4: Run MRIQC on a single participant and session

Use `nipoppy process` to run MRIQC on a single participant and session. This could take around 15 minutes to complete.

```console
$ nipoppy process \
    --dataset nipoppy_study \
    --pipeline mriqc \
    --pipeline-version 23.1.0 \
    --participant-id 09114 \
    --session-id 1pre
```

Pipeline outputs are written to `nipoppy_study/derivatives/mriqc/23.1.0/output`:

```{code-block}
:caption: MRIQC output files
nipoppy_study/derivatives/mriqc/23.1.0/output/
├── dataset_description.json
├── logs
├── sub-09114
│   ├── figures
│   │   ├── sub-09114_ses-1pre_desc-background_T1w.svg
│   │   └── sub-09114_ses-1pre_desc-zoomed_T1w.svg
│   └── ses-1pre
│       └── anat
│           └── sub-09114_ses-1pre_T1w.json
└── sub-09114_ses-1pre_T1w.html
```

Log files can be found in `nipoppy_study/logs/process/mriqc-23.1.0`.

## Step 5: Track the pipeline processing status

Run `nipoppy track-processing` to determine the MRIQC processing status for each subject and session:

```console
$ nipoppy track-processing \
    --dataset nipoppy_study \
    --pipeline mriqc \
    --pipeline-version 23.1.0
```

The command will create an {term}`processing status file` at `nipoppy_study/derivatives/processing_status.tsv`. This file should have a `SUCCESS` status (last column) for participant `09114` session `ses-1pre`, and `FAIL` statuses in every other row, like this:

```
participant_id  bids_participant_id     session_id  pipeline_name   pipeline_version    pipeline_step   bids_session_id     status
09114           sub-09114               1pre        mriqc           23.1.0              default         ses-1pre            SUCCESS
09114           sub-09114               2post       mriqc           23.1.0              default         ses-2post           FAIL
09160           sub-09160               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
09160           sub-09160               2post       mriqc           23.1.0              default         ses-2post           FAIL
09260           sub-09260               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
09260           sub-09260               2post       mriqc           23.1.0              default         ses-2post           FAIL
09300           sub-09300               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
09300           sub-09300               2post       mriqc           23.1.0              default         ses-2post           FAIL
09380           sub-09380               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
09380           sub-09380               2post       mriqc           23.1.0              default         ses-2post           FAIL
09381           sub-09381               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
09381           sub-09381               2post       mriqc           23.1.0              default         ses-2post           FAIL
10134           sub-10134               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
10134           sub-10134               2post       mriqc           23.1.0              default         ses-2post           FAIL
10332           sub-10332               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
10332           sub-10332               2post       mriqc           23.1.0              default         ses-2post           FAIL
10570           sub-10570               1pre        mriqc           23.1.0              default         ses-1pre            FAIL
10570           sub-10570               2post       mriqc           23.1.0              default         ses-2post           FAIL
```

Running `nipoppy status --dataset nipoppy_study` again will show a new column for the MRIQC pipeline showing that one participant has completed processing for the first session:

```{code-block}
:caption: Table in `nipoppy status` output
          Participant counts by session at each Nipoppy checkpoint
            ╷             ╷              ╷               ╷         ╷
            │             │              │               │         │  mriqc
            │             │              │               │         │ 23.1.0
 session_id │ in_manifest │ in_pre_reorg │ in_post_reorg │ in_bids │ default
════════════╪═════════════╪══════════════╪═══════════════╪═════════╪═════════
    1pre    │      9      │      0       │       0       │    9    │    1
   2post    │      9      │      0       │       0       │    9    │    0
            ╵             ╵              ╵               ╵         ╵
```

The {term}`processing status file` can also be uploaded to the [Neurobagel digest dashboard](https://digest.neurobagel.org/), which will produce interactive visualizations of pipeline processing statuses.

Finally, this file can be used directly as input to the [Neurobagel CLI](https://neurobagel.org/user_guide/cli/) when generating participant-level metadata about processing pipeline results.

## Step 6 (optional): Run MRIQC on the rest of the study

Use `nipoppy process` without the participant and session flags to process the rest of the study (in a loop). This will skip the participant-session that has previously been run successfully.

```console
$ nipoppy process \
    --dataset nipoppy_study \
    --pipeline mriqc \
    --pipeline-version 23.1.0
```

Then, run the tracking command again to update the {term}`processing status file`:

```console
$ nipoppy track-processing \
    --dataset nipoppy_study \
    --pipeline mriqc \
    --pipeline-version 23.1.0
```

```{note}
For this dataset specifically, MRIQC will fail on all `ses-2post` sessions because they do not have anatomical data.
```

And that's it! You have successfully run MRIQC on a BIDS dataset using Nipoppy!

While other pipelines may have different pipeline specific configurations to be set up, the general workflow described in this tutorial can be adapted to any other pipeline run with Nipoppy.
