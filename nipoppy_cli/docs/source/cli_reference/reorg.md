# `nipoppy reorg`

```{note}
This command calls the {py:class}`nipoppy.workflows.dicom_reorg.DicomReorgWorkflow` class from the Python {term}`API` internally.

Logfiles for this command can be found in {{dpath_logs}}`/dicom_reorg`.
```

```{argparse}
---
ref: nipoppy.cli.parser.get_global_parser
prog: nipoppy
nodefault: true
path: reorg
---
```
