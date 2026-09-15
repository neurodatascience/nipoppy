# Installing a pipeline

This guide shows how to search for and install pipelines that can be run with Nipoppy.

## Finding an available pipeline

Nipoppy pipeline configuration files are available on [Zenodo](https://zenodo.org/search?q=metadata.subjects.subject%253A%22Nipoppy%22), a research data repository. You can search for pipelines on the Zenodo website itself, or use the `nipoppy pipeline search` command on the terminal directly.

To show all available pipelines, run the command without any argument:

```console
$ nipoppy pipeline search
```

Here is the (trimmed) output obtained at the time of writing:

<!-- TODO auto-generate this table when building docs? -->

```
            ╷                               ╷
  Zenodo ID │             Title             │                         Description
 ═══════════╪═══════════════════════════════╪═════════════════════════════════════════════════════════════
  15299437  │ xcp-d postprocessing pipeline │         Config and Tracker files for running xcp-d
  15306681  │       freesurfer-7.3.2        │  Nipoppy configuration files for freesurfer 7.3.2 pipeline
            │                               │                       (tracking only)
  15306657  │        dcm2bids-3.1.0         │   Nipoppy configuration files for dcm2bids 3.1.0 pipeline
  15306667  │        static_FC-0.1.0        │  Nipoppy configuration files for static_FC 0.1.0 pipeline
  15306677  │        fmriprep-24.1.1        │  Nipoppy configuration files for fmriprep 24.1.1 pipeline
  15271392  │   Fmriprep Ciftify Pipeline   │        Config and Tracker files for running Ciftify
  15306675  │        fmriprep-23.1.3        │  Nipoppy configuration files for fmriprep 23.1.3 pipeline
  15306661  │        dcm2bids-3.2.0         │   Nipoppy configuration files for dcm2bids 3.2.0 pipeline
  15306679  │       freesurfer-6.0.1        │  Nipoppy configuration files for freesurfer 6.0.1 pipeline
            │                               │                       (tracking only)
  15306685  │        qsiprep-0.23.0         │   Nipoppy configuration files for qsiprep 0.23.0 pipeline
            ╵                               ╵
```

```{tip}
By default this shows the 10 results with the highest download counts. You can use the `--size` option to display more.
```

It is also possible to search for a specific pipeline, for example [fMRIPrep](https://fmriprep.org):

```console
$ nipoppy pipeline search fmriprep
```

```{tip}
See [this guide](https://help.zenodo.org/guides/search/) for the full Zenodo search syntax. You may need to add quotes around the query string if it contains spaces or other special characters.
```

At the time of writing, the above command prints the following table (trimmed):

```
            ╷                           ╷
  Zenodo ID │           Title           │                       Description
 ═══════════╪═══════════════════════════╪══════════════════════════════════════════════════════════
  15306677  │      fmriprep-24.1.1      │ Nipoppy configuration files for fmriprep 24.1.1 pipeline
  15306675  │      fmriprep-23.1.3      │ Nipoppy configuration files for fmriprep 23.1.3 pipeline
  15306673  │      fmriprep-20.2.7      │ Nipoppy configuration files for fmriprep 20.2.7 pipeline
  15271392  │ Fmriprep Ciftify Pipeline │       Config and Tracker files for running Ciftify
            ╵                           ╵
```

## Installing a pipeline into a Nipoppy study

Once you know the Zenodo ID of the pipeline we wish to use, you can install it directly from Zenodo using the `nipoppy pipeline install` command. Here we install fMRIPrep version 24.1.1.

```console
$ nipoppy pipeline install --dataset <NIPOPPY_STUDY_ROOT> 15306677
```

````{tip}
You can also install a pipeline from a directory on disk with the same command:

```console
$ nipoppy pipeline install --dataset <NIPOPPY_STUDY_ROOT> <PATH_TO_PIPELINE_CONFIG_DIRECTORY>
```
````


Running this command will download all pipeline configuration files for fMRIPrep 24.1.1 into the Nipoppy study. Depending on the **pipeline type**, the files will be written to different locations:
- BIDSification pipelines: {{dpath_pipelines}}`/bidsification`
- Processing pipelines: {{dpath_pipelines}}`/processing`
- Extraction pipelines: {{dpath_pipelines}}`/extraction`

<!-- TODO "see this page for the difference between these pipeline types" -->

## Updating pipeline variables in the global config file (if needed)

Some pipelines require user-specified paths to files that Nipoppy is not aware of, for example a FreeSurfer license file or other configuration files. Nipoppy handles these cases through the use of **pipeline variables** and allows users to set them in the global config file. For example, when installing fMRIPRep 24.1.1 (Zenodo ID: 15306677), we see the following output:

```
INFO     Adding 2 variable(s) to the global config file:
INFO             FREESURFER_LICENSE_FILE Path to FreeSurfer license file
INFO             TEMPLATEFLOW_HOME       Path to the directory where TemplateFlow will store templates (can be empty)
```

These two pipeline variables have been added to the `"PIPELINE_VARIABLES"` field in the global config file:

```json
    "PIPELINE_VARIABLES": {
        "BIDSIFICATION": {},
        "PROCESSING": {
            "fmriprep": {
                "24.1.1": {
                    "FREESURFER_LICENSE_FILE": null,
                    "TEMPLATEFLOW_HOME": null
                }
            }
        },
        "EXTRACTION": {}
    },
```

The `null` values have to be set before running the pipeline.
