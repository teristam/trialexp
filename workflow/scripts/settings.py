# %%
import os
import dotenv
dotenv.load_dotenv()

# debug_folder = r'//ettin/Magill_Lab/Teris/ASAP/expt_sessions/kms063-2023-02-27-164426/'
# debug_folder = r'//home/MRC.OX.AC.UK/phar0732/ettin/Data/head-fixed/_Other/test_folder_ephys/kms058_2023-03-24_15-09-44_bar_final/Record Node 101/experiment1/recording1/continuous/Neuropix-PXI-100.ProbeA-AP/sorting/'

debug_folder = os.path.join(os.environ['SESSION_ROOT_DIR'], 
                            '2024_April_cohort',
                            'by_sessions',
                            'reaching_go_spout_bar_VR_April24',
                            'RE015-2024-05-31-112606')
# debug_folder = r'/home/MRC.OX.AC.UK/phar0732/ettin/Data/head-fixed/by_sessions/reaching_go_spout_bar_nov22/kms062-2023-03-06-182344'
# %%
