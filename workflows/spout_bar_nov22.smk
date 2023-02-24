from glob import glob
from pathlib import Path

configfile : 'workflows/config/config.yaml'

rule all:
    input: expand('{sessions}/processed/task.done', sessions = Path(config['session_root_dir']).glob('*'))

rule process_pycontrol:
    input:
        session_path = '{session_path}/{session_id}'
    output:
        event_dataframe = '{session_path}/{session_id}/processed/df_events_cond.pkl',
        condition_dataframe = '{session_path}/{session_id}/processed/df_conditions.pkl'
    script:
        'scripts/01_process_pycontrol.py'

rule pycontrol_figures:
    input:
        event_dataframe = '{session_path}/{session_id}//processed/df_events_cond.pkl'
    output:
        event_histogram = report('{session_path}/{session_id}//processed/figures/event_histogram_{session_id}.png'),
        done = touch('{session_path}/{session_id}/processed/task.done')
    script:
        'scripts/02_plot_pycontrol_data.py'
