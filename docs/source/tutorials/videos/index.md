# "How to" tutorial video series

Learn all about the Nipoppy toolbox and its protocol and experience a full usage of all Nipoppy functionalities by following our tutorial series!

This tutorial series is meant to give you a hands-on experience of the Nipoppy toolbox. Please have Nipoppy installed on your device (see [Installation](../../overview/installation.md)) and have our example dataset ready:

```{code-block} console
$ git clone https://github.com/nipoppy/tutorial-dataset.git
```

or visit the [GitHub repo](https://github.com/nipoppy/tutorial-dataset) and download the data without using `git`. We show in the videos how to!

```{attention}
The Nipoppy version used in the tutorial videos was 0.4.5. Console output as well as certain flags could have changed between this version and newer versions. Please consult the [release notes](../../other/changelog.rst) for details. E.g., the `--regenerate` flag for the `track-curation` command is deprecated.
```

## 1. nipoppy init

In this tutorial we will cover how to create a new Nipoppy study. More concretely, we will
- run the [`nipoppy init`](../../reference/cli_reference/init.rst) command
- discover the directories that follow the Nipoppy specification
- explore the [`nipoppy status`](../../reference/cli_reference/status.rst) command
- modify the content of the [`manifest.tsv`](../../explanations/manifest.md) file according to our study
- and run the [`nipoppy track-curation`](../../reference/cli_reference/track_curation.rst) command

Duration: 7:43m

<iframe width="560" height="315" src="https://www.youtube.com/embed/POHCcIHEezE?si=HYgD75sE0kwY0wIu" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## 2. nipoppy pipeline

In this tutorial we will cover how to install a pipeline in a Nipoppy study. More concretely, we will
- explore the [`nipoppy pipeline`](../../reference/cli_reference/pipeline_install.rst) subcommands
- learn how to share containers
- set pipeline configurations

Duration: 6:31m

<iframe width="560" height="315" src="https://www.youtube.com/embed/BSHHArTBx04?si=FbUCBkCIJokKrnNA" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

[Go here to find more info about docker support](https://nipoppy.readthedocs.io/en/latest/how_to_guides/docker/index.html)

## 3. nipoppy reorg

In this tutorial we will cover how to reorganize imaging sourcedata. More concretely, we will
- explore the sourcedata directory
- run the [`nipoppy reorg`](../../reference/cli_reference/reorg.rst) command
- and look at the {term}`curation_status.tsv <curation status file>` file

Duration: 6:06m

<iframe width="560" height="315" src="https://www.youtube.com/embed/udA0FxuMJoc?si=miTxSK9MTpbgvWbl" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## 4. nipoppy bidsify

In this tutorial we will cover how to bidsify imaging sourcedata. More concretely, we will
- install the [dcm2bids](https://unfmontreal.github.io/Dcm2Bids/3.2.0/) pipeline
- explore the [`nipoppy bidsify`](../../reference/cli_reference/bidsify.rst) command
- run [`nipoppy bidsify`](../../reference/cli_reference/bidsify.rst) on our imaging sourcedata

Duration: 8:31m

<iframe width="560" height="315" src="https://www.youtube.com/embed/m0PMMMiKF6w?si=GS6uUiCB9VTWnHQe" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## 5. nipoppy process

In this tutorial we will cover how to run processing pipelines on imaging data. More concretely, we will
- check the prerequisites to run [mriqc](https://mriqc.readthedocs.io/en/stable/index.html) on our study
- execute the [`nipoppy process`](../../reference/cli_reference/process.rst) command
- explore the created output

Duration: 5:26m

<iframe width="560" height="315" src="https://www.youtube.com/embed/9FDdf1BHz0w?si=HK5wj1zQe8GfRsgj" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## 6. nipoppy track-processing

In this tutorial we will cover how to track the processing status of our imaging data with Nipoppy. More concretely, we will
- run the [`nipoppy track-processing`](../../reference/cli_reference/track_processing.rst) command
- get to know the {term}`processing_status.tsv <processing status file>` file
- and explore the [Neurobagel digest dashboard](https://digest.neurobagel.org/)

Duration: 4:21m

<iframe width="560" height="315" src="https://www.youtube.com/embed/9lEsoZrcthU?si=wLno8A99295H-lNc" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

## 7. nipoppy extract

In this tutorial we will cover how to extract imaging-derived phenotypes (IDPs) from our imaging data by running the [`nipoppy extract`](../../reference/cli_reference/extract.rst) command.

Duration: 3:55m

<iframe width="560" height="315" src="https://www.youtube.com/embed/MR42po3pr8w?si=NFRnPXRn0Uovp8Ss" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
