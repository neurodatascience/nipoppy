# Parallelizing pipeline runs on HPC systems

This guide shows how to parallelize pipeline runs on {term}`HPC` systems that use job schedulers supported by Nipoppy.

Currently, we have built-in support for the [Slurm](https://slurm.schedmd.com/overview.html) and [SGE](https://en.wikipedia.org/wiki/Oracle_Grid_Engine) job schedulers.
However, it is possible to [manually add another job scheduler](#support-for-other-job-schedulers).

```{important}
Although the default template job script is designed to work with minimal user configuration, each {term}`HPC` system is different, and some may require different/additional parameters to be set. See the [Further customization](#further-customization) section for how deeper configuration can be achieved.

If the default Slurm/SGE configurations do not work for you, please consider [opening an issue on our GitHub repository](https://github.com/nipoppy/nipoppy/issues/new/choose) so that we can improve our HPC support.
```

## Configuring main HPC options

### Global settings

The default global configuration file has three {term}`HPC`-related fields that should be updated as needed:

```{literalinclude} ../../_inserts/sample_study_config.json5
---
linenos: True
language: json
emphasize-lines: 7,20-29,30
---
```

#### `HPC_PREAMBLE`

`HPC_PREAMBLE` is a list of Bash commands that should executed at the beginning of **every** job.
Importantly, there should be a command for activating the Nipoppy Python environment.
* For {term}`venv` environments, the command would be something like this: `"source <PATH_TO_NIPOPPY_VENV>/bin/activate"`
* For {term}`conda` environments, the command would instead be something like this: `"source ~/.bashrc; conda activate <NIPOPPY_ENV_NAME>"`

#### `[[HPC_ACCOUNT_NAME]]`

The value for the `[[HPC_ACCOUNT_NAME]]` field in the `SUBSTITUTIONS` dictionary should be set to the account name/ID the job will be associated with.
By default this will be passed as `--account-name` in Slurm systems and `-q` in SGE systems during job submission.
This can be left blank if these options are not needed.

```{attention}
If your HPC system needs flags other than `--account-name` or `-q` need to be set, you will have to modify the template job submission script: see the [Further customization](#further-customization) section for more information.
```

#### `HPC_QUEUE_LIMIT`

The maximum number of jobs allowed in the queue for a given user.
This limit is specific to your HPC system.
Set to `null` if there is no such limit, in which case all jobs will always be submitted.

### Pipeline-specific settings

Job time limit and CPU and memory requests can be configured separately for each pipeline via the HPC config file.
Look for this file inside the pipeline config directory at {{dpath_pipelines}}`/<PIPELINE_TYPE>/<PIPELINE_NAME>/<PIPELINE_VERSION>` -- it is most likely called `hpc.json` or `hpc_config.json` (see the pipeline's `config.json` file for the exact name)

The HPC config file should look similar to this:

```{literalinclude} ../../_inserts/hpc.json5
---
linenos: True
language: json
---
```

````{admonition} If the pipeline config directory has no HPC config file
---
class: dropdown
---

You can create an HPC config file manually by copying the content above into a new file called (for example) `hpc.json`.

You will also need to add an `"HPC_CONFIG_FILE"` field for each step in pipeline's `config.json` file:

```{literalinclude} ../../_inserts/config-extraction.json5
---
linenos: True
language: json
lines: 14-21
emphasize-lines: 6
---
```
````

Set the fields in the HPC config file as needed.
Set/leave as empty string if the field is not needed.

* `ACCOUNT`: **do not** modify this field -- the account name [should be set in the global configuration file](#hpc_account_name).
* `TIME`: time limit. Passed as `--time` in Slurm jobs and `-l h_rt` in SGE jobs.
* `CORES`: number of CPUs requested. Passed as `--cpus-per-task` in Slurm jobs and ignored in SGE jobs.
* `MEMORY`: amount of memory requested. Passed as `--mem` in Slurm jobs and `-l h_vmem` in SGE jobs.
* `ARRAY_CONCURRENCY_LIMIT`: maximum number of jobs in the array that can be run at the same time. Set as part of `--array` specification in Slurm jobs and passed as `--tc` in SGE jobs.

## Submitting HPC jobs via `nipoppy` commands

To run a pipeline on an HPC, use the `--hpc` option to specify the HPC job scheduler when running the [`nipoppy bidsify`](<project:../../reference/cli_reference/bidsify.rst>), [`nipoppy process`](<project:../../reference/cli_reference/process.rst>), or [`nipoppy extract`](<project:../../reference/cli_reference/extract.rst>) commands:

```console
$ nipoppy <SUBCOMMAND> \
    --dataset <NIPOPPY_STUDY_ROOT> \
    --pipeline <PIPELINE_NAME> \
    --hpc slurm
    # other desired options
    # ...
```

This will submit a job array (one job per participant/session to run) through the requested job scheduler.
Currently, only `'slurm'` and `'sge'` have built-in support, but it is possible to [add a different job scheduler](#support-for-other-job-schedulers).

```{tip}
We recommend submitting a single job (i.e. by specifying both `--participant-id` and `--session-id`) the first time you launch jobs on an HPC.
This will make it easier to troubleshoot if any problem occurs.
```

## Troubleshooting

Below are some troubleshooting tips that might be helpful if your jobs are submitted successfully but failing before pipeline processing begins.

Slurm/SGE log files are written to {{dpath_logs}}`/hpc`.
If you see an error message complaining about the `nipoppy` command not existing, it is likely that your [`HPC_PREAMBLE`](#hpc_preamble) does not have the right command(s) for activating your Nipoppy Python environment.

By default, the job script generated by Nipoppy is deleted upon successful job submission.
If you suspect that there is something wrong with the job script, rerun the `nipoppy` command you used to submit the job(s) with the `--keep-workdir` flag.
Then, the script can be found at {{dpath_pipeline_work}}`/run_queue.sh`.

```{attention}
Modifying {{dpath_pipeline_work}}`/run_queue.sh` will not have an effect on future job submissions.
Instead, you will need to modify the [template job script](#further-customization) itself.
```

## Further customization

All fields in the HPC config file are passed to the [Jinja](https://jinja.palletsprojects.com) template job script, which can be found at {{dpath_hpc}}`/job_script_template.sh`.

````{admonition} The default template job script
---
class: dropdown
---

```{literalinclude} ../../../../nipoppy/data/hpc/job_script_template.sh
---
linenos: True
language: bash
---
```
````

This template can be modified to hardcode job submission settings or to expose additional pipeline-specific configurations.

As an example, let's say we are interested in specifying the `--nice` option in Slurm jobs.

* To hardcode the same `--nice` value for all jobs/pipelines, add e.g., `#SBATCH --nice=10` in a new line near the beginning of the template script (outside of any `if` block).
* To expose `--nice` as a parameter that can be set independently for each pipeline, instead add the following block:
  ```bash
  {% if NICE %}
  #SBATCH --nice={{ NICE }}
  {%- endif %}
  ```
  Then set `"NICE"` in a new field (alongside `"TIME"`, `"CORE"` etc.) in a pipeline's HPC config file.

## Support for other job schedulers

Job scheduling support in the Nipoppy package relies on the [`pysqa`](https://pysqa.readthedocs.io/) package, which can handle several other job schedulers in addition to Slurm and SGE.

To add support for another job scheduler supported by `pysqa` (e.g., [Flux](https://flux.ly/)), follow these steps:

1. Navigate to {{dpath_hpc}}.
2. Create a `flux.yaml` file. Refer to the existing `slurm.yaml` and `sge.yaml` for what the content of that file should be.
3. Update `clusters.yaml` to add `flux` as an additional cluster.
4. Update `job_script_template.sh` to add a section for Flux configs.
5. You should now be able to run `nipoppy bidsify`/`process`/`extract` with `--hpc flux`.

See also the [`pysqa` documentation](https://pysqa.readthedocs.io) for more information.


```{important}
If you have configured the Nipoppy HPC functionalities to work on a job scheduler other than Slurm/SGE, please consider [opening an issue on our GitHub repository](https://github.com/nipoppy/nipoppy/issues/new/choose) and contributing your additions back to the codebase.
```
