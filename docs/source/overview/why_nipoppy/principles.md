# Inspirations and principles

Nipoppy is inspired by and built upon the previous work of others. These include community standards (e.g. [BIDS](https://bids.neuroimaging.io/)), tools (e.g. [Boutiques](https://boutiques.github.io/)), and technologies (e.g. [Apptainer](https://apptainer.org/)).

Nipoppy will always strive to support and contribute to existing open-source community standards and avoid creating a new one.
We see Nipoppy as a “dry lab protocol” that glues together existing tools to help adopt open-science and FAIR data principles in practice.

This umbrella effort is guided by following design principles:


| Principle   | Example implementation in Nipoppy    |
|:-------|:------------------------------------------------------------------------|
| Specify sequence / ordering of tasks whenever possible   | Generate a {term}`manifest <manifest file>` before anything else!                                |
| Optimize for user-oriented modular design    | Conceptually, Nipoppy is divided into *curate, process, extract* modules to match typical research study stages in a neuroimaging lab. |
| Prioritize lightweight, simpler design over comprehensive functionalities  | Nipoppy performs simpler sanity checks at module endpoints instead of sophisticated provenance tracking of the process to ensure reproducibility|
| Handle collected data “as-is” | Nipoppy doesn’t interfere with the current data collection practice i.e. modify recruitment, assessment, DICOM files |
| Don’t be a black box | Nipoppy wants to be a hands-on training tool helping researchers to adopt FAIR principles |
| Build for iterative workflows | FAIR research involves **re**producibility, **re**use, and **re**plication. Nipoppy tries to simplify these tasks. |
| There are no stupid GitHub issues or Discord questions!| Nipoppy is by and for the community - we always welcome feedback to improve it!  |


We do not claim that all of these principles would immediately improve efficiency. However, we do believe that a short-term investment in the adoption of these efforts will result in huge long-term returns for individual researchers, labs, and consortia.
