# Organizing raw imaging data

To use Nipoppy to convert imaging data to the {term}`BIDS` standard, the data first needs to be organized in a way that Nipoppy can understand. Since different studies typically follow their own methods for raw imaging data organization, this step may require the creation of a custom mapping file or the overriding of some existing methods in the Python API.

## Summary

### Prerequisites

- A Nipoppy dataset with a valid configuration file and an accurate manifest
    - See the [Quickstart guide](../quickstart.md) for instructions on how to set up a new dataset
- Raw imaging data in {{dpath_raw_imaging}}
    - See <project:populating.md>

### Data directories

| Directory | Content description |
|---|---|
| {{dpath_raw_imaging}} | **Input** -- {{content_dpath_raw_imaging}} |
| {{dpath_sourcedata}} | **Output** -- {{content_dpath_sourcedata}} |

### Commands

- Command-line interface: [`nipoppy reorg`](<project:../cli_reference/reorg.md>)
- Python API: {class}`nipoppy.workflows.DicomReorgWorkflow`

## Running the data reorganization tool

This step moves raw imaging data from the {{dpath_raw_imaging}} directory to the {{dpath_sourcedata}} directory. Nipoppy can automatically handle two common cases of input data organization:
1. Participant-level directories with nested session-level directories
    - E.g., {{dpath_raw_imaging}}`/001/ses-1`
    - This is the default behaviour
2. Session-level directories with nested participant-level directories
    - E.g., {{dpath_raw_imaging}}`/ses-1/001`
    - This can be enabled by setting `"DICOM_DIR_PARTICIPANT_FIRST"` to `"false"` in the {ref}`configuration file <config-schema>`

If the raw imaging data is not organized in any of these two structures, a custom comma-separated file can be created to map each unique participant-session pair to a directory path (relative to {{dpath_raw_imaging}}). This path to this mapping file must be specified in the `"DICOM_DIR_MAP_FILE"` in the {ref}`configuration file <config-schema>`. See the {ref}`schema reference <dicom-dir-map-schema>` for more information.

Here is an example file for a dataset that does not use the `ses-` prefix for sessions:

```{csv-table}
---
file: ../../../nipoppy/data/examples/sample_dicom_dir_map.csv
header-rows: 1
---
```

````{admonition} Raw content of the example DICOM directory mapping file
---
class: dropdown
---
```{literalinclude} ../../../nipoppy/data/examples/sample_dicom_dir_map.csv
---
linenos: True
language: csv
---
```
````

All files in participant-session subdirectories (and sub-subdirectories, if applicable) will be reorganized under {{dpath_sourcedata}}`/sub-<PARTICIPANT_ID>/ses-<SESSION_ID>`, creating a flat list of files. By default, the output files will be relative symbolic links ("symlinks") to avoid duplication of files.

```{note}
More granular customization can also be achieved for both the input file paths and the output file names, see [](#customizing-dicom-reorg).
```

### Using the command-line interface

```console
$ nipoppy reorg --dataset-root <DATASET_ROOT>
```

See the [CLI reference page](<project:../cli_reference/reorg.md>) for more information on optional arguments (e.g., reading DICOM headers to check the image type, and copying files instead of creating symlinks).

```{note}
Log files for this command will be written to {{dpath_logs}}`/dicom_reorg`
```

### Using the Python API

```python
from nipoppy.workflows import DicomReorgWorkflow

dpath_root = "."  # replace by path to dataset root directory
workflow = DicomReorgWorkflow(dpath_root=dpath_root)
workflow.run()
```

See the API reference for {class}`nipoppy.workflows.DicomReorgWorkflow` for more information on optional arguments (they correspond to the ones for the [CLI](<project:../cli_reference/reorg.md>)).

(customizing-dicom-reorg)=
#### Customizing input and output file paths

There may be datasets where the raw imaging files are not organized in a participant-session directory. An example of this would a dataset whose raw DICOM files are in archives, like so:
```{literalinclude} ./file_trees/custom_dicom_reorg-before.txt
:class: no-copybutton
```

In this case, using a DICOM directory mapping file as described above is not enough, since files from different imaging sessions are in the same directory.

The {class}`nipoppy.workflows.DicomReorgWorkflow` class exposes two functions for finer control of input paths and output filenames:
- {func}`nipoppy.workflows.DicomReorgWorkflow.get_fpaths_to_reorg` can be overridden to map a participant ID and session ID to a list of absolute filepaths to be reorganized
- {func}`nipoppy.workflows.DicomReorgWorkflow.apply_fname_mapping` can be overridden to rename output files
  - Note: output files will still be in the {{dpath_sourcedata}}`/sub-<PARTICIPANT_ID>/ses-<SESSION_ID>` directory

Here is an example of custom imaging data reorganization script:
```{literalinclude} ./scripts/custom_dicom_reorg.py
---
language: python
---
```

Running this script on the data shown above will create the following organized files (by default symlinks):
```{literalinclude} ./file_trees/custom_dicom_reorg-after.txt
:class: no-copybutton
```

## Next steps

Now that the raw imaging data has been organized in a standardized participant-session structure, it is ready for [BIDS conversion](<project:bids_conversion.md>)!