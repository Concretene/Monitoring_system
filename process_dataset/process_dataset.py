# Import libraries
import os
import re
import numpy as np
import pandas as pd
from scipy.stats import norm
from functions.functions import conver_time_stamp, conver_string_parameter
from functions.functions import change_sample_age, pre_process_dataset



def contol1_dataset(directory: str 
                    #= r"C:\Users\JessicaMaldo_p3rvdgi\OneDrive - Concretene\Results\Controls 1\Logs\\"
                    = '/home/jessicamaldonado/OneDrive/Results/Controls 1/Logs/' 
                    # = '/home/jessicamaldonado/OneDrive/Data/Materials_data_2024/Logs_2024/Trials_2024/'
                     ):
    contents = os.listdir(directory)
    files = []
    for item in contents:
        if re.search('\w*.txt'
            #r"\w*.txt"
            ,item):
            files.append(item)
    
    compression_dataset = []
    flexural_dataset = []
    cement_test = []
    
    for i, file in enumerate(files):
        path = directory + file
        time_stamp = conver_time_stamp(file)
        with open(path) as file:
            
            lines = file.readlines()
            #print(lines)
        test = conver_string_parameter(lines,1)
        id = conver_string_parameter(lines,17)
        id = id.removesuffix(' ')
        id = id.split(sep='-')
        print(time_stamp)
        operator = conver_string_parameter(lines,16)
        sample_age = conver_string_parameter(lines,9)
        sample_number = conver_string_parameter(lines,21)
        depth = conver_string_parameter(lines,7)
        try:
            value = float(conver_string_parameter(lines,-1))
            load = conver_string_parameter(lines,-2)
            strength = value
            comment = "NA"
        except ValueError:
            value = conver_string_parameter(lines,-1)
            load = conver_string_parameter(lines,-3)
            strength = conver_string_parameter(lines,-2)
            comment = conver_string_parameter(lines,-1)
        
        #if value.isdigit():
        #else:
        #    print("Ok")
        #    print("EXCEPT")
        #    print(lines)
        #    print(conver_string_parameter(lines,-3))
        #    #load = conver_string_parameter(lines,-3)
        #    #strength = conver_string_parameter(lines,-2)

        #coment = conver_string_parameter(lines,-1)
        #print(test, id, operator, sample_age, time_stamp)
        if re.search(r"Compression \w",test):
            compression_dataset.append([test,id[0],id[1],sample_age,sample_number,float(depth),float(load),float(strength),operator,time_stamp[0],time_stamp[1], comment])
        if re.search(r"Flexural \w",test):
            flexural_dataset.append([test,id[0],id[1], sample_age,sample_number,float(depth),float(load),float(strength),operator,time_stamp[0],time_stamp[1]])
        if re.search(r"Cement \w",test):
            cement_test.append([test,id[0],id[1], sample_age,sample_number,float(depth),float(load),float(strength),operator,time_stamp[0],time_stamp[1]])
    
    columns = ['Test_type','Week','ID','Sample_Age','Sample_number','Depth','Load','Strength','Operator','Date','Time']
    columns_n = ['Test_type','Week','ID','Sample_Age','Sample_number','Depth','Load','Strength','Operator','Date','Time','Comment']
    
    df_compressive = pd.DataFrame(compression_dataset, columns = columns_n)
    df_flexural = pd.DataFrame(flexural_dataset,columns = columns)
    df_cement = pd.DataFrame(cement_test,columns = columns)
    # Change the data type of sample age
    
    old_sample_age = ['1', '3', ' 7', '7', '8', '14', '15', '27', '28', '29', '30']
    new_sample_age = [1, 3, 7, 7, 7, 14, 14, 28, 28, 28, 28]
    
    old_sample_age_flexural = ['28 dd', '29', '28']
    new_sample_age_flexural = [28, 28, 28]
    
    old_sample_age_cement = ['7', '8', '14', '15', '28', '29', '30', '31']
    new_sample_cement = [7, 7, 14, 14, 28, 28, 28, 28]
    
    change_sample_age(old_sample_age, new_sample_age, df_compressive)
    change_sample_age(old_sample_age_flexural, new_sample_age_flexural, df_flexural)
    change_sample_age(old_sample_age_cement, new_sample_cement, df_cement)
    
    # Strenght calculated and tested
    df_compressive["Strength_calculated"] = np.round(df_compressive["Load"]/df_compressive["Depth"]*10,2)
    df_compressive["Calibration Test"] = np.where(np.absolute(df_compressive["Strength_calculated"]-df_compressive["Strength"])<0.2, "PASS", "FAIL")
    
    casting_age_compressive = [1, 3, 7, 14, 28]
    print("Processing compressive strength")
    df_compressive_sorted = pre_process_dataset(df_compressive, casting_age_compressive, 1)
    print('Finished!')
    #print(df_compressive_sorted.to_string())
    
    casting_age_flex = [28]
    print("Processing flexural strength")
    df_flexural_sorted = pre_process_dataset(df_flexural, casting_age_flex, 0.28)
    print('Finished!')
    #print(df_flexural_sorted.to_string())
    
    casting_age_cement = [7, 14, 28]
    print("Processing morter")
    df_cement_sorted = pre_process_dataset(df_cement, casting_age_cement, 1)
    print('Finished!')

    return df_compressive_sorted, df_flexural_sorted, df_cement_sorted

def materials_params_dataset(directory_params: str 
                             #= r"C:\Users\JessicaMaldo_p3rvdgi\OneDrive - Concretene\Concrete lab\Software\Documents\\"
                             = '/home/jessicamaldonado/OneDrive/Concrete lab/Software/Documents/'
                             #='/home/jessicamaldonado/OneDrive/Concrete lab/Software/Documents/2024/'
                             ):
# Download, clean, and create params dataset. Dataset filter by casted

    contents = os.listdir(directory_params)
    files = []
    for item in contents:
        if re.search('materials_param\w*.csv'
            #r"materials\w*.csv"
            ,item):
            files.append(item)
            print(files)
    df_params = pd.read_csv(directory_params + files[0])
    #print(directory_params + "/" + files[0])
    #print(df_params)
    #df_params = df_params.drop([0,1,2,3,4,5,6,7,30,31,32]) #OLD RECORDS
    df_params['ID'] = df_params['ID'].str.removesuffix(' ')
    id_complete = df_params['ID'].to_list()
    for item in id_complete:
        [week,id] = item.split(sep='-')
        index = (df_params.index[df_params['ID']==item]).to_list()
        df_params.loc[index,'ID'] = id
        df_params.loc[index,'Week'] = week

    columns = df_params.columns.to_list()
    print(columns)
    columns = [columns[-1],columns[0]] + columns[1:len(columns)-1]
    print(columns)
    columns = columns[0:8] + [columns[12], columns[14], columns[15], columns[16], 
                              columns[len(columns)-9], columns[len(columns)-8],
                              columns[len(columns)-7],
                              columns[len(columns)-6], columns[len(columns)-5],
                              columns[len(columns)-4], columns[len(columns)-3], columns[len(columns)-2], columns[-1]]
    print(columns)
    df_params = df_params[columns]
    df_params = df_params.reset_index(drop=True)
    #print(df_params.to_string())
    df_params['Air Content'].replace(['-'], np.nan, inplace=True)
    df_params['Air Content'] = df_params['Air Content'].astype(float)
    df_params['Flow'] = df_params['Flow'].astype(float)
    #index_params_change = [182, 183, 184, 185, 199, 218] #OLD RECORDS
    #value_params_change = [160, 130, 130, 150, 90, 110]
    #for i, value in enumerate(value_params_change):
    #    #print(index_params_change[i])
    #    df_params.loc[index_params_change[i],'Slump'] = value

    df_params['Slump'] = df_params['Slump'].astype(float)
    #df_params = df_params.drop(index = [23, 24, 25, 26, 277]) #OLD RECORDS

    id_values = df_params['ID'].unique()

    for id in id_values:
        values= df_params.index[df_params['ID']==id].to_list()
        for value in values:
            df_params.loc[value,'DATA_ID'] = df_params.loc[value,'Week'] + df_params.loc[value,'ID']

    df_params['Graphene Dosage %'] = df_params['Graphene Dosage %'].astype(str)
    df_params['Graphene Label'] = df_params['Graphene Label'].str.replace(r'-\d+', '', regex=True)
    df_params['Graphene Label'] = df_params['Graphene Label'].str.replace(r'2024-', '', regex=True)
    df_params['Week'] = df_params['Week'].astype(str)
    #df_params['Sand Moisture'].replace('-', np.nan, inplace = True) #OLD RECORDS
    df_params['Coarse Aggregate 10mm'].replace('-', np.nan, inplace = True)
    df_params['Limestone Moisture'].replace('-', np.nan, inplace = True)
    df_params['Limestone Moisture'].replace('2,12', '2.12', inplace = True)
    df_params['Sand Moisture'] = df_params['Sand Moisture'].astype(float)
    df_params['Coarse Aggregate 10mm'] = df_params['Coarse Aggregate 10mm'].astype(float)
    df_params['Limestone Moisture'] = df_params['Limestone Moisture'].astype(float)


    df_params['Flow'] = df_params['Flow'].astype(float)
    df_params['Paste T C'].replace('-', np.nan, inplace=True)
    df_params['Paste T C'] = df_params['Paste T C'].astype(float)
    df_params['Room T C'] = df_params['Room T C'].astype(float)
    df_params['Cubes'].replace('Y', np.nan, inplace=True)
    df_params['Cubes'] = df_params['Cubes'].astype(float)

    return df_params
