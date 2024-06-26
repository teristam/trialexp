'''
Script to compute cell metrics by CellExplorer from Kilosort3 results
'''
#%%
import os
import warnings

import shutil

from pathlib import Path
import numpy as np

import pandas as pd

from snakehelper.SnakeIOHelper import getSnake
import spikeinterface.extractors as se
import spikeinterface.sorters as ss
from spikeinterface.core import select_segment_recording
from kilosort import run_kilosort
import settings
import torch

#%% Load inputs
spike_sorting_done_path = str(Path(settings.debug_folder) / 'processed' / 'spike_sorting.done')
# print(spike_sorting_done_path)
(sinput, soutput) = getSnake(locals(), 'workflow/spikesort.smk',
 [spike_sorting_done_path], 'spike_sorting')

# %%

sorter_name = 'kilosort4'
verbose = True
rec_properties_path = Path(sinput.rec_properties)
session_path = rec_properties_path.parents[1]/'processed'
session_id = rec_properties_path.parents[1].stem
rec_properties = pd.read_csv(rec_properties_path, index_col = 0)
rec_properties['sorting_error'] = False
# Only select longest syncable recordings to sort
idx_to_sort = rec_properties[(rec_properties.syncable == True) & (rec_properties.longest==True)].index.values

root_data_path = os.environ['SORTING_ROOT_DATA_PATH']
temp_sorter_folder = Path(os.environ['TEMP_DATA_PATH']) /session_id
output_si_sorted_folder = Path(soutput.si_output_folder)

# %%
for idx_rec in idx_to_sort:
    # block_index = rec_properties.block_index.iloc[idx_rec]
    # seg_index = rec_properties.seg_index.iloc[idx_rec]
    # exp_nb = rec_properties.exp_nb.iloc[idx_rec]
    # rec_nb = rec_properties.rec_nb.iloc[idx_rec]
    AP_stream = rec_properties.AP_stream.iloc[idx_rec]
    # duration = rec_properties.duration.iloc[idx_rec]
    recording_path = rec_properties.full_path[idx_rec]
    
    # symplifying folder names for each probe
    if 'ProbeA' in AP_stream:    
        probe_name = 'ProbeA'
    elif 'ProbeB' in AP_stream:
        probe_name = 'ProbeB'
    else:
        raise ValueError(f'invalid probe name rec: {rec_properties_path.parent}')

    # Define outputs folder, specific for each probe and sorter
    # output_sorter_specific_folder = sorter_specific_folder / sorter_name / probe_name
    temp_output_sorter_specific_folder = temp_sorter_folder / sorter_name / probe_name

    ephys_path = Path(rec_properties.full_path.iloc[idx_rec]).parents[4]
    
    # Maybe not the best method to get it
    # has introduced some bugs for forgotten reason related to folder changes
    # TODO improve to join just before relative_ephys_path and root_data_path overlap
    relative_ephys_path = os.path.join(*ephys_path.parts[5:])
    ephys_path = os.path.join(root_data_path, relative_ephys_path)
    
    if not (output_si_sorted_folder/probe_name).exists():
        (output_si_sorted_folder/probe_name).mkdir()
    
    # use kilosort4 directly
    device = torch.device('cuda:1')
    settings = {'data_dir': recording_path, 
                'n_chan_bin': 384, 
                'batch_size' : 30000*8, # for speeding up
                'save_extra_vars': True,
                'results_dir': output_si_sorted_folder/probe_name}
    
    
    # run_kilosort(settings=settings, probe_name='neuropixPhase3B1_kilosortChanMap.mat', device=device)
    
        
    rec2save = rec_properties.iloc[[idx_rec]].copy()
    rec2save.to_csv(output_si_sorted_folder/'rec_prop.csv', index=False) #also save the recording property



# %%
