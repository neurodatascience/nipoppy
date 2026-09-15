# Parallelizing pipeline runs

```{toctree}
---
hidden:
includehidden:
---
HPC job scheduling<hpc_scheduler>
Local parallelization<local_parallelization>
```

By default, [`nipoppy bidsify`](<project:../../reference/cli_reference/bidsify.rst>), [`nipoppy process`](<project:../../reference/cli_reference/process.rst>), and [`nipoppy extract`](<project:../../reference/cli_reference/extract.rst>) will run every participant-session pair sequentially. This can be very slow for large studies and suboptimal if more computational resources are available. The following guides show how pipeline runs can be parallelized for different computer/server setups.

::::{grid} 2
:::{grid-item-card}  [HPC systems](hpc_scheduler)
Automatic job submission on some {term}`HPC` systems.
:::
:::{grid-item-card}  [Local parallelization](local_parallelization)
Tips for local parallelization on systems with no job schedulers.
:::
::::
