#%%
import deeplabcut

#%% create training dataset
path_config_file = 'Z:/Teris/ASAP/deeplabcut/side_2_hands_newobj-julien-2022-08-26/config.yaml'

deeplabcut.create_training_dataset(path_config_file)

#%%
deeplabcut.train_network(path_config_file, gputouse=0, saveiters=300, 
                         displayiters=100, maxiters=200000)