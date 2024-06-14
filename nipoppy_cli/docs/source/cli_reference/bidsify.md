# `nipoppy convert`

```{note}
This command calls the {py:class}`nipoppy.workflows.bids_conversion.BidsConversionRunner` class from the Python {term}`API` internally.

Logfiles for this command can be found in {{dpath_logs}}`/bids_conversion`.
```

```{argparse}
---
ref: nipoppy.cli.parser.get_global_parser
prog: nipoppy
nodefault: true
path: bidsify
---
```
