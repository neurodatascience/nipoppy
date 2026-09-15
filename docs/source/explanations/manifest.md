# The manifest file

The Nipoppy manifest file is a TSV file that contains *expected availability* information about the participants, visits, sessions, and imaging datatypes available in a study.

Here is an example manifest file:

```{csv-table}
---
file: ../../../nipoppy/data/examples/sample_manifest.tsv
header-rows: 1
delim: tab
---
```

## Inspiration

Those who are familiar with {term}`BIDS` might notice that this file seems similar to the `participants.tsv` file in BIDS datasets. Indeed, the manifest file is heavily inspired by BIDS' `participant.tsv`, though there are some notable differences:
* The manifest can contain longitudinal information, i.e. a single participant can have multiple rows representing different (imaging or non-imaging visits).
* The manifest file is **mandatory** (`participants.tsv` is optional).

## In the Nipoppy protocol

<img alt="Nipoppy protocol" src="../_static/img/nipoppy_protocol.jpg" width=850px>

Conceptually, the manifest file creation is the first step in the Nipoppy protocol (once the Nipoppy study has been created).

This is where the "Curate" phase of the protocol begins: using information obtained in the "Capture" phase (which may be messy or non/semi-standardized, imaging and/or non-imaging), we build a source of ground truth information that will be critical for knowing which participants and visits (imaging or non-imaging) are expected to exist in the study.

Following the [Nipoppy principle](../overview/why_nipoppy/principles) of specifying the sequence or tasks whenever possible, the Nipoppy protocol stipulates that the manifest should ideally be created before any other step (BIDSification, processing, etc.) is taken.

## With the Nipoppy tools

The manifest is considered the ground truth of what data should be available for a given study: any participant/visit that is not present in the manifest is ignored by the Nipoppy software tools, regardless of whether they have data on disk.

The [`nipoppy status` command](../reference/cli_reference/status) prints a summary table that includes counts for the number of participants that are in the manifest for each imaging session.

The [`nipoppy track-curation` command](../reference/cli_reference/track_curation) will check whether each participant-session pair listed in the manifest file has imaging data in each of the three data curation stages:

- Arbitrarily organized sourcedata in {{dpath_pre_reorg}}
- Sourcedata ready for BIDS conversion in {{dpath_post_reorg}}
- Data organized according to BIDS in {{dpath_bids}}

This information is stored in the {term}`curation status file`, which is used by the [`nipoppy bidsify`](../reference/cli_reference/bidsify), [`nipoppy process`](../reference/cli_reference/process) and [`nipoppy extract`](../reference/cli_reference/extract) commands to determine which participants and sessions a pipeline should be run on.
