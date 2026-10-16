# Import libraries",
import numpy as np
import pandas as pd
import os
import re
import matplotlib.pyplot as plt
import matplotlib.transforms as tr
import scipy
import seaborn as sns
import scipy.stats as statsv
from scipy.stats import norm, ttest_ind, ttest_1samp, ttest_rel
import functions.functions as dataset
from process_dataset.process_dataset import contol1_dataset, materials_params_dataset
import functions.search_functions as search_fnc
from matplotlib.ticker import (MultipleLocator, AutoMinorLocator)
from functions.functions import conver_time_stamp, conver_string_parameter, change_sample_age

def extract_mix_design(ID):
    # remove first 2 letters
    ID = ID[2:]
    
    # remove trailing letter+digit suffix (e.g. D1, X2)
    ID = re.sub(r'[A-Za-z]\d+$', '', ID)
    
    return ID

def Outliers(values: list, percentage: float):
    outliers = []
    n1 = []

    new_values = [n1.append(value) if value > 1 else  outliers.append(index) for index, value in enumerate(values)]

    for index, value in enumerate(n1):
        n = n1.copy()
        n.remove(value)
        #print(n)
        n = np.array(n)
        #print(n)\n",
        o_max = n.mean() * (1 + percentage)
        o_min = n.mean() * (1 - percentage)
        if value >= o_max or value <= o_min:
        #if value <= o_min:\n",
            outliers.append(index)
    return outliers

def pre_process_dataset(data_frame, casting_age, percentage_outliers1, percentage_outliers2):

    df_sorted = data_frame.sort_values(by=['Week','ID','Sample_Age'])
    df_sorted['ID'] = df_sorted['ID'].str.removesuffix(' ')
    id_values = df_sorted['ID'].unique()

    for id in id_values:
        values= df_sorted.index[df_sorted['ID']==id].to_list()
        for value in values:
            df_sorted.loc[value,'DATA_ID'] = df_sorted.loc[value,'Week'] + df_sorted.loc[value,'ID']

    data_id_values = df_sorted['DATA_ID'].unique()

    for id in data_id_values:

        values = df_sorted.index[df_sorted['DATA_ID'] == id].to_list()
    
        for age in casting_age:
            mask = (df_sorted['DATA_ID'] == id) & (df_sorted['Sample_Age'] == age)
            id_value = df_sorted[mask]['Strength'].to_list()
            ind = df_sorted.index[mask].to_list()
            if not id_value:
                continue
            
            out = id_value.copy()

            # ---- FIRST OUTLIER CHECK (50% for all) ----
            outliers1 = Outliers(out, 0.40)
            if outliers1 and not re.search(r"[A-Z]+BR\d+", id):
                out = [v for i, v in enumerate(out) if i not in outliers1]
            #print(id, out, len(out))\n",
            
            # ---- SECOND OUTLIER CHECK ----\n",
            second_percentage = percentage_outliers2 if age == 28 else percentage_outliers1
            outliers2 = Outliers(out, second_percentage)
            
            if outliers2 and not re.search(r"[A-Z]+BR\d+", id):
                out = [v for i, v in enumerate(out) if i not in outliers2]
            
            #print(id, out, len(out))

            # ---- SAVE RESULTS ----
            if ind:
                temp_mean = np.round(np.mean(out),4)
                temp_stdev = np.std(out, ddof=1)
                n = len(out)
                margin = 1.96 * (temp_stdev / np.sqrt(n))
                lower_95 = temp_mean-margin
                df_sorted.loc[ind[0],f'Mean {age}'] = temp_mean
                df_sorted.loc[ind[0],f'STDEV {age}'] = temp_stdev
                df_sorted.loc[ind[0],f'95% Confidence {age}'] = lower_95
                df_sorted.loc[ind[0],f'Outlier {age}'] = len(id_value) - n

    return df_sorted

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

directory = "/home/jessicamaldonado/OneDrive/Results_mortar/Logs/"
base_excel_file = "/home/jessicamaldonado/OneDrive/Calendars/Calendar_materials.xlsx"
base_excel_file_formulations = (
    "/home/jessicamaldonado/OneDrive/Formulation lab/"
    "Formulations Lab Research and Production Plan.xlsx"
)
output_path = os.path.join(
    "/home/jessicamaldonado/OneDrive/Data Lab/Datasets/Mortar/"
)

path_dataset_QA = '/home/jessicamaldonado/OneDrive/Data Lab/Datasets/QA/Mortar/'
base_excel_file_qa = '/home/jessicamaldonado/OneDrive/Formulation lab/Testing_calendar/QA_Results_Lab_NS.xlsx'
contents = os.listdir(directory)

files = []
for item in contents:
    if re.search(r"\w*.txt", item):
        files.append(item)

compression_dataset = []
flexural_dataset = []

for i, file in enumerate(files):
    path = directory + file
    time_stamp = conver_time_stamp(file)

    with open(path) as file:
        lines = file.readlines()

    test = conver_string_parameter(lines, 29)
    id = conver_string_parameter(lines, 26)
    id = id.removesuffix(" ")
    id = id.split(sep="-")

    operator = conver_string_parameter(lines, 16)
    sample_age = conver_string_parameter(lines, 9)
    sample_number = conver_string_parameter(lines, 21)
    depth = conver_string_parameter(lines, 7)

    try:
        value = float(conver_string_parameter(lines, -1))
        load = conver_string_parameter(lines, -2)
        strength = value
        comment = "NA"
    except ValueError:
        value = conver_string_parameter(lines, -1)
        load = conver_string_parameter(lines, -3)
        strength = conver_string_parameter(lines, -2)
        comment = conver_string_parameter(lines, -1)

    print(time_stamp)

    if re.search(r"^C1?$|^c1?$", test):
        compression_dataset.append([test, id[0], id[1], sample_age, sample_number, float(depth),
            float(load), float(strength), operator, time_stamp[0], time_stamp[1], comment,
        ])

    if re.search(r"C2|F|f", test):
        flexural_dataset.append([
            test, id[0], id[1], sample_age, sample_number, float(depth),
            float(load), float(strength), operator, time_stamp[0], time_stamp[1], comment,
        ])

columns = [
    "Test_type",
    "Week",
    "ID",
    "Sample_Age",
    "Sample_number",
    "Depth",
    "Load",
    "Strength",
    "Operator",
    "Date",
    "Time",
    "Comment",
]

df_compressive = pd.DataFrame(compression_dataset, columns=columns)
df_flexural = pd.DataFrame(flexural_dataset, columns=columns)

old_sample_age = [
    "1",
    "3",
    "4",
    "7",
    "8",
    "14",
    "15",
    "28",
    "29",
    "30",
    "28 dd",
    "27",
    "21",
]

new_sample_age = [
    1,
    3,
    3,
    7,
    7,
    14,
    14,
    28,
    28,
    28,
    28,
    28,
    21,
]

change_sample_age(old_sample_age, new_sample_age, df_compressive)
change_sample_age(old_sample_age, new_sample_age, df_flexural)

casting_age = [1, 3, 7, 14, 28, 21]

print("Processing compressive strength")
df_compressive_sorted = pre_process_dataset(df_compressive, casting_age, 1, 1)
print("Finished!")

print("Processing flexural strength")
df_flexural_sorted = pre_process_dataset(df_flexural, casting_age, 1, 1)
print("Finished!")

df_flexural_sorted["Date"] = pd.to_datetime(df_flexural_sorted["Date"], dayfirst=True)
df_flexural_sorted["Sample_Age"] = df_flexural_sorted["Sample_Age"].astype(int)

df_flexural_sorted["Casting_Date"] = (df_flexural_sorted["Date"]- pd.to_timedelta(df_flexural_sorted["Sample_Age"], unit="D"))

df_compressive_sorted["Date"] = pd.to_datetime(df_compressive_sorted["Date"], dayfirst=True)
df_compressive_sorted["Sample_Age"] = df_compressive_sorted["Sample_Age"].astype(int)

df_compressive_sorted["Casting_Date"] = (df_compressive_sorted["Date"]- pd.to_timedelta(df_compressive_sorted["Sample_Age"], unit="D"))

df_compressive_sorted["Casting_Year"] = (df_compressive_sorted["Casting_Date"].dt.year)

df_compressive_sorted["data_id_with_year"] = (df_compressive_sorted["DATA_ID"]+ "-"+ df_compressive_sorted["Casting_Year"].astype(str))

df_flexural_sorted["Casting_Year"] = (df_flexural_sorted["Casting_Date"].dt.year)

df_flexural_sorted["data_id_with_year"] = (df_flexural_sorted["DATA_ID"]+ "-"+ df_flexural_sorted["Casting_Year"].astype(str))

df_compressive_sorted = df_compressive_sorted[
    [
        "Test_type",
        "Week",
        "ID",
        "Sample_Age",
        "Sample_number",
        "Depth",
        "Load",
        "Strength",
        "Operator",
        "Date",
        "Time",
        "Casting_Date",
        "Comment",
        "DATA_ID",
        "data_id_with_year",
        "Mean 1",
        "STDEV 1",
        "95% Confidence 1",
        "Outlier 1",
        "Mean 7",
        "STDEV 7",
        "95% Confidence 7",
        "Outlier 7",
        "Mean 14",
        "STDEV 14",
        "95% Confidence 14",
        "Outlier 14",
        "Mean 28",
        "STDEV 28",
        "95% Confidence 28",
        "Outlier 28",
        "Mean 3",
        "STDEV 3",
        "95% Confidence 3",
        "Outlier 3",
    ]
]
def load_and_prepare(sheet_name):
    df = pd.read_excel(base_excel_file, sheet_name)

    cols = ["Day", "D1", "D3", "D7", "D14", "D28"]

    df["Week"] = df["Week"].astype(str)
    df[cols] = df[cols].apply(pd.to_datetime, dayfirst=True)

    return df


mortar_mixer_data = load_and_prepare("Table_mortar")

data_compressive_sm = pd.merge(
    mortar_mixer_data,
    df_compressive_sorted,
    on=["data_id_with_year", "Week"],
)

data_compressive_sm["Mixer"] = "SM"

data_flexural_sm = pd.merge(
    mortar_mixer_data,
    df_flexural_sorted,
    on=["data_id_with_year", "Week"],
)

data_flexural_sm["Mixer"] = "SM"

data_compressive_all = pd.concat(
    [data_compressive_sm, data_flexural_sm],
    ignore_index=True,
)

data_compressive_all["Mix Design"] = (
    data_compressive_all["ID"].apply(extract_mix_design)
)

data_compressive_all['Mixing'] = data_compressive_all['Day'] + pd.to_timedelta(data_compressive_all['Mixing Time'].astype(str))
data_compressive_all['Testing'] = data_compressive_all['Date'] + pd.to_timedelta(data_compressive_all['Time'])

data_compressive_all['Tolerance'] = data_compressive_all['Testing'] - data_compressive_all['Mixing']
data_compressive_all['Tolerance_hh'] = data_compressive_all['Tolerance'].dt.total_seconds() / 3600


df_CRT_formulation = pd.read_excel(
    base_excel_file_formulations,
    "CRT Sample List",
)

df_MFB_formulation = pd.read_excel(
    base_excel_file_formulations,
    "MFB Sample List",
)

df_CRT_formulation = df_CRT_formulation.rename(
    columns={"Batch": "CRT", "Bulk CRT": "MFB"}
)

df_MFB_formulation = df_MFB_formulation.rename(
    columns={"Batch": "MFB"}
)

df_formulation = df_CRT_formulation.merge(
    df_MFB_formulation,
    on="MFB",
    how="left",
)

df_formulation = df_formulation.rename(
    columns={"MFB": "Bulk CRT"}
)

df_test = data_compressive_all.merge(
    df_formulation,
    on="CRT",
    how="left",
)


df_QA_formulation = pd.read_excel(base_excel_file_qa, 'Raw')
df_QA_formulation = df_QA_formulation.dropna(subset=['Batch'])
#df_QA_CRT = df_QA_formulation[df_QA_formulation['Batch'].str.startswith('CRT')]
df_QA_MFB = df_QA_formulation[df_QA_formulation['Batch'].str.startswith('MFB')]
df_QA_formulation = df_QA_formulation.rename(columns={"Batch": "CRT"})

df_qa_test = df_test.merge(df_QA_formulation, on='CRT', how='left')


df_test_complete = df_qa_test[['Week', 'Day', 'Mortar SM', 'Test-Mortar', 'Project_x', 'Formulation', 'CRT', 'Subindex', 
                                'Dosage', 'Flow', 'Mixing Time', 'ID-Mortar', 'data_id_with_year', 
                                'Test_type', 'ID', 'Sample_Age', 'Sample_number', 'Depth', 'Load', 'Strength', 'Operator', 'Date', 
                                'Time', 'Casting_Date', 'Comment', 'DATA_ID', 'Casting_Year', 'Mix Design', 'Mixing', 'Testing', 'Tolerance', 'Tolerance_hh', 
                                'Tech_x', 'Date_x', 'Project_y', 'Project Notation', 'Date Finished_x', 'Reason_x', 'Test Spec_x', 'Bulk CRT', 'GNP_x', 'GO_x', 'Ratio_x', 'GR%_x', 
                                'Mixer_y', 'Speed (RPM)_x', 'Mix Duration (min)_x', 'SP_x', 'SP Amount_x', 'Notes_x', 'Date_y', 'Tech_y', 'Campaign', 'Form Project', 'Date Finished_y', 
                                'Reason_y', 'Test Spec_y', 'GNP_y', 'GO_y', 'Additive Package', 'Ratio_y', 'GR%_y', 'Speed (RPM)_y', 'Mix Duration (min)_y', 'SP_y', 'SP Amount_y', 'Notes_y', 
                                'Project', 'D#', 'Test', 'PSD GO - 10', 'PSD GO - 50', 'PSD GO - 90', 'Pre PSD - 10', 'Pre PSD - 50', 'Pre PSD - 90', 'PSD CRT - 10', 'PSD CRT - 50', 'PSD CRT - 90', 
                                'Initial Rheo - Tsi', 'Final Rheo - Tsi', 'Turb - cP', 'VC -Pass/Fail', 'Other', 'Results - PSD', 'Results - Rheo', 'Results - Turb']]

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

df_columns = df_test_complete_2.columns.to_list()
print(df_columns)

df_qa_complete = df_test_complete_2[['Week', 'Day', 'Mortar SM', 'Test-Mortar', 'Project_x', 'Formulation', 'CRT', 'Subindex', 
                                'Dosage', 'Flow', 'Mixing Time', 'ID-Mortar', 'data_id_with_year', 
                                'Test_type', 'ID', 'Sample_Age', 'Sample_number', 'Depth', 'Load', 'Strength', 'Operator', 'Date', 
                                'Time', 'Casting_Date', 'Comment', 'DATA_ID', 'Casting_Year', 'Mix Design', 'Mixing', 'Testing', 'Tolerance', 'Tolerance_hh', 
                                'Tech_x', 'Date_x', 'Project_y', 'Project Notation', 'Date Finished_x', 'Reason_x', 'Test Spec_x', 'Bulk CRT', 'GNP_x', 'GO_x', 'Ratio_x', 'GR%_x', 
                                'Mixer_y', 'Speed (RPM)_x', 'Mix Duration (min)_x', 'SP_x', 'SP Amount_x', 'Notes_x', 'Date_y', 'Tech_y', 'Campaign', 'Form Project', 'Date Finished_y', 
                                'Reason_y', 'Test Spec_y', 'GNP_y', 'GO_y', 'Additive Package', 'Ratio_y', 'GR%_y', 'Speed (RPM)_y', 'Mix Duration (min)_y', 'SP_y', 'SP Amount_y', 'Notes_y', 
                                'Project', 'D#', 'Test', 'PSD GO - 10', 'PSD GO - 50', 'PSD GO - 90', 'Pre PSD - 10', 'Pre PSD - 50', 'Pre PSD - 90', 'PSD CRT - 10', 'PSD CRT - 50', 'PSD CRT - 90', 
                                'Initial Rheo - Tsi', 'Final Rheo - Tsi', 'Turb - cP', 'VC -Pass/Fail', 'Other', 'Results - PSD', 'Results - Rheo', 'Results - Turb']]


projects_name = df_test["Project_x"].unique()

for name in projects_name:
    dataset_search = df_test[
        (df_test["ID"].str.startswith(("C", "G")))
        & (df_test["Project_x"].str.startswith(f"{name}"))
    ]

    dataset_search.to_csv(output_path + "/CSV/" + f'Results_{name}.csv')
    dataset_search.to_excel(output_path + "/Excel/" + f'Results_{name}.xlsx')

    dataset_search_qa = df_qa_complete[
            (df_qa_complete["ID"].str.startswith(( "G")))
            & (df_qa_complete["Project_x"].str.startswith(f"{name}"))
        ]

    dataset_search_qa.to_excel(path_dataset_QA + f'Results_{name}.xlsx')

print("Excel and CSV exported!")