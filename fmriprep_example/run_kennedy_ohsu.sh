# add to existing nidm file
csv2nidm -csv /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/kennedy_ohsu/sub-0050169_fmriprep_simple.csv -csv_map /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/kennedy_ohsu/fmriprep_data_dictionary.csv -derivative /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/kennedy_ohsu/fmriprep_software_metadata.csv -no_concepts -nidm /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/kennedy_ohsu/nidm.ttl
pynidm visualize -nl /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/kennedy_ohsu/nidm.ttl
