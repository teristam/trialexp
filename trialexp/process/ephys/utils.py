
import numpy as np
import pandas as pd   
from pandas.api.types import infer_dtype

def denest_string_cell(cell):
        if len(cell) == 0: 
            return 'ND'
        else:
            return str(cell[0])
        
def dataframe_cleanup(dataframe: pd.DataFrame):
    '''
    Turn object columns into str columns and fill empty gaps with ''
    '''
    types_dict = dict(zip(dataframe.columns,dataframe.dtypes))
    for (col, dtype) in types_dict.items():
        if dtype == np.dtype(object):
            dtype_inferred = infer_dtype(dataframe[col])
            dataframe[col] = dataframe[col].fillna('', downcast={np.dtype(object):str}).astype(str)
            dataframe[col] = dataframe[col].astype(dtype_inferred)
            # session_cell_metrics[col] = session_cell_metrics[col].astype(str)
    
    return dataframe

def session_and_probe_specific_uid(session_ID: str, probe_name: str, uid: int):
    '''
    Build unique cluster identifier string of cluster (UID),
    session and probe specific
    '''
    
    return session_ID + '_' + probe_name + '_' + str(uid)