'''
Script to create the session folder structure
'''
#%%
import os
import shutil
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm
from trialexp.process.pycontrol.data_import import session_dataframe
from trialexp.process.pyphotometry.utils import import_ppd_auto, get_dataformat

from trialexp.utils.pycontrol_utilities import parse_pycontrol_fn
from trialexp.utils.pyphotometry_utilities import parse_pyhoto_fn, create_photo_sync, parse_video_fn
from trialexp.utils.ephys_utilities import parse_openephys_folder, get_recordings_properties, create_ephys_rsync
from trialexp.process.pycontrol.utils import auto_load_dotenv
from loguru import logger
import settings

def copy_if_not_exist(src, dest):
    if not (dest/src.name).exists():
        shutil.copy(src, dest)

#%% Retrieve all task names from the tasks_params.csv
SESSION_ROOT_DIR = Path(os.environ['SESSION_ROOT_DIR'])
ETTIN_DATA_FOLDER = Path(os.environ['ETTIN_DATA_FOLDER'])
PROJECT_ROOT = Path(os.environ['SNAKEMAKE_DEBUG_ROOT'])

tasks_params_path = PROJECT_ROOT / 'params' / 'tasks_params.csv'
tasks_params_df = pd.read_csv(tasks_params_path)
tasks = tasks_params_df.task.values.tolist()

skip_existing = True #whether to skip existing folders

# cohort to copy, if empty then search for all cohorts
cohort_to_copy = ['2024_April_cohort'] 

#%%

def get_df_video(video_folder):
    video_files = list(video_folder.glob('*.mp4'))
    df_video = pd.DataFrame(list(map(parse_video_fn, video_files)))
    df_video = df_video.dropna()
    return df_video

#%%
def get_matched_timestamp(df, df_pycontrol_row, camera_no=2, min_minute=3):
    df = df[df.subject_id == df_pycontrol_row.subject_id]
    # find the closet match in time
    if not df.empty:
        min_td = np.min(abs(df_pycontrol_row.timestamp - df.timestamp))
        idx = np.argmin(abs(df_pycontrol_row.timestamp - df.timestamp))
        if min_td < timedelta(minutes=min_minute):
            #Find videos from other cameras
            cameras =  df[df.iloc[idx].timestamp == df.timestamp]
            return cameras
    else:
        return None

# %%

for cohort_id, cohort in enumerate(cohort_to_copy):

    print(f'cohort {cohort_id+1}/{len(cohort_to_copy)}: {cohort}')
    export_base_path = SESSION_ROOT_DIR/f'{cohort}'/'by_sessions'

    pycontrol_folder = SESSION_ROOT_DIR/f'{cohort}'/'pycontrol'
    pyphoto_folder = SESSION_ROOT_DIR/f'{cohort}'/'pyphotometry'
    ephys_base_path = ETTIN_DATA_FOLDER/'head-fixed'/'neuropixels'
    video_folder = ETTIN_DATA_FOLDER/'head-fixed'/'videos'

    # Gather all pycontrol, photometry, and ephys files/folders 
    pycontrol_files = list(pycontrol_folder.glob('*.txt')) + list(pycontrol_folder.glob('*.tsv'))
    pyphoto_files = list(pyphoto_folder.glob('*.ppd'))
    
    
    open_ephys_folders = os.listdir(ephys_base_path)

    df_pycontrol = pd.DataFrame(list(map(parse_pycontrol_fn, pycontrol_files)))
    assert len(df_pycontrol) == len(pycontrol_files)
    
    df_pycontrol = df_pycontrol[(df_pycontrol.subject_id!='00') & (df_pycontrol.subject_id!='01')] # do not copy the test data

    try:
        df_pycontrol = df_pycontrol[df_pycontrol.session_length>1000*60*3] #remove sessions that are too short, v2 uses second as unit
    except AttributeError:
        print(f'no session length, skipping folder')
        continue

    df_pyphoto = pd.DataFrame(list(map(parse_pyhoto_fn, pyphoto_files)))
        
    all_parsed_ephys_folders = list(map(parse_openephys_folder, open_ephys_folders))
    # remove unsuccessful ephys folders parsing 
    parsed_ephys_folders = [result for result in all_parsed_ephys_folders if result is not None]
    df_ephys_exp = pd.DataFrame(parsed_ephys_folders)
    df_video = get_df_video(video_folder)

    
    # Match
    #Try to match pycontrol file together with pyphotometry file
    matched_photo_path = []
    matched_photo_fn  = []
    matched_ephys_path = []
    matched_ephys_fn  = []
    matched_video_names = []
    
    df_pycontrol['do_copy'] = True
    
    if skip_existing:
        
        for i in df_pycontrol.index:
            # filter out folders that are already there
            session_id = df_pycontrol.loc[i].filename
            task_name = df_pycontrol.loc[i].task_name
            if Path(export_base_path, task_name, session_id).exists():
                df_pycontrol.loc[i, 'do_copy'] = False
                    
    df_pycontrol = df_pycontrol[df_pycontrol.do_copy==True]
    # df_pycontrol= df_pycontrol[df_pycontrol.subject_id == 'TT008']
    # df_pycontrol= df_pycontrol[df_pycontrol.session_id == 'TT008-2024-06-10-153517']
    
    for _, row in df_pycontrol.iterrows():
        
        # Photometry matching
        # will only compute time diff on matching subject_id
        # First identify the same animal
        if not df_pyphoto.empty:
            df_pyphoto_subject = df_pyphoto[df_pyphoto.subject_id == row.subject_id]
        else:
            matched_photo_path.append(None)
            matched_photo_fn.append(None)
            
            
        # Matching videos
        matched_videos = get_matched_timestamp(df_video,row)
        if matched_videos is not None:
            matched_video_names.append(matched_videos.filename.values)
        else:
            matched_video_names.append(None)

        

        # find the closet match in time
        if not df_pyphoto_subject.empty:
            min_td = np.min(abs(row.timestamp - df_pyphoto_subject.timestamp))
            idx = np.argmin(abs(row.timestamp - df_pyphoto_subject.timestamp))

            if min_td < timedelta(minutes=15):
                matched_photo_path.append(df_pyphoto_subject.iloc[idx].path)
                matched_photo_fn.append(df_pyphoto_subject.iloc[idx].filename)
            else:
                matched_photo_path.append(None)
                matched_photo_fn.append(None)
        
        elif not df_pyphoto.empty and df_pyphoto_subject.empty:
            matched_photo_path.append(None)
            matched_photo_fn.append(None)

        # Ephys matching
        if not df_ephys_exp.empty:
            df_ephys_exp_subject = df_ephys_exp[df_ephys_exp.subject_id == row.subject_id]
            if not df_ephys_exp_subject.empty:
                
                # need to be more careful about the matching because ephys can start
                # much earlier than pycontrol session
                # find all potential match, choose the one that is earlier and closest
                td = (row.timestamp - df_ephys_exp_subject.exp_datetime)
                td = np.array([t.total_seconds() for t in td])
                df_ephys_exp_subject = df_ephys_exp_subject[td>=-1] # pycontrol is later
                
                if len(df_ephys_exp_subject) > 0:
                    min_td = np.min(abs(row.timestamp - df_ephys_exp_subject.exp_datetime))
                    idx = np.argmin(abs(row.timestamp - df_ephys_exp_subject.exp_datetime))
                    if min_td < timedelta(days=0.25):
                        matched_ephys_path.append(ephys_base_path / df_ephys_exp_subject.iloc[idx].foldername)
                        matched_ephys_fn.append(df_ephys_exp_subject.iloc[idx].foldername)
                        continue
        
        # some error occur, append None
        matched_ephys_path.append(None)
        matched_ephys_fn.append(None)

    df_pycontrol['pyphoto_path'] = matched_photo_path
    df_pycontrol['pyphoto_filename'] = matched_photo_fn

    df_pycontrol['ephys_path'] = matched_ephys_path
    df_pycontrol['ephys_folder_name'] = matched_ephys_fn
    
    df_pycontrol['video_names'] = matched_video_names

    ##########################
    # Move folders
    for i in tqdm(range(len(df_pycontrol))):
        row = df_pycontrol.iloc[i]
        session_id = row.session_id
        subject_id = row.subject_id
        task_name = row.task_name
        
        target_pycontrol_folder = Path(export_base_path,task_name, session_id, 'pycontrol')
        target_pyphoto_folder = Path(export_base_path, task_name, session_id, 'pyphotometry')
        target_ephys_folder = Path(export_base_path,  task_name, session_id, 'ephys')
        target_video_folder = Path(export_base_path, task_name, session_id, 'video')
        
        if not target_pycontrol_folder.exists():
            # create the base folder
            target_pycontrol_folder.mkdir(parents=True)
            
        if not target_pyphoto_folder.exists():
            target_pyphoto_folder.mkdir(parents=True)

        if not target_ephys_folder.exists():
            target_ephys_folder.mkdir(parents=True)
            
        if not target_video_folder.exists():
            target_video_folder.mkdir(parents=True)
            
        pycontrol_file = row.path
        pyphotometry_file = row.pyphoto_path
        video_files = row.video_names

        #copy the pycontrol files
        # print(pycontrol_file, target_pycontrol_folder)
        copy_if_not_exist(pycontrol_file, target_pycontrol_folder)
        
        #copy all the analog data
        analog_files = list(pycontrol_file.parent.glob(f'{session_id}*.pca')) + list(pycontrol_file.parent.glob(f'{session_id}*.npy'))
        for f in analog_files:
            copy_if_not_exist(f, target_pycontrol_folder) 
            
        #Copy pyphotometry file if they match
        if pyphotometry_file is not None:
            data_pycontrol = session_dataframe(pycontrol_file)
            data_pyphotmetry = import_ppd_auto(pyphotometry_file)
            if create_photo_sync(data_pycontrol, data_pyphotmetry) is not None:
                copy_if_not_exist(pyphotometry_file, target_pyphoto_folder)
            else:
                logger.debug(f'Cannot sync photometry data for {pyphotometry_file.name}')

                
        # write down the filename of the video file
        video_list_file = target_video_folder/'video_list.txt'
        if row.video_names is not None and not video_list_file.exists():
            np.savetxt(video_list_file, row.video_names, '%s')


        #write information about ephys recrodings in the ephys folder
        if row.ephys_folder_name:

            recordings_properties = get_recordings_properties(ephys_base_path, row.ephys_folder_name)
            # try to sync ephys recordings
            recordings_properties['syncable'] = False
            recordings_properties['longest'] = False
            sync_paths = recordings_properties.sync_path.unique()
            for sync_path in sync_paths:
                # copy syncing files in 
                if create_ephys_rsync(str(pycontrol_file), sync_path) is not None:
                    recordings_properties.loc[recordings_properties.sync_path == sync_path, 'syncable'] = True
                else:
                    print(f'Cannot sync ephys data for {sync_path.parent.name}')
            longest_syncable = recordings_properties.loc[recordings_properties.syncable == True, 'duration'].max()
            recordings_properties.loc[(recordings_properties.duration == longest_syncable) & (recordings_properties.syncable == True), 'longest'] = True

            sync_path = recordings_properties.loc[recordings_properties.longest == True, 'sync_path'].unique()
            
            if len(sync_path) > 1:
                raise NotImplementedError(f'multiple valids sync_path for the session, something went wrong: {row.ephys_folder_name}')
            
            # copy sync files from the longest syncable recording
            elif len(sync_path) == 1:

                copy_if_not_exist(sync_path[0] / 'states.npy', target_ephys_folder)
                copy_if_not_exist(sync_path[0] / 'timestamps.npy', target_ephys_folder)

            else:
                # no syncable recordings
                ...


            recordings_properties.to_csv(target_ephys_folder / 'rec_properties.csv')


# %%
