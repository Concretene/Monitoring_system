# Import libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import norm
import scipy
import re

# User define functions
def conver_string_parameter (list,index):
    if len(list[index].split(sep='"'))==1:
        _,_,parameter = list[index].split(sep=" ")
        parameter = parameter.replace('"',"")
        parameter = parameter.replace('\n',"")
        return parameter
    else:
        _,parameter,_ = list[index].split(sep='"')
        return parameter

def conver_time_stamp(file):
    remove_date = file.replace('.txt', '')
    remove_date = remove_date.replace('_Last test', '')
    remove_date = remove_date.split(sep = '_')
    date = remove_date[0] + '/' + remove_date[1] + '/' + remove_date[2]
    time = remove_date[3] + ':' + remove_date[4] + ':' + remove_date[5]
    time_stamp = [date, time]
    return time_stamp

def mad(arr):
    """ Median Absolute Deviation: a "Robust" version of standard deviation.
        Indices variabililty of the sample.
        https://en.wikipedia.org/wiki/Median_absolute_deviation 
    """
    #arr = np.ma.array(arr).compressed() # should be faster to not use masked arrays.
    med = np.median(arr)
    return np.median(np.abs(arr - med))

def mad_mean(data, axis=None):
    return np.mean(np.absolute(data - np.mean(data, axis)), axis)

def change_sample_age(old_samples_age:list,new_samples_age:list,dataframe):
    for index,age in enumerate(old_samples_age):
        dataframe.loc[dataframe.index[dataframe['Sample_Age']==age].to_list(),'Sample_Age'] = new_samples_age[index]

def sumarize_statistics(dataframe,day, set_stat: str = 'Strength'):
    if set_stat == 'Strength':
        array_df_mean = dataframe[(dataframe['Sample_Age']==day)][f'Mean {day}'].dropna().to_list()
        array_df_global = dataframe[(dataframe['Sample_Age']==day)][set_stat].dropna().to_list()
    else:
        array_df_global = dataframe[set_stat].to_list()
        array_df_mean = array_df_global
    
    array_df_percentage = dataframe[(dataframe['Sample_Age']==day)][f'95% Confidence {day}'].dropna().to_list()
    mean_dataframe = np.round(np.mean(array_df_mean),4)
    median_ad = np.round(np.median(array_df_global),4)
    mean_ad = np.round(mad_mean(array_df_global),4)
    std_dataframe = np.round(np.std(array_df_global),4)
    counts = len(array_df_global)
    try:
        outliers_samples = dataframe[(dataframe['Sample_Age']==day)][f'Outlier {day}'].dropna().to_list()
    except:
        outliers_samples = np.nan
    #outliers_samples = dataframe[(dataframe['Sample_Age']==day)][f'Outlier {day}'].dropna().to_list()
    error = np.round(scipy.stats.sem(array_df_global),4)
    max_mean = np.round(np.round(np.mean(array_df_mean),4) + np.round(np.std(array_df_global),4),4)
    min_mean = np.round(np.round(np.mean(array_df_mean),4) - np.round(np.std(array_df_global),4),4)
    cv_percentage = np.round( (max_mean/mean_dataframe-1)*100 , 4)
    percentage_95 = round(array_df_percentage[0], 4) if array_df_percentage else None
    print(percentage_95)
    
    return mean_dataframe, median_ad, mean_ad, std_dataframe, counts, error, max_mean, min_mean, cv_percentage, outliers_samples, percentage_95

def search_by_ID_age(dataframe, search_id : str,age : int = 0,week: str = '0', marks: list = [1 , 7, 14, 28]):
        
    dataframe_search = dataframe[dataframe['DATA_ID'].str.endswith(search_id)]
    #print(dataframe_search.to_string())
    
    ##Default values
    if week == '0':
        week = dataframe_search['Week']
    dataframe_search = dataframe_search[dataframe_search['Week']==week]

    if age == 0:
        age = dataframe_search['Sample_Age']

    statistics = []
    for mark in marks:
     statistics.append(sumarize_statistics(dataframe_search, mark))
    #print(statistics)
    average = [item[0] for item in statistics]
    median_ad = [item[1] for item in statistics]
    mean_ad = [item[2] for item in statistics]
    std = [item[3] for item in statistics]
    size = [item[4] for item in statistics]
    error = [item[5] for item in statistics]
    max_mean = [item[6] for item in statistics]
    min_mean = [item[7] for item in statistics]
    cv_percentage = [item[8] for item in statistics]
    outliers_samples = [item[9] for item in statistics]
    percentage_95 = [item[10] for item in statistics]

    print(f'====Statistics {search_id}===========\n'
          f'==Average==Median AD==Mean AD==STD==Size===\n'
          f'Day1: {statistics[0][0]} , {statistics[0][1]}, {statistics[0][2]}, {statistics[0][3]}, {statistics[0][4]}\n'
          f'Day7: {statistics[1][0]} , {statistics[1][1]}, {statistics[1][2]}, {statistics[1][3]}, {statistics[1][4]}\n'
          f'Day14: {statistics[2][0]} , {statistics[2][1]}, {statistics[2][2]}, {statistics[2][3]}, {statistics[2][4]}\n'
          f'Day28: {statistics[3][0]} , {statistics[3][1]}, {statistics[3][2]}, {statistics[3][3]}, {statistics[3][4]}\n'
          )
    
    #print(dataframe_search[dataframe_search['Sample_Age']==age].to_string())

    return average, median_ad, mean_ad, std, size, error, max_mean, min_mean, cv_percentage, outliers_samples, percentage_95

def graphs (x,y,error):
    x_points = x
    y_points = y

    plt.plot(x_points, y_points)
    for i,j in zip(x_points,y_points):
            plt.annotate(str(j),xy=(i,j+1))
    plt.title('Average')
    plt.xlabel('Casting Age')
    plt.ylabel('MPa')
    plt.errorbar(x_points, y_points, 
             yerr = error, 
             fmt ='o')
    plt.grid(True)
    plt.show()

def Outliers(values: list, percentage: float):
    outliers = []
    n1 = []

    new_values = [n1.append(value) if value > 2 else  outliers.append(index) for index, value in enumerate(values)]

    for index, value in enumerate(n1):
        n = n1.copy()
        n.remove(value)
        #print(n)
        n = np.array(n)
        #print(n)
        o_max = n.mean() * (1 + percentage)
        o_min = n.mean() * (1 - percentage)
        if value >= o_max or value <= o_min:
            #print(True, index, values)
            outliers.append(index)
        #print(outliers)
    return outliers

def pre_process_dataset(data_frame, casting_age, percentage_outliers):

    df_sorted = data_frame.sort_values(by=['Week','ID','Sample_Age'])
    df_sorted['ID'] = df_sorted['ID'].str.removesuffix(' ')
    id_values = df_sorted['ID'].unique()

    for id in id_values:
        values= df_sorted.index[df_sorted['ID']==id].to_list()
        for value in values:
            df_sorted.loc[value,'DATA_ID'] = df_sorted.loc[value,'Week'] + df_sorted.loc[value,'ID']

    data_id_values = df_sorted['DATA_ID'].unique()

    for id in data_id_values:
        values= df_sorted.index[df_sorted['DATA_ID']==id].to_list()
        for age in casting_age:
            id_value = df_sorted[(df_sorted['DATA_ID']==id) & (df_sorted['Sample_Age']==age)]['Strength'].to_list()
            ind = df_sorted.index[(df_sorted['DATA_ID']==id) & (df_sorted['Sample_Age']==age)].to_list()
            outliers = Outliers(id_value,percentage_outliers)
            if outliers and not re.search(r"[A-Z]+BR\d", id):
                out = [v for i, v in enumerate(id_value) if i not in outliers]
                #print(out, len(out))
            else:
                out = id_value.copy()
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
                #print(len(out), len(id_value))
    return  df_sorted

def graphs_normal_dist(x_min,x_man,mean,std, error):
    x_axis = np.arange(x_min, x_man, 0.001)
    ci = scipy.stats.norm.interval(0.90, loc=mean, scale=error)
    normal_dist = norm.pdf(x_axis,mean,std)
    return x_axis, normal_dist, ci


def create_baseline(id_baseline, type, df_search, casting_age):
    #casting_age = 
    results_baseline = []
    for id in id_baseline:
        average, median_ad, mean_ad, std, size, _, _, _, _  = search_by_ID_age(df_search,id, 0, '0', casting_age)
        results_baseline.append([id, average, median_ad, mean_ad, std, size])

    
    avg_baseline = []
    medianad_baseline = []
    meanad_baseline = []
    sample_size = []

    for ind in enumerate(casting_age):
        avg_baseline.append(np.round(np.mean([item[1][ind[0]] for item in results_baseline]),4))
        medianad_baseline.append(np.round(np.mean([item[2][ind[0]] for item in results_baseline]),4))
        meanad_baseline.append(np.round(np.mean([item[3][ind[0]] for item in results_baseline]),4))
        sample_size.append([item[-1][ind[0]] for item in results_baseline])
    
    if type == 'DOE':
        id_baseline = 'DOE'
        avg_baseline = [18.63305, 39.60014, 43.59121, 46.30873]
        meanad_baseline = [2.2132,	2.7473, 2.4571, 2.9773]

    baseline = {'Formulation' : 'Baseline',
            'ID' : id_baseline,
            'Average' : avg_baseline,
            'Median AD' : medianad_baseline,
            'Mean AD' : meanad_baseline,
            'Sample Size' : sample_size,
            'Ratio %' : [0, 0, 0, 0]
            }
    
    return baseline
