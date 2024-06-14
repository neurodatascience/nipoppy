**If using the default configuration file**:
- The Apptainer (formerly Singularity) container platform installed on your system
    - See [here](https://apptainer.org/docs/user/main/quick_start.html) for installation instructions
    - **Note**: Apptainer is only natively supported on Linux systems
- The container image file for the pipeline you wish to use
    - This can be downloaded by e.g., running `apptainer pull <URI>` inside your container directory (see the configuration file for URI). Make sure the file path is the same as what is specified in the configuration file!

```{caution}
Although it is *possible* to use Nipoppy without containers by modifying the default invocation files, we highly recommend using containerized pipelines to make your workflow as reproducible as possible. Using containers instead of locally installed software can also help avoid conflicts or unwanted interactions between different software/versions.
```
