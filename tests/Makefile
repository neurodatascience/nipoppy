.PHONY: data/ds004097

data/ds004097:
	rm -fr data/ds004097
	datalad install -s ///openneuro/ds004097 data/ds004097
	cd data/ds004097 && datalad get sub-NDARDD890AYU/ses-01/anat/ -J 12
	cd data/ds004097 && datalad get sub-NDARDD890AYU/ses-01/dwi/ -J 12
