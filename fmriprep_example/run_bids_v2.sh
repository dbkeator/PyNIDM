# create nidm file from BIDS dataset
bidsmri2nidm -d /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/ -bidsignore -no_concepts

# add to existing nidm file
csv2nidm -csv /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -json_map /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.json -derivative /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -nidm /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm.ttl
pynidm visualize -nl /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm.ttl

# create new nidm file of only derivative data
csv2nidm -csv /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -json_map /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.json -derivative /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -out /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm_only_fmriprep.ttl
pynidm visualize -nl /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm_only_fmriprep.ttl

# create new nidm file using CSV version of data dictionary
csv2nidm -csv /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -csv_map /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.csv -derivative /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -out /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm_only_fmriprep_csv_dd.ttl
pynidm visualize -nl /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm_only_fmriprep_csv_dd.ttl

# add to existing nidm file using CSV version of data dictionary
bidsmri2nidm -d /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/ -bidsignore -no_concepts
csv2nidm -csv /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -csv_map /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.csv -derivative /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -nidm /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm.ttl
pynidm visualize -nl /Users/dkeator/Documents/Coding/PyNIDM/fmriprep_example/bids_v2/nidm.ttl