````{admonition} Understanding Boutiques descriptors and invocations
---
class: dropdown
---
{term}`Boutiques` descriptors have an `inputs` field listing all available parameters for the tool being described. As a simple example, let's use the following descriptor for a dummy "pipeline":

```{literalinclude} ./inserts/example_descriptor.json
```

Each key in the invocation file should match the `id` field in an input described in the descriptor file. The descriptor contains information about the input, such as its type (e.g., file, string, flag), whether it is required or not, etc.

Here is a valid invocation file for the above descriptor:
```{literalinclude} ./inserts/example_invocation.json
```

If we pass these two files to Boutiques (or rather, `bosh`, the Boutiques CLI tool), it will combine them into the following command (and run it):
```bash
echo . choice1 -f
```

Hence, Boutiques allows Nipoppy to abstract away pipeline-specific parameters into JSON text files, giving it the flexibility to run many different kinds of pipelines!

```{seealso}
See the [Boutiques tutorial](https://nbviewer.org/github/boutiques/tutorial/blob/master/notebooks/boutiques-tutorial.ipynb) for a much more comprehensive overview of Boutiques.
```
````
