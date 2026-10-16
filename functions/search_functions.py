# Import libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.transforms as tr
from scipy.stats import norm
import seaborn as sns
import functions.functions as dataset


def search_by_formulation(search_formulation, 
                          df_search, df_formulation, avg_baseline = [18.63305, 39.60014, 43.59121, 46.30873]):
    id_search = []

    for fomulation in search_formulation:
        df = df_formulation[df_formulation['Graphene Label'].str.endswith(fomulation)]
        ids = df['DATA_ID'].unique()
        id_search = id_search + list(ids)

    search_results = []
    avg_divided = []

    for id in id_search:
        average, median_ad, mean_ad, std, size, error  = dataset.search_by_ID_age(df_search,id)
        formulation = df_search[df_search['DATA_ID'] == id]['Graphene Label'].to_list()
        dosage = df_search[df_search['DATA_ID'] == id]['Graphene Dosage %'].to_list()
        avg_divided.append(median_ad[1])
        print(avg_baseline)
        ratio = [np.round((item1 / item2 - 1) * 100, 3) for item1, item2 in zip(average,avg_baseline)]
        search_results.append([formulation[0], dosage[0], id, average, median_ad, mean_ad, std, size, error, ratio])
    
    columns_search = ['Formulation', 'Dosage', 'ID', 'Average', 'Median AD', 'Mean AD', 'STD', 'Sample Size', 'Error', 'Ratio %']
    df_search_results = pd.DataFrame(search_results, columns=columns_search)
    return df_search_results, id_search

def search_using_params (id_search, df_search, param_search):
    search_results = []

    for id in id_search:
        df_provisional = df_search[df_search['DATA_ID'].str.endswith(id)]
        average, median_ad, mean_ad, std, size, error, max_mean, min_mean, cv_percentage  = dataset.sumarize_statistics(df_provisional, 0, param_search)
        search_results.append([id, average, median_ad, mean_ad, std, size, error, max_mean, min_mean, cv_percentage])

    columns_search = ['ID', 'Average', 'Median AD', 'Mean AD', 'STD', 'Sample Size','Error', 'Max+STD', 'Max-STD', 'CV%']
    df_search_results = pd.DataFrame(search_results, columns=columns_search)

    return df_search_results

def search_by_id(id_search, marks, df_search):
    search_results = []

    for id in id_search:
        average, median_ad, mean_ad, std, size, error, max_mean, min_mean, cv_percentage, sample_outliers, percentage_95 = dataset.search_by_ID_age(df_search,id, marks=marks)
        #flex_mean = comp_flex[comp_flex['ID_y'].str.startswith(id)]['Mean 28_y'].mean()
        search_results.append([id, average, median_ad, mean_ad, std, size, error, max_mean, min_mean, cv_percentage, sample_outliers, percentage_95])

    columns_search = ['ID', 'Average', 'Median AD', 'Mean AD', 'STD', 'Sample Size','Error', 'Max+STD', 'Max-STD', 'CV%', 'Size Outliers', '95% percentage']
    df_search_results = pd.DataFrame(search_results, columns=columns_search)

    return df_search_results

def nd_search_results(type: str, id_search, df_search_results, color, text, min, max, age):
    color_graph = []
    text_graph = []
    avg_searc = []
    #medianad_searc = []
    meanad_searc= []

    for i,item in enumerate(id_search):
        color_graph.append(color[i])
        text_graph.append(text[i])

    a = np.array(df_search_results['Average'].to_list())
    b = np.array(df_search_results['Mean AD'].to_list())
    c = np.array(df_search_results['Error'].to_list())

    marks = [1, 3, 7, 14, 28]

    index_id = [i for i, mark in enumerate(marks) if mark == age]

    if type == 'ID':

        avg_searc = list([a[:, i] for i in range(a.shape[1])])
        meanad_searc = list([b[:, i] for i in range(b.shape[1])])
        error_searc = list([c[:, i] for i in range(c.shape[1])])

        normal_dist = []
        index_id = index_id[0]

        for index, value in enumerate(avg_searc[index_id]):
            normal_dist.append(dataset.graphs_normal_dist(min, max, value, meanad_searc[index_id][index], error_searc[index_id][index]))


    elif type == 'Slump':
        avg_searc = a
        meanad_searc = b 
        error_searc = c

        normal_dist = []

        for index, value in enumerate(avg_searc):
            normal_dist.append(dataset.graphs_normal_dist(min, max, value, meanad_searc[index], error_searc[index]))

    return normal_dist, color_graph, text_graph

def graph_search_results(type, df_search_results, normal_dist, color_graph, text_graph, text_x, age, text, save_path):
    ids = df_search_results['ID'].to_list()
    #ids[-2] = 'All1'
    ids[-1] = 'All'

    for i, id in enumerate(ids):
        plt.plot(normal_dist[i][0], normal_dist[i][1], color_graph[i], label = id)
        if type == 'Slump':
            plt.text(text_x, text_graph[i], f'CI({id}) : {normal_dist[i][2]} \n', fontsize = 10)
            xlabel = 'SLUMP (mm)'
            title = 'Normal Distribution'
        if type == 'ID':
            plt.text(text_x, text_graph[i]*10, f'CI({id}) : {normal_dist[i][2]} \n', fontsize = 10)
            xlabel = 'Mpa'
            title = f'Normal Distribution {age}-D'

    plt.title(title)
    plt.xlabel(xlabel)
    #plt.ylim(0,0.1)
    plt.ylabel('Distribution')
    #plt.legend(bbox_to_anchor=(2.1, 1.05))
    plt.legend(loc = 'best')
    plt.grid(True)
    plt.savefig(save_path + '\\' f'{title}_{type}_{text}.png', dpi = 500, bbox_inches = tr.Bbox([[0, 0], [10, 5]]))
    plt.show()

def divided_columns_results(df, changes, names):
    i = df['ID'].unique()
    for ID in i:
        j = df.index[df['ID']==ID].to_list()
        for c in changes:
            ratio = df[df['ID']==ID][c].to_list()
            for r in enumerate(ratio[0]):
                df.loc[j, f'{c}_{names[r[0]]}'] = r[1]
    df = df.drop(columns=changes)
    return df

def suffix_file_name(id):
    chr_remove = ['(', ')', "'",' ']
    text = id[-1]
    print(text)
    for chr in chr_remove:
        text = str(text).replace(chr,'')
    text = text.replace(',', '_')
    print(text)
    return text