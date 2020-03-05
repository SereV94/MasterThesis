import pandas as pd
from pandas.tseries.offsets import DateOffset
from datetime import timedelta
from copy import deepcopy
from scipy.stats import mode
from statistics import mean, stdev
from model import ModelNode, Model
from tslearn.metrics import dtw
from sklearn.preprocessing import MinMaxScaler
import re


def set_windowing_vars(in_filepath, approx_length):
    """
    Function for automatically calculating the time windows and strides to be used for creating the traces at each time
    step, given a preference on the number of records to be contained in each trace.
    :param in_filepath: the relative path of the input dataframe
    :param approx_length: the approximate number of records desired to be put in every trace
    :return: a tuple with the calculated time windows and strides in a dataframe format
    """
    data = pd.read_pickle(in_filepath)
    # find the medians of the time differences in the dataframe for rolling windows of approx_length length
    median_diffs = data['date'].sort_values().diff().dt.total_seconds().rolling(approx_length).median()
    median_diffs = median_diffs.fillna(method='bfill').apply(lambda x: timedelta(seconds=x))
    return 100 * median_diffs, 20 * median_diffs


def traces_dissimilarity(trace1, trace2, multivariate=True, normalization=True):
    """
    Function for calculating the dissimilarity between two input traces. The traces are in the form of list of lists and
    are dealt either as multivariate series or as multiple univariate series depending on the value of the multivariate
    flag provided
    :param trace1: the first trace
    :param trace2: the second trace
    :param multivariate: the multivariate flag
    :param normalization: the normalization flag for performing (or not) min-max normalization
    :return: the dissimilarity score (the lower the score the higher the similarity)
    """
    if normalization:
        traces = MinMaxScaler().fit_transform(trace1 + trace2)
        trace1 = traces[:len(trace1)].tolist()
        trace2 = traces[len(trace1):].tolist()
    return dtw(trace1, trace2) if multivariate else mean([dtw(list(list(zip(*trace1))[j]), list(list(zip(*trace2))[j]))
                                                          for j in range(len(trace1[0]))])


def convert2flexfringe_format(win_data):
    """
    Function to convert the windowed data into a trace in the format accepted by the multivariate version of flexfringe
    :param win_data: the windowed dataframe
    :return: a list of the events in the trace with features separated by comma in each event
    """
    return list(map(lambda x: ','.join(map(lambda t: str(int(t)), x)), win_data.to_numpy().tolist()))


def trace2list(trace):
    """
    Function for converting a list of string records of a trace to a list of lists
    :param trace: the list with the string records
    :return: the converted list of lists
    """
    return list(map(lambda x: list(map(int, x.split(','))), trace))


def aggregate_in_windows(data, window, timed=False, resample=False):
    """
    Function for aggregating specific features of a dataframe in rolling windows of length window
    Currently the following features are taken into account: source port, destination ip/port, originator's bytes,
    responder's bytes, duration, and protocol
    :param data: the input dataframe
    :param window: the window length
    :param timed: boolean flag specifying if aggregation window should take into account the timestamps
    :param resample: boolean flag specifying if aggregation window should be rolling or resampling
    :return: a dataframe with the aggregated features
    """
    old_column_names = deepcopy(data.columns.values)
    # if the timed flag is True then timestamps are used as indices
    if timed:
        data.set_index('date', inplace=True)
    if not resample:
        if 'orig_ip_bytes' in old_column_names:
            data['median_orig_bytes'] = data['orig_ip_bytes'].rolling(window).median()
            data['var_orig_bytes'] = data['orig_ip_bytes'].rolling(window).var()
        if 'resp_ip_bytes' in old_column_names:
            data['median_resp_bytes'] = data['resp_ip_bytes'].rolling(window).median()
            data['var_resp_bytes'] = data['resp_ip_bytes'].rolling(window).var()
        if 'duration' in old_column_names:
            data['median_duration'] = data['duration'].rolling(window).median()
            data['var_duration'] = data['duration'].rolling(window).var()
        if 'dst_ip' in old_column_names:
            data['unique_dst_ips'] = data['dst_ip'].rolling(window).apply(lambda x: len(set(x)))
        if 'src_port' in old_column_names:
            data['unique_src_ports'] = data['src_port'].rolling(window).apply(lambda x: len(set(x)))
            data['var_src_ports'] = data['src_port'].rolling(window).var()
        if 'dst_port' in old_column_names:
            data['unique_dst_ports'] = data['dst_port'].rolling(window).apply(lambda x: len(set(x)))
            data['var_dst_ports'] = data['dst_port'].rolling(window).var()
        if 'protocol_num' in old_column_names:
            data['argmax_protocol_num'] = data['protocol_num'].rolling(window).apply(lambda x: mode(x)[0])
            data['var_protocol_num'] = data['protocol_num'].rolling(window).var()
    else:
        # can be called only if timed flag has been set to True
        # TODO: check if all aggregation functions are compatible with resample
        if 'orig_ip_bytes' in old_column_names:
            data['median_orig_bytes'] = data['orig_ip_bytes'].resample(window).median()
            data['var_orig_bytes'] = data['orig_ip_bytes'].resample(window).var()
        if 'resp_ip_bytes' in old_column_names:
            data['median_resp_bytes'] = data['resp_ip_bytes'].resample(window).median()
            data['var_resp_bytes'] = data['resp_ip_bytes'].resample(window).var()
        if 'duration' in old_column_names:
            data['median_duration'] = data['duration'].resample(window).median()
            data['var_duration'] = data['duration'].resample(window).var()
        if 'dst_ip' in old_column_names:
            data['unique_dst_ips'] = data['dst_ip'].resample(window).apply(lambda x: len(set(x)))
        if 'src_port' in old_column_names:
            data['unique_src_ports'] = data['src_port'].resample(window).apply(lambda x: len(set(x)))
            data['var_src_ports'] = data['src_port'].resample(window).var()
        if 'dst_port' in old_column_names:
            data['unique_dst_ports'] = data['dst_port'].resample(window).apply(lambda x: len(set(x)))
            data['var_dst_ports'] = data['dst_port'].resample(window).var()
        if 'protocol_num' in old_column_names:
            data['argmax_protocol_num'] = data['protocol_num'].resample(window).apply(lambda x: mode(x)[0])
            data['var_protocol_num'] = data['protocol_num'].resample(window).var()
    data.drop(columns=old_column_names, inplace=True)
    return data


def extract_traces(in_filepath, out_filepath, selected, window, stride, dynamic=True, aggregation=0):
    """
    Function for extracting traces from the dataframe stored in the in_filepath and saving them in out_filepath. The
    features to be taken into account are provided in the selected list. Each trace is extracted by rolling a window of
    window seconds in the input data with a stride of stride seconds. If aggregation flag is set to 1, then aggregation
    windows are created in each rolling window
    :param in_filepath: the relative path of the input dataframe
    :param out_filepath: the relative path of the output traces' file
    :param selected: the features to be used
    :param window: the window size
    :param stride: the stride size
    :param dynamic: boolean flag about the use of dynamically changing windows
    :param aggregation: the aggregation flag - if set to 1, then aggregation windows are created
    :return: creates and stores the traces' file extracted from the input dataframe
    """
    data = pd.read_pickle(in_filepath)

    # create an anonymous function for increasing timestamps given the type of the window (int or Timedelta)
    time_inc = lambda x, w: x + DateOffset(seconds=w) if type(window) == int else x + w

    # set the initial start and end dates, as well as the empty traces' list and the window limits
    # use a counter for the new window structure
    window_cnt = 0
    start_date = data['date'].iloc[0]
    if dynamic:
        end_date = time_inc(start_date, window.median())
    else:
        end_date = time_inc(start_date, window[window_cnt])  # change
    traces = []  # list of lists
    min_window, max_window = (window.min(), window.max())
    # special counters used for counting the consecutive times a window with 0 records has been retrieved
    prev_zero_cnt = 0
    zero_cnt = 0
    # structures just for progress visualization purposes
    cnt = 0
    tot = len(data.index)
    progress_list = []

    # iterate through the input dataframe until the end date is greater than the last date recorded
    while end_date < data['date'].iloc[-1]:
        # retrieve the window of interest
        time_mask = (data['date'] >= start_date) & (data['date'] <= end_date)
        windowed_data = data[time_mask]
        if len(windowed_data.index.tolist()) != 0:
            # create aggregated features if needed (currently with a hard-coded window length)
            if aggregation:
                windowed_data = aggregate_in_windows(windowed_data[selected].copy(deep=True),
                                                     min(10, int(len(windowed_data.index))))
                selected = windowed_data.columns.values
            # extract the trace of this window and add it to the traces' list
            traces += [convert2flexfringe_format(windowed_data[selected])]
            if dynamic:
                # reset the counters of consecutive empty windows
                prev_zero_cnt = 0
                zero_cnt = 0
                # dynamic check of the windowing procedure
                if len(traces) > 1:
                    # TODO: set the limits for the dynamic windows to more robust values
                    # first check if there are any huge or tiny traces to adjust the window size
                    traces_lengths = list(map(len, traces))
                    if len(traces[-1]) - mean(traces_lengths) > 3 * stdev(traces_lengths):
                        print('--------------- Reducing the size of the window... ---------------')
                        window = max(window / 2, min_window)
                        # we don't let the size of the window become less than the stride since in that case data points
                        # can be missed
                        if window <= stride:
                            stride /= 2
                    elif len(traces[-1]) - mean(traces_lengths) < -3 * stdev(traces_lengths):
                        print('--------------- Increasing the size of the window... ---------------')
                        window = min(window * 2, max_window)
                    else:
                        # then check the novelty of the content of the window
                        dissim = traces_dissimilarity(deepcopy(trace2list(traces[-1])), deepcopy(trace2list(traces[-2])))
                        if dissim < 0.05:
                            print('--------------- Increasing the stride of the window... ---------------')
                            stride *= 2
                            # we don't let the size of the window become less than the stride since in that case data
                            # points can be missed
                            if stride >= window:
                                window = min(window * 2, max_window)
                                if window == max_window:
                                    stride = deepcopy(max_window / 2)
                        elif dissim > 2.5:
                            print('--------------- Reducing the stride of the window... ---------------')
                            stride /= 2
                        else:
                            print('--------------- The size and stride of the window remain the same ---------------')
            # update the progress variable
            cnt = windowed_data.index.tolist()[-1]
        else:
            if dynamic:
                zero_cnt += 1
                print('--------------- Window with NO data identified!!! ---------------')
                if zero_cnt - prev_zero_cnt == 20:
                    window = min(window * 2, max_window)
                    prev_zero_cnt = deepcopy(zero_cnt)
                if zero_cnt - prev_zero_cnt == 10:
                    stride *= 2
                    if stride >= window:
                        window *= 2
                        if window == max_window:
                            stride = deepcopy(max_window / 2)
            else:
                pass

        # increment the window limits according to the way the window is calculated (dynamic | static)
        if dynamic:
            start_date = time_inc(start_date, stride)
            end_date = time_inc(start_date, window)
        else:
            start_date = time_inc(start_date, stride[window_cnt])
            window_cnt = data.index[data['date'] >= start_date].tolist()[0]
            end_date = time_inc(start_date, window[window_cnt])

        # show progress
        prog = int((cnt / tot) * 100)
        if prog // 10 != 0 and prog % 10 == 0 and prog not in progress_list:
            progress_list += [prog]
            print('\n' + str(prog) + '% of the data processed...' + '\n')
        # print(str(cnt) + '  rows processed...')

    print('Finished with rolling windows!!!')
    print('Starting writing traces to file...')
    # create the traces' file in the needed format
    if aggregation:
        out_filepath = out_filepath.split('.')[0] + '_aggregated.' + out_filepath.split('.')[1]
    f = open(out_filepath, "w")
    f.write(str(len(traces)) + ' ' + '100:' + str(len(selected)) + '\n')
    for trace in traces:
        f.write('1 ' + str(len(trace)) + ' 0:' + ' 0:'.join(trace) + '\n')
    f.close()
    print('Traces written successfully to file!!!')


def parse_dot(dot_path):
    """
    Function for parsing dot files describing multivariate models produced through FlexFringe
    :param dot_path: the path to the dot file
    :return: the parsed model
    """
    with open(dot_path, "r") as f:
        dot_string = f.read()
    # initialize the model
    model = Model()
    # regular expression for parsing a state as well as its contained info
    state_regex = r"(?P<src_state>\d+) \[\s*label=\"(?P<state_info>(.+))\".*\];$"
    # regular expression for parsing a state's contained info
    info_regex = r"((?P<identifier>(fin|symb|attr)+\(\d+\)):\[*(?P<values>(\d|,)+)\]*)+"
    # regular expression for parsing the transitions of a state, as well as the firing conditions
    transition_regex = r"(?P<src_state>.+) -> (?P<dst_state>\d+)( \[label=\"(?P<transition_cond>(.+))\".*\])*;$"
    # regular expression for parsing the conditions firing a transition
    cond_regex = r"((?P<sym>\d+) (?P<ineq_symbol>(<|>|<=|>=|==)) (?P<boundary>\d+))+"
    # boolean flag used for adding states in the model
    cached = False
    for line in re.split(r'\n\t+', dot_string):  # split the dot file in meaningful lines
        state_matcher = re.match(state_regex, line, re.DOTALL)
        # if a new state is found while parsing
        if state_matcher is not None:
            # check if there is a state pending and, if there is, update the model
            if cached:
                model.add_node(ModelNode(src_state, attributes, fin, tot, dst_nodes, cond_dict))
            src_state = state_matcher.group("src_state")  # find the state number
            # and initialize all its parameters
            attributes = {}
            fin = 0
            tot = 0
            dst_nodes = []
            cond_dict = {}
            # find the state information while parsing
            state_info = state_matcher.group("state_info")
            if state_info != 'root':
                # if the state is not the root one retrieve the state's information
                for info_matcher in re.finditer(info_regex, state_info):
                    identifier = info_matcher.group("identifier")
                    id_values = info_matcher.group("values")
                    if 'fin' in identifier:  # the number of times the state was final
                        fin = int(id_values)
                    elif 'symb' in identifier:  # the number of times the state was visited
                        tot = fin + int(id_values[:-1])
                    else:
                        # the quantiles of each attribute
                        attributes[re.findall(r'\d+', identifier)[0]] = list(map(float, id_values.split(',')[:-1]))
            else:
                # otherwise set the state's name to root (because for some reason 3 labels are used for the root node)
                src_state = 'root'

        transition_matcher = re.match(transition_regex, line, re.DOTALL)
        # if a transition is identified while parsing (should be in the premises of the previously identified state)
        if transition_matcher is not None:
            src_state_1 = transition_matcher.group("src_state")  # the source state number
            if src_state_1 == 'I':  # again the same problem as above
                src_state_1 = 'root'
            # just consistency check that we are still parsing the same state as before
            if src_state != src_state_1:
                print('Something went wrong - Different source states in a state!!!')
                return -1
            # identify the destination state and add it to the list of destinations
            dst_state = transition_matcher.group("dst_state")
            dst_nodes += [dst_state]  # should exist given that transitions come after the identification of a new state
            # check for the transitions' conditions only if the current state is not the root
            if src_state_1 != 'root':
                # find the transition's conditions while parsing
                transition_conditions = transition_matcher.group("transition_cond")
                for condition_matcher in re.finditer(cond_regex, transition_conditions):
                    attribute = condition_matcher.group("sym")  # the attribute contained in the condition
                    inequality_symbol = condition_matcher.group("ineq_symbol")  # the inequality symbol
                    boundary = condition_matcher.group("boundary")  # the numeric limit in the condition
                    # and update the conditions' dictionary
                    # the condition dictonary should be initialized from the state identification stage
                    if dst_state not in cond_dict.keys():
                        cond_dict[dst_state] = []
                    cond_dict[dst_state] += [attribute, inequality_symbol, float(boundary)]
            # set the cached flag to True after the first state is fully identified
            cached = True

    # one more node addition for the last state in the file to be added
    model.add_node(ModelNode(src_state, attributes, fin, tot, dst_nodes, cond_dict))
    return model


def traces2list(traces_path):
    """
    Function for converting the trace file into a list of traces ready for further processing
    :param traces_path: the filepath of the traces
    :return: the list of the traces as a list of lists (each trace) of lists (each record in each trace)
    """
    traces = []
    with open(traces_path, "r") as fp:
        # skip first line
        line = fp.readline()
        while line:
            line = fp.readline()
            # split lines by spaces
            tokens = line.split()
            # gather the records of each trace and keep only the record values and map them to float
            traces += [[list(map(float, t.split(':')[1].split(','))) for t in tokens[2:]]]
    return traces


def run_traces_on_model(traces_path, model):
    """
    Function for running a trace file on the provided model and storing the observed attributes' values on it
    :param traces_path: the filepath to the traces' file
    :param model: the given model
    :return: the updated model
    """
    traces = traces2list(traces_path)
    for trace in traces:
        # first fire the transition from root node
        label = model.fire_transition('root', dict())  # TODO: check if the empty dict will work
        for record in trace:
            observed = dict(zip([str(i) for i in range(len(record))], record))
            model.update_attributes(label, observed)
            label = model.fire_transition(label, observed)
    return model


if __name__ == '__main__':
    traces_filepath = 'Datasets/IOT23/training/training_traces.txt'
    traces = traces2list(traces_filepath)
    print('Done')
