# Import libraries
import numpy as np
import pandas as pd
import os
import re
import matplotlib.pyplot as plt
import matplotlib.transforms as tr
import scipy.stats as statsv
from scipy.stats import norm, ttest_ind, ttest_1samp, ttest_rel
import seaborn as sns
import functions.functions as dataset
from process_dataset.process_dataset import contol1_dataset, materials_params_dataset
import functions.search_functions as search_fnc
from datetime import datetime
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)


def extract_mix_design(ID):
    # remove first 2 letters
    ID = ID[2:]
    
    # remove trailing letter+digit suffix (e.g. D1, X2)
    ID = re.sub(r'[A-Za-z]\d+$', '', ID)
    
    return ID

def get_strength_data(df, ids, sample_age, use_contains=False):
    """
    ids: single string or tuple/list of strings
    use_contains: True -> uses .str.endswith (for multiple patterns)
                  False -> exact match
    """
    
    if use_contains:
        mask_id = df['DATA_ID'].str.endswith(tuple(ids))
    else:
        mask_id = df['DATA_ID'].isin(ids if isinstance(ids, (list, tuple)) else [ids])

    filtered = df[
        mask_id &
        (df['Sample_Age'] == sample_age)
    ]

    return filtered['Strength']

def load_and_prepare(sheet_name):
    df = pd.read_excel(base_excel_file, sheet_name)
    cols = ['Day', 'D1', 'D3', 'D7', 'D14', 'D28']
    df['Week'] = df['Week'].astype(str)
    df[cols] = df[cols].apply(pd.to_datetime, dayfirst=True)
    return df

df_compressive_sorted, df_flexural_sorted, df_cement_sorted = contol1_dataset()
df_params = materials_params_dataset()
df_compressive_cleaned = df_compressive_sorted.dropna(thresh=1, subset=['Mean 1','Mean 7','Mean 14','Mean 28','Mean 3'])
#save_path = r"C:\Users\JessicaMaldo_p3rvdgi\OneDrive - Concretene\Documents\ws_concretene\dataset\\"
save_path = '/home/jessicamaldonado/OneDrive/Documents/ws_concretene/dataset/'
base_excel_file = '/home/jessicamaldonado/OneDrive/Calendars/Calendar_materials.xlsx'
base_excel_file_formulations = '/home/jessicamaldonado/OneDrive/Formulation lab/Formulations Lab Research and Production Plan.xlsx'
path_dataset_sharepoint = '/home/jessicamaldonado/OneDrive/Data Lab/Datasets/Concrete/'
path_dataset_QA = '/home/jessicamaldonado/OneDrive/Data Lab/Datasets/QA/Concrete/'
base_excel_file_qa = '/home/jessicamaldonado/OneDrive/Formulation lab/Testing_calendar/QA_Results_Lab_NS.xlsx'
    
df_compressive_sorted.to_csv(save_path + 'compressive_rawr_data.csv')
df_flexural_sorted.to_csv(save_path + 'flexural_rawr_data.csv')
df_cement_sorted.to_csv(save_path + 'morter_rawr_data.csv')

# Merge Datasets
results_compressive = pd.merge(df_params,df_compressive_sorted, on = ['ID', 'DATA_ID','Week'])
results_flexural = pd.merge(df_params,df_flexural_sorted, on = ['ID','Week'])
comp_flex = pd.merge(df_compressive_cleaned,df_flexural_sorted, on = ['DATA_ID','Sample_number'])
comp_flex = comp_flex.dropna(subset=['Mean 28_y'])

#save_path = r"C:\Users\JessicaMaldo_p3rvdgi\OneDrive - Concretene\Documents\ws_concretene\dataset\\"
save_process_dataset ='/home/jessicamaldonado/OneDrive/Data Lab/Raw_datasets/'
results_compressive.to_csv(save_process_dataset + 'Results_compressive.csv')
df_params.to_csv(save_process_dataset + 'Params_processed.csv')
df_compressive_sorted.to_csv(save_process_dataset + 'Test_machine_dataset/' + 'compressive_rawr_data.csv')
df_flexural_sorted.to_csv(save_process_dataset + 'Test_machine_dataset/' + 'flexural_rawr_data.csv')
df_cement_sorted.to_csv(save_process_dataset + 'Test_machine_dataset/' + 'morter_rawr_data.csv')

df_compressive_sorted['Date'] = pd.to_datetime(df_compressive_sorted['Date'], dayfirst=True)
df_compressive_sorted['Sample_Age'] = df_compressive_sorted['Sample_Age'].astype(int)

df_compressive_sorted['Casting_Date'] = (
    df_compressive_sorted['Date'] 
    - pd.to_timedelta(df_compressive_sorted['Sample_Age'], unit='D')
)
df_compressive_sorted['Casting_Year'] = df_compressive_sorted['Casting_Date'].dt.year

df_compressive_sorted['data_id_with_year'] = (
    df_compressive_sorted['DATA_ID'] + '-' +
    df_compressive_sorted['Casting_Year'].astype(str)
)

df_compressive_sorted = df_compressive_sorted[['Test_type', 'Week', 'ID', 'Sample_Age', 'Sample_number', 'Depth',
                                                'Load', 'Strength', 'Operator', 'Date', 'Time', 'Casting_Date', 'Comment',
                                                'Strength_calculated', 'Calibration Test', 'DATA_ID', 'data_id_with_year', 'Mean 1',
                                                'STDEV 1', '95% Confidence 1', 'Outlier 1', 'Mean 7', 'STDEV 7',
                                                '95% Confidence 7', 'Outlier 7', 'Mean 14', 'STDEV 14',
                                                '95% Confidence 14', 'Outlier 14', 'Mean 28', 'STDEV 28',
                                                '95% Confidence 28', 'Outlier 28', 'Mean 3', 'STDEV 3',
                                                '95% Confidence 3', 'Outlier 3']]


### Dataset with materials
big_mixer_data = load_and_prepare('Table_concrete_BM')
small_mixer_data = load_and_prepare('Table_concrete_SM')

data_compressive_bm = pd.merge(big_mixer_data,df_compressive_sorted, on = ['data_id_with_year', 'Week'])
data_compressive_sm = pd.merge(small_mixer_data,df_compressive_sorted, on = ['data_id_with_year', 'Week'])

data_compressive_bm['Mixer'] = 'BM'
data_compressive_sm['Mixer'] = 'SM'

data_compressive_all = pd.concat(
    [data_compressive_bm, data_compressive_sm],
    ignore_index=True
)

data_compressive_all['Mix Design'] = data_compressive_all['ID_x'].apply(extract_mix_design)

data_compressive_all = data_compressive_all[['Week', 'Day', 'ID_x', 'Test', 'Project', 'D1',
       'D3', 'D7', 'D14', 'D28', 'data_id_with_year', 'ID_y',
       'Sample_Age', 'Depth', 'Load', 'Strength', 'Operator',
       'Date', 'Time', 'Casting_Date', 'Comment', 'Mixer', 'Mix Design', 'DATA_ID', 'CRT', 'Dosage', 'Mixing Time', 'Slump', 'Mean 1', 'STDEV 1', '95% Confidence 1',
       'Outlier 1', 'Mean 7', 'STDEV 7', '95% Confidence 7', 'Outlier 7',
       'Mean 14', 'STDEV 14', '95% Confidence 14', 'Outlier 14', 'Mean 28',
       'STDEV 28', '95% Confidence 28', 'Outlier 28', 'Mean 3', 'STDEV 3',
       '95% Confidence 3', 'Outlier 3']]


data_compressive_all['Mixing'] = data_compressive_all['Day'] + pd.to_timedelta(data_compressive_all['Mixing Time'].apply(lambda t: f"{t.hour}:{t.minute}:{t.second}"))
data_compressive_all['Testing'] = data_compressive_all['Date'] + pd.to_timedelta(data_compressive_all['Time'])

data_compressive_all['Tolerance'] = data_compressive_all['Testing'] - data_compressive_all['Mixing']
data_compressive_all['Tolerance_hh'] = data_compressive_all['Tolerance'].dt.total_seconds() / 3600


df_CRT_formulation = pd.read_excel(base_excel_file_formulations, 'CRT Sample List')
df_MFB_formulation = pd.read_excel(base_excel_file_formulations, 'MFB Sample List')
df_CRT_formulation = df_CRT_formulation.rename(columns={"Batch": "CRT", "Bulk CRT": "MFB"})
df_MFB_formulation = df_MFB_formulation.rename(columns={'Batch': 'MFB'})

df_formulation = df_CRT_formulation.merge(df_MFB_formulation, on='MFB', how='left')
df_formulation = df_formulation.rename(columns={'MFB': 'Bulk CRT'})

df_test = data_compressive_all.merge(df_formulation, on='CRT', how='left')

####Dataset QA
df_QA_formulation = pd.read_excel(base_excel_file_qa, 'Raw')
df_QA_formulation = df_QA_formulation.dropna(subset=['Batch'])
#df_QA_CRT = df_QA_formulation[df_QA_formulation['Batch'].str.startswith('CRT')]
df_QA_MFB = df_QA_formulation[df_QA_formulation['Batch'].str.startswith('MFB')]
df_QA_formulation = df_QA_formulation.rename(columns={"Batch": "CRT"})

df_qa_test = df_test.merge(df_QA_formulation, on='CRT', how='left')
df_columns = df_qa_test.columns.to_list()

df_test_complete = df_qa_test[['Week', 'Day', 'ID_x', 'Test_x', 'Project_x',
                                 'ID_y', 'Sample_Age', 'Strength', 'Operator', 
                                 'Date', 'Time', 'Casting_Date', 'Comment', 'Mixer_x', 'Mix Design', 'DATA_ID', 'CRT', 'Dosage',
                                   'Mixing Time', 'Slump', 'Tolerance_hh', 'Tech_x', 'Date_x', 'Project_y', 'Project Notation', 'Date Finished_x', 'Reason_x', 
                                   'Test Spec_x', 'Bulk CRT', 'GNP_x', 'GO_x', 'Ratio_x', 'GR%_x', 'Mixer_y', 'Speed (RPM)_x', 'Mix Duration (min)_x', 'SP_x', 
                                   'SP Amount_x', 'Notes_x', 'Date_y', 'Tech_y', 'Campaign', 'Form Project', 'Date Finished_y', 'Reason_y', 'Test Spec_y', 'GNP_y',
                                     'GO_y', 'Additive Package', 'Ratio_y', 'GR%_y', 'Speed (RPM)_y', 'Mix Duration (min)_y', 'SP_y', 'SP Amount_y', 'Notes_y', 
                                     'Project', 'D#', 'Test_y', 'PSD GO - 10', 'PSD GO - 50', 'PSD GO - 90', 'Pre PSD - 10', 'Pre PSD - 50', 'Pre PSD - 90', 'PSD CRT - 10',
                                       'PSD CRT - 50', 'PSD CRT - 90', 'Initial Rheo - Tsi', 'Final Rheo - Tsi', 'Turb - cP', 'VC -Pass/Fail', 'Other']]

df_QA_MFB = df_QA_MFB.rename(columns={"Batch": "Bulk CRT"})

df_test_complete_2 = df_test_complete.merge(
    df_QA_MFB,
    on='Bulk CRT',
    how='left',
    suffixes=('', '_MFB')
)

columns_to_fill = [
    'Project', 'D#', 'Test_y', 'PSD GO - 10', 'PSD GO - 50', 'PSD GO - 90', 'Pre PSD - 10', 'Pre PSD - 50', 'Pre PSD - 90', 'PSD CRT - 10',
                                           'PSD CRT - 50', 'PSD CRT - 90', 'Initial Rheo - Tsi', 'Final Rheo - Tsi', 'Turb - cP', 'VC -Pass/Fail', 'Other'
]

for col in columns_to_fill:
    mfb_col = f'{col}_MFB'

    if col in df_test_complete_2.columns and mfb_col in df_test_complete_2.columns:
        df_test_complete_2[col] = (
            df_test_complete_2[col]
            .combine_first(df_test_complete_2[mfb_col])
        )

df_qa_complete = df_test_complete_2[['Week', 'Day', 'ID_x', 'Test_x', 'Project_x',
                                 'ID_y', 'Sample_Age', 'Strength', 'Operator', 
                                 'Date', 'Time', 'Casting_Date', 'Comment', 'Mixer_x', 'Mix Design', 'DATA_ID', 'CRT', 'Dosage',
                                   'Mixing Time', 'Slump', 'Tolerance_hh', 'Tech_x', 'Date_x', 'Project_y', 'Project Notation', 'Date Finished_x', 'Reason_x', 
                                   'Test Spec_x', 'Bulk CRT', 'GNP_x', 'GO_x', 'Ratio_x', 'GR%_x', 'Mixer_y', 'Speed (RPM)_x', 'Mix Duration (min)_x', 'SP_x', 
                                   'SP Amount_x', 'Notes_x', 'Date_y', 'Tech_y', 'Campaign', 'Form Project', 'Date Finished_y', 'Reason_y', 'Test Spec_y', 'GNP_y',
                                     'GO_y', 'Additive Package', 'Ratio_y', 'GR%_y', 'Speed (RPM)_y', 'Mix Duration (min)_y', 'SP_y', 'SP Amount_y', 'Notes_y', 
                                     'Project', 'D#', 'Test_y', 'PSD GO - 10', 'PSD GO - 50', 'PSD GO - 90', 'Pre PSD - 10', 'Pre PSD - 50', 'Pre PSD - 90', 'PSD CRT - 10',
                                       'PSD CRT - 50', 'PSD CRT - 90', 'Initial Rheo - Tsi', 'Final Rheo - Tsi', 'Turb - cP', 'VC -Pass/Fail', 'Other']]


#### Creation of excel and csv dataset
projects_name = df_test['Project_x'].unique()
for name in projects_name:
    dataset_search = df_test[(df_test['ID_y'].str.startswith(('C', 'G'))) 
                                       #df_compressive_sorted['ID'].str.endswith('C')
                                       &
                                       (df_test['Project_x'].str.startswith(f'{name}'))
                                       #&
                                       #(df_compressive_sorted['Sample_Age']==1)
                                       ]
    dataset_search.to_csv(path_dataset_sharepoint + "/CSV/" + f'Results_{name}.csv')
    dataset_search.to_excel(path_dataset_sharepoint + "/Excel/" + f'Results_{name}.xlsx')
    dataset_search_qa = df_qa_complete[(df_qa_complete['ID_y'].str.startswith(('G'))) 
                                           #df_compressive_sorted['ID'].str.endswith('C')
                                           &
                                           (df_qa_complete['Project_x'].str.startswith(f'{name}'))
                                           #&
                                           #(df_compressive_sorted['Sample_Age']==1)
                                           ]
    dataset_search_qa.to_excel(path_dataset_QA + f'Results_{name}.xlsx')

print("Excel and CSV exported with QA!")

