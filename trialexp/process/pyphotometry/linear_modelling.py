import xarray as xr
import numpy as np
from sklearn import linear_model
import matplotlib.pylab as plt
import pandas as pd
import seaborn as sns
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

def extract_event(df_events, event, order, dependent_event=None):
    # extract the required event according to order, which can be one of 'first','last','last_before_first'
    # if order is 'last_before', you need to specify the depedent_event as well, it will always be
    # result is a pandas series
    events = df_events[df_events.name==event]

    if len(events) == 0:
        return None

    if order =='first':
        return events.iloc[0]
    elif order == 'last':
        return events.iloc[-1]
    elif order == 'last_before_first':
        assert dependent_event is not None, 'You must supply the dependent_event'
        if (dep_event := extract_event(df_events, dependent_event, 'first')) is not None:
            df_filter = df_events[df_events.time<=dep_event.time]
            if len(events := df_filter[df_filter.name == event])>0:
                return events.iloc[-1]
        return None
    elif order == 'first_after_last':
        assert dependent_event is not None, 'You must supply the dependent_event'
        if (dep_event := extract_event(df_events, dependent_event, 'last')) is not None:
            df_filter = df_events[df_events.time>=dep_event.time]
            if len(events := df_filter[df_filter.name == event])>0:
                return events.iloc[0]
        
        return None
    else:
        raise NotImplementedError('The specified order is not supported')



def interp_data(trial_data, df_trial, trigger, extraction_specs, sampling_rate):
    # extract siganl around event by event_window in ms
    # all the time between events wall be warpped according to padding in ms
    # the trigger event must be present in df_trial

    event_specs = dict(filter(lambda k: k[0]!=trigger, extraction_specs.items()))
    trigger_specs = extraction_specs[trigger]

    # Construct the interpolation time stamp
    event_window_len = int(np.sum([v['event_window'][1]-v['event_window'][0] for k,v in extraction_specs.items()])/1000*sampling_rate)
    total_padding_len = int(np.sum([v['padding'] for k,v in extraction_specs.items()])/1000*sampling_rate)
    total_len = total_padding_len+event_window_len

    if len(trial_data) < total_len:
        raise ValueError('There is not enough data for interpolation')
        
    t = np.zeros((total_len),)
    cur_idx = 0

    # find the trigger
    t_trigger_event = df_trial[df_trial.name == trigger]
    if len(t_trigger_event) == 0:
        raise ValueError(f"Error: the trigger {trigger} is not found")

    #copy the signal around the trigger
    t_trigger = t_trigger_event.iloc[0].time
    event_window_len = int((trigger_specs['event_window'][1] - trigger_specs['event_window'][0])/1000*sampling_rate)
    t[cur_idx:(cur_idx+event_window_len)] = np.arange(t_trigger+trigger_specs['event_window'][0], 
                                                      t_trigger+trigger_specs['event_window'][1], 1/sampling_rate*1000)
    cur_idx += event_window_len
    cur_time = t_trigger+trigger_specs['event_window'][1] #the trial time corresponding to cur_idx
    padding = trigger_specs['padding']
    padding_len = int(padding/1000*sampling_rate)

    # process the other events one by one
    for evt, specs in event_specs.items():
        dependent_event = specs.get('dependent_event', None)
        # if we can find the event, then warp from the event, if not, just start after padding
        if (event := extract_event(df_trial, evt, specs['order'], dependent_event)) is not None:
            t_event = event.time
        else:
            t_event = cur_time+padding-specs['event_window'][0]
            
        #TODO, detect when there is overlap between t_event and padding
        # find a way to warp between two events
        # Note: note there will be nan when the animal touch the spout too close to the start of next trial
        # e.g. in aborted trial
        
        # warp the inter-event period
        t[cur_idx:(cur_idx+padding_len)] = np.linspace(cur_time, t_event+specs['event_window'][0], padding_len)
        cur_idx += padding_len
        cur_time = cur_time + padding

        # copy the data around event
        event_window_time = specs['event_window'][1] - specs['event_window'][0]
        event_window_len = int(event_window_time/1000*sampling_rate)
        t[cur_idx:(cur_idx+event_window_len)] = np.arange(t_event+specs['event_window'][0], t_event+specs['event_window'][1], 1/sampling_rate*1000)

        cur_idx += event_window_len
        cur_time = cur_time + event_window_time
        padding = specs['padding']
        padding_len = int(specs['padding']/1000*sampling_rate)
        
    # use linear interpolation to warp them
    data_interp  = trial_data.interp(time=t)
    data_interp['time'] = np.arange(total_len)/sampling_rate*1000 + trigger_specs['event_window'][0]

    return data_interp

def extract_data(dataArray, start_time, end_time):
    # extract data specified by a start and ending time in ms
    ref_time = dataArray.time
    start_idx = np.searchsorted(ref_time, start_time)
    end_idx = np.searchsorted(ref_time, end_time)
    return dataArray[np.arange(start_idx, end_idx)]

def time_warp_data(df_events_cond, xr_signal, extraction_specs, Fs):
    # time warp between events so that they can be aligned together

    data_list = []
    trial_nb = []
    signal_var = 'analog_2_df_over_f'
    
    for i in range(1, int(df_events_cond.trial_nb.max()+1)):
        df_trial = df_events_cond[df_events_cond.trial_nb==i]
    
        pre_time = extraction_specs['hold_for_water']['event_window'][0]-500
        # extract photometry data around trial
        trial_data = extract_data(xr_signal, df_trial.iloc[0].time+pre_time, df_trial.iloc[-1].time)
        
        #time wrap it
        try:
            data_p = interp_data(trial_data, df_trial, 'hold_for_water', extraction_specs, Fs)
            data_p = data_p.expand_dims({'trial_nb':[i]})
            data_list.append(data_p)
        except NotImplementedError as e:
            print(e)
        except ValueError:
            pass
        
    xa = xr.concat(data_list,dim='trial_nb')

    return xa

def plot_warpped_data(xa_cond, signal_var, extraction_specs, ax=None):
    df = xa_cond[[signal_var,'trial_outcome']].to_dataframe().reset_index()
    sns.lineplot(df, x='time',y=signal_var, 
                   hue='trial_outcome', ax = ax)
    
    # add a bit of padding for text later
    ylim = ax.get_ylim()
    ax.set_ylim(ylim[0], ylim[1]*1.1)
    
    # plot the time point in the extraction_specs
    
    trigger_window = extraction_specs['hold_for_water']['event_window']
    cur_time = -500
    colors = (c for c in plt.cm.tab10.colors)
    
    for evt, specs in extraction_specs.items():
        pre_time, post_time = specs['event_window']
        padding = specs['padding']
        
        color = next(colors)
        ax.axvline(cur_time-pre_time,color= color, ls='--')
        ax.axvspan(cur_time, cur_time+(post_time-pre_time), alpha=0.1,color=color)
        ax.text(cur_time-pre_time-10, ax.get_ylim()[1], evt.replace('_', ' '), rotation = 90, ha='right', va='top')
        
        cur_time += (post_time-pre_time)+padding
        
def prepare_regression_data(xa_cond, signal_var):

    xr_data = xa_cond.dropna(dim='trial_nb')
    data = np.squeeze(xr_data[signal_var].data)

    # construct the predictor index
    # trial_outcome
    event_idx = np.where(xr_data.trial_outcome == 'success')[0]
    x_event = np.zeros_like(data)
    x_event[event_idx,:] = 1

    # trial_nb (a proxy for time)
    x_trial_nb = np.tile(xr_data.trial_nb, [data.shape[1],1]).T
    
    return (data, {'trial_outcome': x_event, 'trial_nb':x_trial_nb})

def perform_linear_regression(xa_cond,data, **predictor_vars):
    regress_res = []
    
    for t in range(data.shape[1]):
        y = data[:,t]
    
        # construct the dataframe for linear regression
        df2fit = pd.DataFrame({
            'signal':y,
            })
        
        for k,v in predictor_vars.items():
            df2fit[k] = v[:,t]
                    
        mod = smf.ols(formula = 'signal ~ trial_outcome + trial_nb', data=df2fit)
        res = mod.fit()

        for factor in ['trial_outcome', 'trial_nb']:
            regress_res.append({
                'beta':res.params[factor],
                'intercept': res.params['Intercept'], # the intercept represent the mean value
                'pvalue': res.pvalues[factor],
                'factor': factor,
                'CI': res.conf_int().loc[factor].tolist(),
                'time': xa_cond.time.data[t]})

    regress_res = pd.DataFrame(regress_res)

    return regress_res,res


def highlight_pvalues(df_reg_res, ax, threshold=0.05):
    # highlight the significant time
    for _, row in df_reg_res.iterrows():
        if row.pvalue < threshold:
            ax.axvline(row.time, alpha=0.1, color='y')