
'''
Plotting of photometry data
'''
#%%
from snakehelper.SnakeIOHelper import getSnake
from trialexp.process.pyphotometry.plotting_utils import annotate_trial_number, plot_and_handler_error, plot_pyphoto_heatmap
from trialexp.process.pyphotometry.utils import *
from glob import glob
import xarray as xr
from trialexp.utils.rsync import *
import pandas as pd 
from scipy.interpolate import interp1d
import seaborn as sns 
from matplotlib import pyplot as plt 
import numpy as np
import os
from workflow.scripts import settings

#%% Load inputs

(sinput, soutput) = getSnake(locals(), 'workflow/pycontrol.smk',
  [settings.debug_folder + '/processed/log/photometry.done'],
  'photometry_figure')


#%%
xr_session = xr.open_dataset(sinput.xr_session)

figure_dir = soutput.trigger_photo_dir

#%% plot all event-related data

plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.spines.right'] = False
plt.rcParams['xtick.direction'] = 'out'
plt.rcParams['ytick.direction'] = 'out'
plt.rcParams["legend.frameon"] = False
plt.rcParams['xtick.bottom']=True
plt.rcParams['ytick.left']=True

if os.name =='nt':
    plt.rcParams['font.family'] = ['Arial']
elif os.name =='posix':
    plt.rcParams['font.family'] = ['Lato']

sns.set_context('paper')

skip_outcome = ['button_press'] #outcome variable to skip plotting (e.g. due to having too large variance)

for k in sorted(xr_session.data_vars.keys()):
    da = xr_session[k]
    
    if 'event_time' in da.coords: # choose data varialbes that are event related
        df2plot = xr_session[[k,'trial_outcome']].to_dataframe().reset_index()
        df2plot = df2plot[~df2plot.trial_outcome.isin(skip_outcome)]
        trial_outcome = df2plot['trial_outcome'].unique()
        
        g = sns.FacetGrid(df2plot, col='trial_outcome', col_wrap=3, hue='trial_outcome')
        g.map_dataframe(plot_and_handler_error, sns.lineplot, x='event_time', y=k)
        g.map_dataframe(annotate_trial_number)
        g.set_titles(col_template='{col_name}')
        g.set_xlabels('Time (ms)')
            
        g.figure.savefig(os.path.join(figure_dir, f'{k}.png'), dpi=300, bbox_inches='tight')
        
        # plot heatmap
        fig = plot_pyphoto_heatmap(xr_session[k])
        fig.savefig(os.path.join(figure_dir, f'{k}_heatmap.png'), dpi=300, bbox_inches='tight')

xr_session.close()

# %% 
#TODO add a vertical strip to show trial outcomes
