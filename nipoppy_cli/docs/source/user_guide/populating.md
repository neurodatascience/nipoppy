# Populating an empty dataset

Once an empty Nipoppy dataset has been created, the next step is to manually populate it with the raw data available in the study.

In general, all data pertaining to the study should be stored together (i.e., under {{dpath_root}}), as that makes it easier to maintain the dataset, link data between modalities, and keep track of the available data.

```{note}
Depending on the study you are working with, there might not be any data to put in some of the directories described below -- that is not an issue. On the other hand, if your study has data that does not seem to fit anywhere, you should still try to store it inside the Nipoppy dataset. You can create additional directories for non-imaging and non-tabular data under {{dpath_root}} or {{dpath_scratch}} (in moderation).
```

## Summary

### Prerequisites

- An empty Nipoppy dataset, as created by [`nipoppy init`](../cli_reference/init.md)
    - See the [Quickstart guide](../quickstart.md) for full instructions on
    initializing a new dataset

### Data directories

| Directory | Content description |
|---|---|
| {{dpath_downloads}} | Data archives, web downloads, etc. (imaging and non-imaging data) |
| {{dpath_raw_imaging}} | {{content_dpath_raw_imaging}} |

## Data archives and web downloads

The {{dpath_downloads}} directory is for storing data archives (e.g., `.zip`, `.tar`, or `.tar.gz` files), or any file downloaded/moved from another location (e.g., spreadsheets for raw tabular data). An example of this would be file dumps downloaded from web portals (e.g., [LONI](https://ida.loni.usc.edu/login.jsp)).

There is no specification for the internal organization inside this directory, though it should be internally consistent. If downloads are made at multiple points in time, files should be labelled with a timestamp (and not overwritten).

```{attention}
If you have imaging data that does not need to be uncompressed/extracted (for example, if the {term}`BIDS` conversion pipeline you plan to use can handle data archives), then it should *not* go in the {{dpath_downloads}} directory. Instead, those files should go directly to the appropriate imaging data directory.
```

## Raw imaging data

The {{dpath_raw_imaging}} directory is for storing **raw imaging data as they are, before any organization/processing is done**. It is okay (and expected) for the data in this directory to be messy or to follow an arbitrary organization (e.g., many subfolder levels).

Data in this directory will typically consists of [DICOM](https://en.wikipedia.org/wiki/DICOM) files from scanners, though some analyses might start with files in the [NIfTI](https://en.wikipedia.org/wiki/Neuroimaging_Informatics_Technology_Initiative) format instead (e.g., if DICOM-to-NIfTI conversion has already been done and the original DICOMs are not available anymore).

```{attention}
If both DICOMs and NIfTIs are available, we recommend starting over with the DICOMs since they contain more information than NIfTIs for BIDS conversion. If that is not feasible, then {{dpath_raw_imaging}} should contain the NIfTIs, and the raw DICOMs can be archived and stored somewhere else (e.g., {{dpath_downloads}}).
```

## Next steps

For imaging data, the next step is to [reorganize the data](organizing_imaging.md) in a way that prepares it for {term}`BIDS` conversion.

If you have tabular non-imaging (e.g., demographic or assessments) data, guidelines for wrangling and linking tabular data can be found [here](organizing_tabular.md)
