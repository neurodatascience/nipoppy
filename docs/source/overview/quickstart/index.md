# Quickstart

This page is intended to give you a quick first run through the curation and processing stages with Nipoppy using real DICOM data from an example dataset.

```{important}
See the [Installation instructions](../installation.md) first if you have not yet installed Nipoppy and do not forget to activate your Nipoppy environment.
```

## Download the example dataset

```{code-block} console
$ git clone https://github.com/nipoppy/tutorial-dataset.git
```

## Initializing a new study

**1.** Initialize a Nipoppy study:
```{code-block} console
$ nipoppy init --dataset my-example-study
```

```{important}
The newly created directory tree follows the Nipoppy specification. Other Nipoppy commands expect all these directories to exist -- they will throw an error if that is not the case.
```

**2.** Move the example dataset and files into your Nipoppy study:
```{code-block} console
$ mv tutorial-dataset/manifest.tsv my-example-study
$ mv tutorial-dataset/reorg/* my-example-study/sourcedata/imaging/pre_reorg
$ mv tutorial-dataset/bidsify/dcm2bids_config.json my-example-study/code
$ mv tutorial-dataset/bidsify/participants.tsv tutorial-dataset/bidsify/dataset_description.json my-example-study/bids
```

See the [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/3.2.0/tutorial/first-steps/#building-the-configuration-file) docs for info about the `dcm2bids_config.json` and the [BIDS](https://bids.neuroimaging.io/getting_started/tutorials/annotation.html) docs for info about valid BIDS dataset requirements.


**3.** Change directory into your Nipoppy study:
```{code-block} console
$ cd my-example-study
```

## Creating/modifying required files

(customizing-config)=
### Customizing the global configuration file

The global configuration file at {{fpath_config}} starts out like this:
```{literalinclude} ../../_inserts/sample_study_config.json5
---
linenos: True
language: json
---
```

**Fields that may need to be modified depending on your setup:**
- If you are on a system that uses Singularity instead of Apptainer, you need to change `CONTAINER_CONFIG` -> `COMMAND` to `"singularity"` instead of `"apptainer"`
- If your group uses a shared directory for storing container image files, you can replace `"[[NIPOPPY_DPATH_ROOT]]/containers"` by the full path to that shared directory. Alternatively, you can create a symlink from {{dpath_containers}} to that directory (then this line in the configuration can be deleted).

### [Customizing the manifest.tsv file](../../how_to_guides/manifest/index.md)

The example {term}`manifest file` created at {{fpath_manifest}} by `nipoppy init` always looks like this:
```{literalinclude} ../../../../nipoppy/data/examples/sample_manifest.tsv
---
linenos: True
---
```

**For our example study, we changed it to this:**

(This is the {term}`manifest file` you copied from the tutorial-dataset; you will always have to modify it according to your study setup)
```{literalinclude} example-dataset_manifest.tsv
---
linenos: True
---
```

## Prepare sourcedata for bidsification

**1.** Reorganize the sourcedata to simplify bidsification:
```{code-block} console
$ nipoppy reorg
```

**2.** Check the study status:
```{code-block} console
$ nipoppy status
```

Expected output:
```
...
               Participant counts by session at each Nipoppy checkpoint
                      ╷             ╷              ╷               ╷
           session_id │ in_manifest │ in_pre_reorg │ in_post_reorg │ in_bids
          ════════════╪═════════════╪══════════════╪═══════════════╪═════════
               BL     │      4      │      4       │       4       │    0
                      ╵             ╵              ╵               ╵
...
```

## [Pipeline setups](../../how_to_guides/pipeline_install/index.md)

A newly initialized Nipoppy study does not contain any pipeline setups or containers.

### dcm2bids example

**1.** Search for the desired pipeline:
```{code-block} console
$ nipoppy pipeline search dcm2bids
```
**2.** Copy the Zenodo ID of version 3.2.0 of the pipeline ({{zenodo_id_dcm2bids_3_2_0}} at the time of writing) and run:
```{code-block} console
$ nipoppy pipeline install {{zenodo_id_dcm2bids_3_2_0}}
```
**3.** Choose to install the container as well or not: `y/n`

**4.** Check pipeline installation:
```{code-block} console
$ nipoppy pipeline list
```

Expected output:
```
...

INFO     Available bidsification pipelines and versions:
INFO            - dcm2bids (3.2.0)

...
```

## BIDSify the sourcedata

```{note}
Please see the [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/3.2.0/tutorial/first-steps/) documentation to know what dcm2bids does and how it works.

Usually you would start with running `nipoppy bidsify` with the first `--pipeline-step` (e.g. `prepare`). For `dcm2bids` this step would run the `dcm2bids_helper` in order to extract information from the dicom headers to create a `dcm2bids_config.json`. We already provided you with a `dcm2bids_config.json`, so we will skip this step here.
```

**1.** Replace the placeholder for `"DCM2BIDS_CONFIG_FILE"` in the `global_config,json` with the path to your code directory:
```yaml
{
    # ...
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {
            "dcm2bids": {
                "3.2.0": {
                    "DCM2BIDS_CONFIG_FILE": "[[NIPOPPY_DPATH_ROOT]]/code/dcm2bids_config.json"
                }
            }
        }
    }
    # ...
}
```

**2.** Run bidsification:
```{code-block} console
$ nipoppy bidsify --pipeline dcm2bids --pipeline-step convert
```

**3.** Track the curation status:
```{code-block} console
$ nipoppy track-curation
```

The curation status file can be found at {{fpath_curation_status}}.

**4.** Check the study status:
```{code-block} console
$ nipoppy status
```

Expected output:
```
...
               Participant counts by session at each Nipoppy checkpoint
                      ╷             ╷              ╷               ╷
           session_id │ in_manifest │ in_pre_reorg │ in_post_reorg │ in_bids
          ════════════╪═════════════╪══════════════╪═══════════════╪═════════
               BL     │      4      │      4       │       4       │    4
                      ╵             ╵              ╵               ╵
...
```


## [Run a processing pipeline on BIDS data](../../how_to_guides/pipeline_run/index.md)

**1.** Search and install the MRIQC pipeline, version 23.1.0 (and if necessary the container) as described above.<br>

**2.** Check the pipeline installation:
```{code-block} console
$ nipoppy pipeline list
```

Expected output:
```
...

INFO     Available bidsification pipelines and versions:
INFO            - dcm2bids (3.2.0)
INFO     Available processing pipelines and versions:
INFO            - mriqc (23.1.0)

...
```
**3.** Create a new directory in the Nipoppy study root called `templateflow` (required by MRIQC, see [TemplateFlow](https://www.templateflow.org/) docs):
```{code-block} console
$ mkdir templateflow
```

**4.** Replace the placeholders (here: the templateflow path) in the `global_config.json`:

```yaml
{
    # ...
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {
            "dcm2bids": {
                "3.2.0": {
                    "DCM2BIDS_CONFIG_FILE": "[[NIPOPPY_DPATH_ROOT]]/code/dcm2bids_config.json"
                }
            }
        },
        "PROCESSING": {
            "mriqc": {
                "23.1.0": {
                    "TEMPLATEFLOW_HOME": "[[NIPOPPY_DPATH_ROOT]]/templateflow"
                }
            }
        },
        "EXTRACTION": {}
    }
    # ...
}
```

```{note}
You can also point to an already existing shared templateflow directory, if you have access to one.
```

**5.** Run MRIQC on one participant:
```{code-block} console
$ nipoppy process --pipeline mriqc --participant-id ED01
```

**6.** Track the processing status:
```{code-block} console
$ nipoppy track-processing --pipeline mriqc
```

The processing status file can be found at {{fpath_processing_status}}.

**7.** Check the study status:
```{code-block} console
$ nipoppy status
```

Expected output:
```
...
                           Participant counts by session at each Nipoppy checkpoint
                      ╷             ╷              ╷               ╷         ╷
                      │             │              │               │         │  mriqc
                      │             │              │               │         │  23.1.0
           session_id │ in_manifest │ in_pre_reorg │ in_post_reorg │ in_bids │ default
          ════════════╪═════════════╪══════════════╪═══════════════╪═════════╪══════════
               BL     │      4      │      4       │       4       │    4    │    1
                      ╵             ╵              ╵               ╵         ╵
...
```

```{tip}
You can also upload your processing status file to the Neurobagel digest dashboard at [https://digest.neurobagel.org/](https://digest.neurobagel.org/) to get a nice summary and visualization of your work!
```

## Next steps

Repeat the steps of the previous section with a processing pipeline such as `fmriprep` to consequently use the `nipoppy extract` command with the `fs_stats` pipeline. Try it out, it will be fun!
