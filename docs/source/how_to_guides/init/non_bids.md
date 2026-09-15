# Initializing a new study starting with non-BIDS data

This guide shows how to initialize a new Nipoppy study with source imaging data that consists of DICOM files or non-{term}`BIDS` NIfTI files.

The first step is to create an empty Nipoppy study using the [`nipoppy init`](../../reference/cli_reference/init) command:

```console
$ nipoppy init --dataset <PATH_TO_NEW_STUDY>
```

This will create the directory tree and copy an [example manifest](https://github.com/nipoppy/nipoppy/blob/main/nipoppy/data/examples/sample_manifest.tsv) and an [example global configuration file](https://github.com/nipoppy/nipoppy/blob/main/nipoppy/data/examples/sample_global_config.json5) into it.

```{attention}
It is extremely unlikely that the example {term}`manifest <manifest file>` accurately represents your study, so you will have to generate one yourself. See [this guide](../manifest/index) for more details.

You may also need to modify the default [global configuration file](../../reference/config.md), depending on your setup.
```

Then the raw imaging data should be added (symlinked/copied/moved) to {{dpath_pre_reorg}} and reorganized with [`nipoppy reorg`](../../reference/cli_reference/reorg) to prepare it for BIDS conversion. See [this guide](../reorganize_sourcedata/index.md) for more information.
