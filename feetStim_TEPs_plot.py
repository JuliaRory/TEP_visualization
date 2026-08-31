    
import resonance
from resonance import input, playback
from resonance.pipe_tep import (
    transform_channels,
    interpolate_by_trigger,
    bit_signal_to_event,
    sosfilt,
    windowize_by_events, 
    transform_window_to_channels, 
    transform_to_event,
    combine_sequential_events,
    combine_channels,
    transform_to_channels
)
import resonance.si as si
#from resonance.cross import windowize_by_events, combine_sequential_events
import numpy as np
from scipy.signal import butter, iirnotch, tf2sos, decimate, resample_poly
import json
from scipy.ndimage import uniform_filter1d
from math import gcd

"""
Parameters:
    "window_start": -300,  [ms] -- начало эпохи
    "window_end": 500,     [ms] -- конец эпохи
    "artifact": true,           -- удалять артефакт?
    "artifact_start": -5,  [ms] -- начало артефакта
    "artifact_end": 15,    [ms] -- конец артефакта
    "lowpass": true,            -- использовать фильтр низких частот?
    "high_freq": 2500,     [Hz] -- частота среза
    "highpass": false,          -- использовать фильтр верхних частот?
    "low_freq": 1,         [Hz] -- частота среза
    "median": false,            -- использовать медианный фильтр?
    "kernel_size": 21,          -- размер ядра медианного фильтра
    "notch": false,             -- использовать Notch-фильтр?
    "notch_fr": 50,        [Hz] -- частота notch-фильтра
    "resampling": true,         -- делать даунсемплинг? 
    "Fs_orig": 25000,      [Hz] -- первоначальная частота записи
    "Fs": 1000             [Hz] -- частота на выходе 
"""

def load_parameters_from_json(filename):
    #функция подгрузки параметров
    with open(filename, 'r') as f:
        settings = json.load(f)
    return settings
   
   
def resample_signal(inp, fs_orig, fs_new, axis=0):
    if fs_orig <= 0 or fs_new <= 0:
        raise ValueError("Sampling rates must be positive")

    if fs_orig == fs_new:
        return inp

    # сокращаем отношение частот
    divisor = gcd(int(fs_orig), int(fs_new))

    up = int(fs_new // divisor)
    down = int(fs_orig // divisor)

    out = resample_poly(
        inp,
        up=up,
        down=down,
        axis=axis
    )
    expected_length = round(
        inp.shape[axis] * fs_new / fs_orig
    )

    if out.shape[axis] != expected_length:
        raise RuntimeError(
            f"Unexpected resampled length: "
            f"{out.shape[axis]}, expected {expected_length}"
        )

    return out
    
def pipeline_tep_feetStim(filename):
    
    #bit = [0] # TMS
    #bit = [1] # TMS 2
    #bit = [2] # photo
    """пайплайн обработки сигнала"""
    params = load_parameters_from_json(filename)    # вгрузить параметры 
    
    raw_signal = input(0)   # входной сигнал с nvx [n_samples, n_channels]
    #resonance.createOutput(raw_signal, "raw_signal")
    
    bit = [params["bit"]]
    
    # удаление и линейная интерполяция участка с артефактом по триггеру
    Fs = params["Fs_orig"]

    art_start = int(params["artifact_start"] * Fs/1000)    # начало артефакта (перевод в сэмплы)
    art_end = int(params["artifact_end"] * Fs/1000)        # конец артефакта (перевод в сэмплы)

    interp_signal = interpolate_by_trigger(raw_signal, art_start, art_end, bit=bit)     # интерполяция сигнала по сигналу с триггера 
    resonance.createOutput(interp_signal, "interp_signal")  # --> [n_samples, n_channels]   n_channels == n_EEG_ch + n_EMG_ch + trigger_ch

    #обработка сигнала
    #N_eeg_ch = 64  # количество ЭЭГ-каналов
    n_ch = raw_signal.shape[1]
    #EMG_ch = [n_ch-3, n_ch-2]

    full_signal = transform_channels(interp_signal, n_ch-1, lambda x: x[:, :-1])     # сигнал без триггера
        
    if params["highpass"]:                                                       # если применять фильтр низких частот 
        sos_high = butter(2, params['low_freq']/Fs*2, btype='highpass', output='sos')
        high_filt = sosfilt(full_signal, np.ascontiguousarray(sos_high))
    else:
        high_filt = transform_channels(full_signal, n_ch-1, lambda x: x)              # если не фильтровать, вернуть тот же канал

    #resonance.createOutput(high_filt, "high_filt")  # --> [n_samples, n_channels]   n_channels == n_EEG_ch + n_EMG_ch + trigger_ch
    
    if params["notch"]:
        
        notch_filt = high_filt
        
        notch_freqs = np.arange(params["notch_fr"], params["high_freq"] + 1, params["notch_fr"]) if params["notch_harmonics"] else [params["notch_fr"]]
        
        for freq in notch_freqs:
            notch_width = 1
            Q = freq / notch_width

            b_notch, a_notch = iirnotch(freq, Q, fs=Fs)

            sos_notch = tf2sos(b_notch, a_notch)

            notch_filt = sosfilt(
                notch_filt,
                np.ascontiguousarray(sos_notch)
            )

    else:
        notch_filt = transform_channels(high_filt, n_ch-1, lambda x: x)
    
    #resonance.createOutput(notch_filt, "notch_filt")  # --> [n_samples, n_channels]   n_channels == n_EEG_ch + n_EMG_ch + trigger_ch

    if params["lowpass"]:                                                             # если применять фильтр низких частот 
        sos_low = butter(2, params['high_freq']/Fs*2, btype='lowpass', output='sos')
        signal_filt = sosfilt(notch_filt, np.ascontiguousarray(sos_low))
    else:
        signal_filt = transform_channels(notch_filt, n_ch-1, lambda x: x)              # если не фильтровать, вернуть тот же канал
    
    #resonance.createOutput(signal_filt, "signal_filt")

    # вырезание эпохи по триггеру
    # определение триггера
    trigger_ch = raw_signal.shape[1] - 1    # trigger - последний канал
    trigger = transform_channels(raw_signal, 1, lambda x: x[:, trigger_ch].astype(int))
        
    
    events = bit_signal_to_event(trigger, bit[0], rising_edge=True, falling_edge=None)   # True если ивент был, False - если нет
    #resonance.createOutput(events, "events")

    start = params["window_start"]
    end =  params["window_end"]
    shift = int(start * Fs/1000)            # сдвиг начала относительно тригера 
    length = int((end-start) * Fs/1000)     # длина окна TEP
    
    wnd = windowize_by_events(signal_filt, events, window_size=length, shift=shift)

    #даунсемплинг и вывод результата
    decim = Fs // params["Fs"]
    def downsample(inp, factor):
        return inp[::factor] # [n_samples//factor, n_channels]
    
    if params["resampling"]:
        #epochs = transform_window_to_channels(wnd, n_ch-1, lambda x: downsample(x, decim))
        epochs = transform_window_to_channels(wnd, n_ch-1, lambda x: resample_signal(x, fs_orig=Fs, fs_new=params["Fs"], axis=0))
    else:
        epochs = transform_window_to_channels(wnd, n_ch-1, lambda x: x)
    
    resonance.createOutput(epochs, "epochs")

    ###########################################################################################################
    # MEPs = transform_window_to_channels(wnd_EMG, 1, lambda x: downsample(x, factor=factor))
    # resonance.createOutput(MEPs, "MEPs")

    # # output = combine_channels(TEPs, MEPs, 65, lambda x: downsample(x, factor=factor))
    # # resonance.createOutput(output, "epochs")

    # TEPs_event = transform_to_event(wnd_EEG, lambda x: {"TEPs": downsample(x, factor=factor)})
    # MEPs_event = transform_to_event(wnd_EMG, lambda x: {"MEPs": downsample(x, factor=factor)})

    # event = combine_sequential_events(TEPs_event, MEPs_event)

    # def combine_data(inp):
    #     arr = np.concatenate([inp[0]["TEPs"], inp[1]["MEPs"]], axis=1).round(2)
    #     return json.dumps({'data': arr.tolist()})

    # output_json = transform_to_event(event,combine_data)
    # resonance.createOutput(output_json, "epochs_event")

    # TEPs_json = transform_to_event(wnd_EEG, lambda x: json.dumps({"TEPs": downsample(x, factor=factor).round().tolist()}))
    # resonance.createOutput(TEPs_json, "TEPs_event")

    # MEPs_json = transform_to_event(wnd_EMG, lambda x: json.dumps({"MEPs": downsample(x, factor=factor).round(3).tolist()}))
    # resonance.createOutput(MEPs_json, "MEPs_event")
     
     
      # 15:34:10 !> index 3840 is out of bounds for axis 0 with size 3840 during blockReceived
    """
    
    channels = ['T7', 'TP9', 'P7', 'CP5', 'FT9', 'F7', 'FC5', 'F3', 'P3', 'C3', 'CP1', 'O1', 'Fp1', 'FC1', 'Fz', 'Fp2', 'Cz', 'FC2', 'CP2', 'Pz', 'O2', 'Oz', 'C4', 'P4', 'F4', 'FC6', 'F8', 'FT10', 'CP6', 'P8', 'T8', 'TP10', 'FT7', 'TP7', 'AF7', 'F5', 'C5', 'FC3', 'CP3', 'P5', 'PO3', 'PO7', 'C1', 'P1', 'AF3', 'F1', 'AF4', 'Fpz', 'FCz', 'F2', 'CPz', 'C2', 'POz', 'P2', 'PO8', 'PO4', 'P6', 'CP4', 'FC4', 'C6', 'F6', 'AF8', 'FT8', 'TP8']
    
    def resample(data, old_rate, new_rate):
        # data : np.ndarray  Исходный массив формы (n_samples, n_channels).
        n_samples, n_channels = data.shape
        duration = n_samples / old_rate  # общая длина в секундах
        new_samples = int(round(duration * new_rate))

        # временные оси
        t_old = np.linspace(0, duration, n_samples, endpoint=False)
        t_new = np.linspace(0, duration, new_samples, endpoint=False)

        # интерполяция по каждому каналу
        resampled = np.empty((n_channels, new_samples), dtype=float)
        for ch in range(n_channels):
            resampled[ch] = np.interp(t_new, t_old, data[:, ch])

        return resampled
    
    
    
    # def resample(data, fs_old, fs_new):
    #     # data : np.ndarray  Исходный массив формы (n_samples, n_channels).
    #     step = 5 #int(round(fs_old / fs_new))
    #     if step < 1:
    #         step = 1

    #     return data[::step, :]
    
    def create_json_res(inp, old_rate, new_rate, channels):
        inp = resample(np.array(inp).round(2), old_rate, new_rate)
        
        data = {}
        for i in range(inp.shape[1]): # for each channel
            data[channels[i]] = list(np.array(inp)[:, i].flatten())
        return json.dumps(data)
    
    #wnd_event = transform_to_event(wnd, lambda x: create_json_res(x, Fs, params["Fs"], channels))
    #resonance.createOutput(wnd_event, "TEP_raw")
    
    # медианный фильтр
    def median_subtract_filter(data, k=21):
        #data : np.ndarray  (n_channels, n_samples)
        if k % 2 == 0:
            raise ValueError("Размер окна k должен быть нечётным!")

        # применяем фильтр вдоль оси времени
        baseline = np.apply_along_axis(lambda x: signal.medfilt(x, kernel_size=k), axis=1, arr=data)
        return data - baseline

    #удаление артефакта + интерполяция
    
    def remove_and_interpolate(data, start, end, kernel_size=5):
        # data : np.ndarray Массив формы (n_samples, n_channels).
        
        data = data.copy()
        n_samples, n_ch = data.shape
        
        # индексы концов
        x = np.array([start-1, end+1])
        if x[0] < 0: x[0] = 0
        if x[1] >= n_samples: x[1] = n_samples-1
        
        for ch in range(n_ch):
            # значения на концах
            y = np.array([data[x[0], ch], data[x[1], ch]])
            
            # линейная интерполяция
            interp = np.interp(np.arange(start, end+1), x, y)
            data[start:end+1, ch] = interp
            
            # сглаживание окрестностей границ
            left = max(0, start - kernel_size)
            right = min(n_samples, end + kernel_size + 1)
            data[left:right, ch] = uniform_filter1d(data[left:right, ch], size=kernel_size)
        
        return data
    
    
    def create_json_inter(inp, start, end, old_rate, new_rate, channels):
        inp = np.array(inp).round(2)
        interp = remove_and_interpolate(inp, start, end)
        res = resample(interp, old_rate, new_rate)
        
        # data = {}
        # for i in range(res.shape[1]): # for each channel
        #     data[channels[i]] = list(res[:, i].flatten())
        
        data = {}
        for i in range(res.shape[0]): # for each channel
            data[channels[i]] = list(res[i].flatten())
        return json.dumps(data)
    
    
    art_start = int(params["artifact_start"] * Fs/1000) - shift
    art_end = int(params["artifact_end"] * Fs/1000) - shift
    wnd_interp_event = transform_to_event(wnd, lambda x: create_json_inter(x, art_start, art_end, Fs, params["Fs"], channels))
    resonance.createOutput(wnd_interp_event, "TEP_interp")
    
    
    #фильтрация 
    def filtering(inp, sos_high, sos_low):
        # ret = signal.sosfilt(sos_high, inp, axis=1)
        #ret = signal.sosfilt(sos_low, inp, axis=0)
        return inp
    
    def create_json_filt(inp, start, end, sos_high, sos_low, old_rate, new_rate, channels):
        inp = np.array(inp).round(2)
        interp = remove_and_interpolate(inp, start, end)
        filt = filtering(interp, np.ascontiguousarray(sos_high), np.ascontiguousarray(sos_low))
        res = resample(filt, old_rate, new_rate).round(2)

    
        # data = {}
        # for i in range(res.shape[1]): # for each channel
        #     data[channels[i]] = list(res[:, i].flatten())
         
        data = {}
        for i in range(res.shape[0]): # for each channel
            data[channels[i]] = list(res[i].flatten())
        return json.dumps(data)
    
   
    lowFreq = params["low_freq"]
    sos_high = signal.butter(2, lowFreq/Fs*2, btype='highpass', output='sos')
    highFreq = params["high_freq"]
    sos_low = signal.butter(2, highFreq/Fs*2, btype='lowpass', output='sos')
    
    wnd_filt_event = transform_to_event(wnd, lambda x: create_json_filt(x, art_start, art_end, sos_high, sos_low, Fs, params["Fs"], channels))
    resonance.createOutput(wnd_filt_event, "TEP_filtered")
    
    
    #создать json-чики с канал - окно

    #подсчёт амплитуды и латентности
    ## фильтрация сигнала  -- в файл filters.py
    filter_is_sos, filter_args = None, None
    filt_EMG = sosfilt(raw_EMG, np.ascontiguousarray(p.sos))
    filt_EMG = filter(raw_EMG, (p.b, p.a))

    trigger_ch = 66
    trigger = transform_channels(raw_signal, 1, lambda x: x[:, trigger_ch].astype(int))  # кажется триггер... 
    events = bit_signal_to_event(trigger, 0)  # 0 -- channel? # rising_edge=True, falling_edge=None  в rms front=False
    
    length, shift = 1000, 100  # ВВЕСТИ НУЖНОЕ !!!!!!!!!!!!!
    wnd3 = windowize_by_events(filt_EMG, events, window_size=length, shift=shift)
    wnd2 = windowize_by_events(filt_EMG, events, window_size=length-shift-10, shift=10)
    
    def calc_amplitude_and_latencу(EMG, channel):
        res = []
        for wnd in EMG:
            ch = wnd[:, channel]
            # Индексы глобального минимума/максимума 
            b = int(np.argmin(ch)) 
            e = int(np.argmax(ch))
            amp = float(ch[e] - ch[b])

            i = min(b, e) # Ранний из двух экстремумов
            over0 = np.diff(np.sign(ch))  # Изменения знака между соседними отсчётами

            # Эквивалент R: i0 <- tail(which(over0[1:i] != 0), 1)
            # находит все смены знака в первых i переходах (между парами 1–2, 2–3, …, i–(i+1)) и берёт последнюю из них.
            idx = np.nonzero(over0[:i] != 0)[0]   # позиции ненулевых элементов
            i0 = int(idx[-1] + 1) if idx.size > 0 else None  
            res.append({'amplitude': amp, 'latency': i0})
        return res
    
    ch_a, ch_b = 0, 1  # ВВЕСТИ НУЖНОЕ !!!!!!!!!!!!!
    M2 = calc_amplitude_and_latencу(wnd2, ch_a)
    M5 = calc_amplitude_and_latencу(wnd2, ch_b)

    combined = combine_events(wnd3, M2, M5) # класс, написанный с лёгкой руки чата по типу кода на R... 

    def empty_transform(inp):
        return inp
    
    json = transform_to_event(combined, empty_transform)
    resonance.createOutput(json, "json") 
    
    
    
#######################################################################################

    # симуляция прогона этого файла в онлайне
    # filename = r"R:\mulines2024\data\rec2-06.h5"
    # stream = signal_creator(raw_signal, filename)

    # stream = raw_signal

    # resonance.createOutput(stream, "orig_out") # only channels and events

    # 0. Load parameters
    p = load_parameters_from_mat(mat)
    
    # 1. Пространственный фильтр (вгружаемая матрица: проверить что совпадает с количеством ЭЭГ-каналов)

    spatial_transformation = (
        ((np.eye(67)[:, p.eeg_chans_inds.astype(int) - 1]) * (10**6)) @ p.spatialW
    )  # combination of spatial filer and EEG channels filter

    # rearranged = spatial(stream, spatial_transformation) # for online simulation 
    rearranged = spatial(raw_signal, spatial_transformation) # for offline and real online

    #resonance.createOutput(rearranged, "spatial_out") # only channels and events
    
    # # 2. Фильтрация (вгружаемые коэффициенты: [b a] или [sos]

    # filter_is_sos, filter_args = None, None
    # if p.sos is not None:
    #     filtered = sosfilt(rearranged, np.ascontiguousarray(p.sos))
    # else:
    #     filtered = filter(rearranged, (p.b, p.a))

    # 3. FFT (длина окна, оконная функция, перекрытие)

    fft_length = 1000# len(p.fft_window)
    fft_overlap = 900

    windowized = windowizer(rearranged, fft_length, int(fft_length - fft_overlap))
    
    # создание из окон Windows потока Channels для вывода данных
    ch_number = 2
    windows_channel = transform_window_to_channels(windowized, ch_number)

    #resonance.createOutput(windowized, "windowized_out_2")

    #resonance.createOutput(windows_channel, "windowized_out") # only channels and events
    
    # 4. Вычисление фич - пар канал+частота - из параметров: (канал, частоты, если несколько, то усредняются)

    feature_params = []
    feature_spatial = np.zeros((0,0))
    features_selected = np.arange(4, 44) # p.features['freq']
    channels_selected = np.arange(len(p.features['ch'])) # p.features['ch']
    for i in range(len(p.features["ch"])):
        ch = int(channels_selected[i])
        for freq in features_selected:
            feature_params.append((ch, freq))
        l = len(features_selected)
        new_shape = feature_spatial.shape
        new_shape = (new_shape[0] + l, new_shape[1] + 1)
        fs = np.zeros(new_shape)
        fs[0:feature_spatial.shape[0], 0:feature_spatial.shape[1]] = feature_spatial
        fs[-l::, new_shape[1]-1] = p.features['freq'][i]
        feature_spatial = fs
    feature_params = np.array(feature_params, [("channel", "i4"), ("frequency", "f8")])
    
    features_fft = fft(windowized, feature_params)
    # print(features_fft.shape)
    # features_windows = windowizer(features_fft, fft_length//100, int(fft_length - fft_overlap)//100)
    # print(features_windows.shape, features_windows[0].shape)
    #resonance.createOutput(features_fft, "fft_out") # only channels and events

    # freq_filter = np.concatenate(np.array([freq for freq in p.features['freq']])) # for _ in range(4)])
    # print(p.features['freq'])
    # print(freq_filter.reshape(-1, 1))
    # print(freq_filter.shape)
    # features = spatial(features_fft, freq_filter.reshape(-1, 1))
    # print(features.shape)
    # print(feature_spatial.shape)
    features = spatial(features_fft, feature_spatial)
    #resonance.createOutput(features, "features_out") # only channels and events
    # print(features)
    # 5. Эпохизация (по триггеру – по цифровому триггеру или по фотодатчику [which_photo], берутся коэффициенты за последние [features_window] мс)

    # if p.which_photo:
    #     pass
    #     # resonance.pipe.transform_to_event()
    #     raw_signal_as_int = transform_channels(
    #         raw_signal, 1, lambda x: x[:, 64].astype(int)
    #     )
    #     trigger_signal = bit_signal_to_event(raw_signal_as_int, 0)

    # else:
    #     raise Exception("Not implemented yet")
    # epoch = windowize_by_events(features, trigger_signal, int(p.features_window/1000*features.SI.samplingRate/(fft_length - p.fft_overlap)))
    # epoch = windowizer(features, fft_length//1000, int(fft_length - fft_overlap)//100)
    # print(epoch.shape)
    # resonance.createOutput(epoch, "feat_out") # only channels and events

    # 6. Усреднение по всему окну для каждой фичи ([features_average])

    def apply_avg(wnd):
        return np.average(wnd, axis=0)
    
    # avg = transform_to_event(features, apply_avg)
    # print(avg)
    # print(avg.shape)
    # 7. Классификатор LDA (что нужно передать – скажи, добавлю в настройки)
    
    def apply_lda_raw(wnd):
        score_raw = float(wnd @ p.LDAW + p.LDA_Const)
        return score_raw
    
    classified_raw = transform_to_channels(features, apply_lda_raw)

    resonance.createOutput(classified_raw, "lda_raw") # only channels and events 
    
    # self.sc = pickle.load(open(sc_filename, 'rb'))
    def apply_lda(wnd):
        score_raw = float(wnd @ p.LDAW + p.LDA_Const)
        score = 1 if score_raw < 0 else 0
        return score

    # classified = transform_to_event(avg, apply_lda)
    classified = transform_to_channels(features, apply_lda)

    resonance.createOutput(classified, "lda_binary") # only channels and events 

    # resonance.createOutput(classified, "out") # only channels and events 

    # 8. Классификатор имени Анатолия

    def apply_naiveAnatolyan_raw(features):
        posterior_prob = np.zeros(features.shape)
        for ch in range(len(features)):
            posterior_prob[ch] = np.interp(features[ch], p.MdlA['bin'][ch], p.MdlA['value'][ch])
        posterior_prob = np.array(posterior_prob)
        numerator = np.prod(posterior_prob)
        denominator = np.prod(posterior_prob) + np.prod(1-posterior_prob)
        proba = round(numerator / denominator, 4)
        
        return proba

    
    classified_prob = transform_to_channels(features, apply_naiveAnatolyan_raw)
    resonance.createOutput(classified_prob, "naive_probability") # only channels and events 

    """