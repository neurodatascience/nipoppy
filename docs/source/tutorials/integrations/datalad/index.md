# DataLad

This tutorial shows how to run the MRIQC pipeline on a BIDS dataset using [DataLad](https://datalad.org) for easy basic provenance tracking.
This is based on the {doc}`main MRIQC tutorial <../../mriqc_from_bids/index>` but uses DataLad commands for easy basic reproducibility.

## Step 0: Download the BIDS dataset with DataLad

Clone the dataset and retrieve all the data files.

```console
$ datalad clone https://github.com/OpenNeuroDatasets/ds004101.git
$ cd ds004101
$ datalad get -r .
$ cd ..
```


## Step 1: Initialize the Nipoppy study

Create a DataLad dataset first so we can record the provenance of all the Nipoppy commands from the beginning.

```console
$ datalad create -c text2git nipoppy_study
$ cd nipoppy_study
# We use `init --force` because the datalad dataset contains .git and .datalad directories.
$ datalad run -m "Initialize nipoppy study" nipoppy init --bids-source ../ds004101 --force
```

## Step 2: Modify the global configuration file

Follow the {doc}`main tutorial Step 2 <../../mriqc_from_bids/index>`.
If any changes were made, save them with datalad.

```console
$ datalad save -m "Update nipoppy config"
```

## Step 3: Install the MRIQC pipeline

Now we install the pipeline from the {doc}`main tutorial Step 3 <../../mriqc_from_bids/index>`

```{code-block} console
$ datalad run -m "Install pipeline" \
    nipoppy pipeline install {{zenodo_id_mriqc_23_1_0}}
```

Then manually update the `TEMPLATEFLOW_HOME` in `global_config.json` as described in the main tutorial, and save the change:

```console
$ datalad save -m "set templateflow home"
```

## Step 4: Run MRIQC with DataLad provenance

Now we will run the pipeline on a single participant, see the {doc}`main tutorial Step 4 <../../mriqc_from_bids/index>`.

```console
$ datalad run -m "process single participant/session" \
    nipoppy process \
        --pipeline mriqc \
        --pipeline-version 23.1.0 \
        --participant-id 09114 \
        --session-id 1pre
```

## Step 5: Track the pipeline processing status

Next we will record the tracking status from the {doc}`main tutorial Step 5 <../../mriqc_from_bids/index>`.

```console
$ datalad run -m "Track processing status" \
    nipoppy track-processing \
        --dataset nipoppy_study \
        --pipeline mriqc \
        --pipeline-version 23.1.0
```

## Step 6: Review Recorded Provenance

Now we can see the advantage of using `datalad run` with Nipoppy, the exact commands and parameters have been recorded into the git history!

```console
$ git log
```

```{code-block}
commit 6cc7cd3ad9ba21886f69124daed73907078022cd
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:43:47 2025 -0500

    [DATALAD RUNCMD] Track processing status

    === Do not change lines below ===
    {
     "chain": [],
     "cmd": "nipoppy track-processing --dataset nipoppy_study --pipeline mriqc --pipeline-version 23.1.0",
     "dsid": "880521ec-8d70-4fdf-85db-b9cafe4fec2f",
     "exit": 0,
     "extra_inputs": [],
     "inputs": [],
     "outputs": [],
     "pwd": "."
    }
    ^^^ Do not change lines above ^^^

commit 582155668ff9e7a0fc16ad14e48f058ec9b6c04e
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:42:33 2025 -0500

    [DATALAD RUNCMD] process single participant/session

    === Do not change lines below ===
    {
     "chain": [],
     "cmd": "nipoppy process --pipeline mriqc --pipeline-version 23.1.0 --participant-id 09114 --session-id 1pre",
     "dsid": "880521ec-8d70-4fdf-85db-b9cafe4fec2f",
     "exit": 0,
     "extra_inputs": [],
     "inputs": [],
     "outputs": [],
     "pwd": "."
    }
    ^^^ Do not change lines above ^^^

commit 04af4dd460458f65f7732bcbf1e5773d4acfcf8b
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:29:42 2025 -0500

    Update templateflow home

commit 5738c1309a3b302cc9385d029f5dc8b6d44bf57b
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:28:22 2025 -0500

    [DATALAD RUNCMD] Install pipeline

    === Do not change lines below ===
    {
     "chain": [],
     "cmd": "nipoppy pipeline install {{zenodo_id_mriqc_23_1_0}}",
     "dsid": "880521ec-8d70-4fdf-85db-b9cafe4fec2f",
     "exit": 0,
     "extra_inputs": [],
     "inputs": [],
     "outputs": [],
     "pwd": "."
    }
    ^^^ Do not change lines above ^^^

commit b81f344ba381788c94f8f58753b965ee794ed4c6
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:22:44 2025 -0500

    [DATALAD RUNCMD] Initialize nipoppy study

    === Do not change lines below ===
    {
     "chain": [],
     "cmd": "nipoppy init --bids-source ../ds004101 --force",
     "dsid": "880521ec-8d70-4fdf-85db-b9cafe4fec2f",
     "exit": 0,
     "extra_inputs": [],
     "inputs": [],
     "outputs": [],
     "pwd": "."
    }
    ^^^ Do not change lines above ^^^

commit c6c3e108b6f15077e1e43a966548d3eee28c92fe
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:22:16 2025 -0500

    Instruct annex to add text files to Git

commit a9e71d6806969b0503b1cc36d6d097674a225e2a
Author: Austin Macdonald <austin@dartmouth.edu>
Date:   Fri Jul 11 12:22:15 2025 -0500

    [DATALAD] new dataset
```
