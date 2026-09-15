# Study specification

Nipoppy provides a specification (i.e. directory layout) for study organization that extends the [Brain Imaging Data Structure (BIDS) standard](https://bids.neuroimaging.io/). One can think of this as a "standard" for organizing data generated during a lifecycle of a study which may include sourcedata (e.g. DICOMs), tabular data (e.g., phenotypic assessments), and imaging derivatives (e.g. fMRIPrep output), in addition to the raw BIDS data. A study-level standardized directory layout simplifies curation and processing tasks as well as tracking of outputs. Additionally, the layout consists of directories to store pipeline specifications and custom code used for data wrangling tasks. The [manifest](manifest.md) file at the root level is meant to provide *expected availability* information about the participants, visits, sessions, and imaging datatypes available in the study.

There are ongoing efforts to merge this specification with the BIDS standard's study-level dataset type.

The directory tree shown below is generated automatically upon study initialization (see [`nipoppy init`](../reference/cli_reference/init.rst)).

![Nipoppy specification](../_static/img/nipoppy_specification.jpg)
