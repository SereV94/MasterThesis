import pandas as pd
import socket


def preprocess_unidirectional_data(filepath):
    """
    Helper function for preprocessing the unidirectional netflows. The ips should be separated from the ports, the date
    values should be taken care of while splitting, while the separator should be converted from space to comma to meet
    the specifications of the rest datasets
    :param filepath: the relative path of the file to be processed
    :return: a file with the preprocessed data is created
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()
    fout = open(filepath + '_preprocessed', 'w')

    column_names = ['date', 'duration', 'protocol', 'src_ip', 'src_port', 'dst_ip', 'dst_port', 'flags', 'tos',
                    'packets', 'bytes', 'flows', 'label']

    fout.write(','.join(column_names) + '\n')
    for i, line in enumerate(lines[1:]):
        elements = []
        columns = line.split()
        for ind in range(len(columns)):
            # take into account that date has a space
            if ind == 1:
                elements += [columns[ind - 1] + ' ' + columns[ind]]
            # split source ips and ports
            elif ind == 4:
                elements += [columns[ind].split(':')[0]]
                elements += ['NaN' if len(columns[ind].split(':')) == 1 or not columns[ind].split(':')[1].isdigit()
                             else columns[ind].split(':')[1]]
            # split destination ips and ports
            elif ind == 6:
                elements += [columns[ind].split(':')[0]]
                elements += ['NaN' if len(columns[ind].split(':')) == 1 or not columns[ind].split(':')[1].isdigit()
                             else columns[ind].split(':')[1]]
            # ignore these two indexes
            elif ind == 0 or ind == 5:
                pass
            else:
                elements += [columns[ind]]

        fout.write(','.join(elements) + '\n')
        if i % 10000:
            print(str(i) + ' lines have been processed...')
    fout.close()


def read_data(filepath, flag='CTU-uni', preprocessing=None, background=True, expl=False):
    """
    Helper function to read the datasets into a Pandas dataframe
    :param filepath: the relative path of the file to be read
    :param flag: flag showing the origin of the dataset (CTU | CICIDS | CIDDS | IOT | USNW)
    :param preprocessing: flag only applicable to the unidirectional Netflow case of CTU-13
    :param background: flag showing if the background data should be removed (for the CTU-13 dataset mostly)
    :param expl: flag regarding the visualization of the error lines in the dataset
    :return: the dataframe with the data
    """
    # if the dataset needs some preprocessing
    if preprocessing:
        preprocess_unidirectional_data(filepath)
        filepath += '_preprocessed'

    # Set the flags for dataframe parsing in the appropriate way for each dataset
    # The values set are the following:
    # delimeter: Delimiter to use to separate the values in each column
    # header: row number to use as header - if it is set to None then no header is inferred
    # names: List of column names to use, in case header is set to None
    # usecols: The set of columns to be used
    # skiprows: The row numbers to skip or the number of rows to skip from the beginning of the document
    # sikpfooter: Number of lines at bottom of file to skip
    # na_values: Additional strings to recognize as NA/NaN
    # parse_field: The columns to parse with the dateparse function
    # dateparse: Function to use for converting a sequence of string columns to an array of datetime instances
    delimiter = ','
    header = None
    skiprows = 1
    skipfooter = 0
    na_values = []
    parse_field = ['date']
    engine = 'python'

    # Unidirectional Netflow data from CTU-13 dataset
    if flag == 'CTU-uni':
        names = ['date', 'duration', 'protocol', 'src_ip', 'src_port', 'dst_ip', 'dst_port', 'flags', 'packets',
                 'bytes', 'label']
        usecols = [_ for _ in range(0, 8)] + [9, 10, 12]
        dateparse = lambda x: pd.datetime.strptime(x, '%Y-%m-%d %H:%M:%S.%f')
    # Bidirectional Netflow data from CTU-13 dataset
    elif flag == 'CTU-bi':
        names = ['date', 'duration', 'protocol', 'src_ip', 'src_port', 'direction', 'dst_ip', 'dst_port', 'state',
                 'packets', 'bytes', 'src_bytes', 'label']
        usecols = [_ for _ in range(0, 9)] + [_ for _ in range(11, 15)]
        dateparse = lambda x: pd.datetime.strptime(x, '%Y/%m/%d %H:%M:%S.%f')
    # Bidirectional Netflow data from the mixed CTU dataset
    elif flag == 'CTU-mixed':
        names = ['date', 'duration', 'protocol', 'src_ip', 'src_port', 'direction', 'dst_ip', 'dst_port', 'state',
                 'packets', 'bytes', 'src_bytes', 'label']
        usecols = [_ for _ in range(0, 9)] + [_ for _ in range(11, 14)] + [16]
        dateparse = lambda x: pd.datetime.strptime(x, '%Y/%m/%d %H:%M:%S.%f')
    # Zeek flow data from IOT-23 dataset
    elif flag == 'IOT':
        delimiter = '\s+'
        names = ['date', 'src_ip', 'src_port', 'dst_ip', 'dst_port', 'protocol', 'service', 'duration',
                 'orig_bytes', 'resp_bytes', 'state', 'missed_bytes', 'orig_packets', 'orig_ip_bytes', 'resp_packets',
                 'resp_ip_bytes', 'label', 'detailed_label']
        usecols = [0] + [_ for _ in range(2, 12)] + [14] + [_ for _ in range(16, 20)] + [21, 22]
        skiprows = 8
        skipfooter = 1
        na_values = ['-']
        dateparse = lambda x: pd.to_datetime(x, unit='s')
    # Netflow data from UNSW-NB15 dataset
    elif flag == 'UNSW':
        names = ['src_ip', 'src_port', 'dst_ip', 'dst_port', 'protocol', 'state', 'duration', 'src_bytes',
                 'dst_bytes', 'missed_src_bytes', 'missed_dst_bytes', 'service', 'src_packets', 'dst_packets',
                 'start_time', 'end_time', 'detailed_label', 'label']
        usecols = [_ for _ in range(0, 9)] + [_ for _ in range(11, 14)] + [16, 17, 28, 29, 47, 48]
        na_values = ['-']
        skiprows = []
        dateparse = lambda x: pd.to_datetime(x, unit='s')
        parse_field = ['start_time', 'end_time']
    # Netflow data from CICIDS2017 dataset
    elif flag == 'CICIDS':
        names = ['src_ip', 'src_port', 'dst_ip', 'dst_port', 'protocol', 'date', 'duration', 'total_fwd_packets',
                 'total_bwd_packets', 'total_len_fwd_packets', 'total_len_pwd_packets', 'label']
        usecols = [_ for _ in range(1, 12)] + [84]
        dateparse = lambda x: pd.to_datetime(x, dayfirst=True)
    # Netflow data from CIDDS dataset
    else:
        names = ['date', 'duration', 'protocol', 'src_ip', 'src_port', 'dst_ip', 'dst_port', 'packets', 'bytes',
                 'flags', 'label', 'attack_type', 'attack_id', 'attack_desc']
        usecols = [_ for _ in range(0, 9)] + [10] + [_ for _ in range(12, 16)]
        na_values = ['---']
        dateparse = lambda x: pd.to_datetime(x)

    # a simple try-except loop to catch any tokenizing errors in the data (e.g. the FILTER_LEGITIMATE field in the
    # unidirectional flows - for now these lines are ignored) in case the explanatory flag is True
    cont = True
    data = []
    while cont:
        try:
            # read the data into a dataframe according to the background flag
            data = pd.read_csv(filepath, delimiter=delimiter, header=header, names=names, parse_dates=parse_field,
                               date_parser=dateparse, usecols=usecols, na_values=na_values, error_bad_lines=expl,
                               engine=engine, skiprows=skiprows, skipfooter=skipfooter) if background else \
                pd.concat(remove_background(chunk) for chunk in pd.read_csv(filepath, chunksize=100000,
                                                                            delimiter=delimiter,
                                                                            parse_dates=parse_field,
                                                                            date_parser=dateparse,
                                                                            error_bad_lines=expl,
                                                                            engine=engine,
                                                                            skiprows=skiprows,
                                                                            skipfooter=skipfooter))
            cont = False
        except Exception as e:
            errortype = str(e).split('.')[0].strip()
            if errortype == 'Error tokenizing data':
                cerror = str(e).split(':')[1].strip().replace(',', '')
                nums = [n for n in cerror.split(' ') if str.isdigit(n)]
                skiprows.append(int(nums[1]) - 1)
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                err_line = lines[int(nums[1]) - 1]
                print(err_line)
            else:
                print(errortype)

    # Separate handling of the background data (for the CTU-13 datasets mostly)
    if not background:
        data.to_pickle(filepath + '_no_background.pkl')
    return data


def remove_background(df):
    """
    Helper function removing background flows from a given dataframe
    :param df: the dataframe
    :return: the no-background dataframe
    """
    df = df[df['label'] != 'Background']
    return df


if __name__ == '__main__':
    # filepath = input("Enter the desired filepath: ")
    filepath = 'Datasets/IOT23/Malware-Capture-8-1/conn.log.labeled.txt'

    # Choose between the flags CTU-uni | CTU-bi | CTU-mixed | CICIDS | CIDDS | UNSW | IOT
    flag = 'IOT'
    # while True:
    #     flag = input("Enter the desired flag (CTU-uni | CTU-bi | CTU-mixed | CICIDS | CIDDS | UNSW | IOT): ")
    #     if flag in ['CTU-uni', 'CTU-bi', 'CTU-mixed', 'CICIDS', 'CIDDS', 'UNSW', 'IOT']:
    #         break

    # only for the CTU-mixed case
    given_dates = ['2015/07/26 14:41:51.734831', '2015/07/27 15:51:12.978465']

    # to get preprocessing, necessary for unidirectional netflows, done, set the 'preprocessing' flag to True
    if flag == 'CTU-uni':
        data = read_data(filepath, flag=flag, preprocessing='uni' if bool(input("Enable preprocessing (for NO give no "
                                                                                "answer)? ")) else None)
    else:
        data = read_data(filepath, flag=flag)

    print('Dataset from ' + filepath + ' has been successfully read!!!')

    # resetting indices for data
    data = data.reset_index(drop=True)

    # some more preprocessing on the specific fields of the dataframe
    if flag == 'CTU-uni':
        # parse packets, and bytes as integers instead of strings
        data['packets'] = data['packets'].astype(int)
        data['bytes'] = data['bytes'].astype(int)

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # add the numerical representation of the categorical data
        data['protocol_num'] = pd.Categorical(data['protocol'], categories=data['protocol'].unique()).codes
        data['flags_num'] = pd.Categorical(data['flags'], categories=data['flags'].unique()).codes

        # drop NaN rows (mostly NaN ports)
        data.dropna(inplace=True)

        # since NaN values have been removed from ports
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)

        # split the data according to their labels
        anomalous = data[data['label'] == 'Botnet']
        anomalous = anomalous.reset_index(drop=True)

        normal = data[data['label'] == 'LEGITIMATE']
        normal = normal.reset_index(drop=True)

        background = data[data['label'] == 'Background']
        background = background.reset_index(drop=True)

        # save the separated data
        anomalous.to_pickle('/'.join(filepath.split('/')[0:3]) + '/netflow_anomalous.pkl')
        normal.to_pickle('/'.join(filepath.split('/')[0:3]) + '/netflow_normal.pkl')
        background.to_pickle('/'.join(filepath.split('/')[0:3]) + '/netflow_background.pkl')
    elif flag in ['CTU-bi', 'CTU-mixed']:
        # parse packets, and bytes as integers instead of strings
        data['packets'] = data['packets'].astype(int)
        data['bytes'] = data['bytes'].astype(int)
        data['src_bytes'] = data['src_bytes'].astype(int)

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # add the numerical representation of the categorical data
        data['protocol_num'] = pd.Categorical(data['protocol'], categories=data['protocol'].unique()).codes
        data['state_num'] = pd.Categorical(data['state'], categories=data['state'].unique()).codes

        # drop NaN rows (mostly NaN ports)
        data.dropna(inplace=True)

        # since NaN values have been removed from ports
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)

        # in case of the mixed CTU flows drop also the deep packet data
        if flag == 'CTU-mixed':
            data.drop(columns=['label'], inplace=True)
            mask = (data['date'] >= given_dates[0]) & (data['date'] <= given_dates[1]) \
                if len(given_dates) == 2 else data['date'] >= given_dates[0]
            # the rows that agree with the mask are anomalous
            anomalous = data.loc[mask]
            anomalous = anomalous.reset_index(drop=True)

            normal = data.loc[~mask]
            normal = normal.reset_index(drop=True)

            # save the separated data
            anomalous.to_pickle('/'.join(filepath.split('/')[0:3]) + '/binetflow_anomalous.pkl')
            normal.to_pickle('/'.join(filepath.split('/')[0:3]) + '/binetflow_normal.pkl')
        else:
            # split the data according to their labels
            anomalous = data[data['label'].str.contains("Botnet")]
            anomalous = anomalous.reset_index(drop=True)

            normal = data[data['label'].str.contains("Normal")]
            normal = normal.reset_index(drop=True)

            background = data[data['label'].str.contains("Background")]
            background = background.reset_index(drop=True)

            # save the separated data
            anomalous.to_pickle('/'.join(filepath.split('/')[0:3]) + '/binetflow_anomalous.pkl')
            normal.to_pickle('/'.join(filepath.split('/')[0:3]) + '/binetflow_normal.pkl')
            background.to_pickle('/'.join(filepath.split('/')[0:3]) + '/binetflow_background.pkl')
    elif flag == 'IOT':
        # TODO: check how to handle NaN values
        # parse packets, bytes, and ports as integers instead of strings
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)
        data['orig_bytes'] = data['orig_bytes'].astype(int)
        data['resp_bytes'] = data['resp_bytes'].astype(int)
        data['missed_bytes'] = data['missed_bytes'].astype(int)
        data['orig_packets'] = data['orig_packets'].astype(int)
        data['orig_ip_bytes'] = data['orig_ip_bytes'].astype(int)
        data['resp_packets'] = data['resp_packets'].astype(int)
        data['resp_ip_bytes'] = data['resp_ip_bytes'].astype(int)

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # add the numerical representation of the categorical data
        data['protocol_num'] = pd.Categorical(data['protocol'], categories=data['protocol'].unique()).codes
        data['service_num'] = pd.Categorical(data['service'], categories=data['service'].unique()).codes
        data['state_num'] = pd.Categorical(data['state'], categories=data['state'].unique()).codes

        # split the data according to their labels
        anomalous = data[data['label'] == 'Malicious']
        anomalous = anomalous.reset_index(drop=True)

        normal = data[data['label'] == 'Benign']
        normal = normal.reset_index(drop=True)

        # save the separated data
        anomalous.to_pickle('/'.join(filepath.split('/')[0:3]) + '/zeek_anomalous.pkl')
        normal.to_pickle('/'.join(filepath.split('/')[0:3]) + '/zeek_normal.pkl')
    elif flag == 'UNSW':
        # TODO: check how to handle NaN values
        # parse packets, bytes, and ports as integers instead of strings
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)
        data['src_bytes'] = data['src_bytes'].astype(int)
        data['dst_bytes'] = data['dst_bytes'].astype(int)
        data['missed_src_bytes'] = data['missed_src_bytes'].astype(int)
        data['missed_dst_bytes'] = data['missed_dst_bytes'].astype(int)
        data['src_packets'] = data['src_packets'].astype(int)
        data['dst_packets'] = data['dst_packets'].astype(int)

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # add the numerical representation of the categorical data
        data['protocol_num'] = pd.Categorical(data['protocol'], categories=data['protocol'].unique()).codes
        data['service_num'] = pd.Categorical(data['service'], categories=data['service'].unique()).codes
        data['state_num'] = pd.Categorical(data['state'], categories=data['state'].unique()).codes

        # split the data according to their labels
        anomalous = data[data['label'] == '1']
        anomalous = anomalous.reset_index(drop=True)

        normal = data[data['label'] == '0']
        normal = normal.reset_index(drop=True)

        # save the separated data
        anomalous.to_pickle('/'.join(filepath.split('/')[0:2]) + '/' + filepath.split('.')[-1] + '_anomalous.pkl')
        normal.to_pickle('/'.join(filepath.split('/')[0:2]) + '/' + filepath.split('.')[-1] + '_normal.pkl')
    elif flag == 'CICIDS':
        # TODO: check how to handle NaN values
        # parse packets, bytes, and ports as integers instead of strings
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)
        data['total_fwd_packets'] = data['total_fwd_packets'].astype(int)
        data['total_bwd_packets'] = data['total_bwd_packets'].astype(int)
        data['total_len_fwd_packets'] = data['total_len_fwd_packets'].astype(int)
        data['total_len_bwd_packets'] = data['total_len_bwd_packets'].astype(int)
        data['protocol_num'] = data['protocol'].astype(int)

        # convert the numerical protocol values to strings according to their code
        table = {num: name[8:] for name, num in vars(socket).items() if name.startswith("IPPROTO")}
        data['protocol'] = data['protocol'].apply(lambda x: table[x])

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # split the data according to their labels
        anomalous = data[data['label'] != 'BENIGN']
        anomalous = anomalous.reset_index(drop=True)

        normal = data[data['label'] == 'BENIGN']
        normal = normal.reset_index(drop=True)

        # save the separated data
        anomalous.to_pickle('/'.join(filepath.split('/')[0:2]) + '/' + filepath.split('/')[2].split('.')[0] +
                            '_anomalous.pkl')
        normal.to_pickle('/'.join(filepath.split('/')[0:2]) + '/' + filepath.split('/')[2].split('.')[0] +
                         '_normal.pkl')
    else:
        # TODO: check how to handle NaN values
        # parse packets, bytes, and ports as integers instead of strings
        data['src_port'] = data['src_port'].astype(int)
        data['dst_port'] = data['dst_port'].astype(int)
        data['packets'] = data['packets'].astype(int)
        data['bytes'] = data['bytes'].astype(int)

        # parse duration as float
        data['duration'] = data['duration'].astype(float)

        # add the numerical representation of the categorical data
        data['protocol_num'] = pd.Categorical(data['protocol'], categories=data['protocol'].unique()).codes
        data['flags_num'] = pd.Categorical(data['flags'], categories=data['flags'].unique()).codes

        # split the data according to their labels
        anomalous = data[data['label'] != 'normal']    # To remember: In this dataset there are multiple abnormal labels
        anomalous = anomalous.reset_index(drop=True)

        normal = data[data['label'] == 'normal']
        normal = normal.reset_index(drop=True)

        # save the separated data
        anomalous.to_pickle('/'.join(filepath.split('/')[0:5]) + '/' + filepath.split('/')[5].split('.')[0] +
                            '_anomalous.pkl')
        normal.to_pickle('/'.join(filepath.split('/')[0:5]) + '/' + filepath.split('/')[5].split('.')[0] +
                         '_normal.pkl')
