from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from scipy import signal

from settings.settings import Settings

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean


class DataProcessor(QObject):
    """
    Базовый класс для источника данных.

    Args:
        settings(Settings): класс для хранения настроек для обработки данных.

    Attributes: 

    Private Attributes: 
        _n_epoch (int): счётчик сохранённого количества эпох
        _epochs (list): signle-trial TEPs [n_epoch x n_samples x n_channels]
        _timestamps (list): время прихода пакета (от резонанса) --> для сохранения эпох only [n_epoch]

    Signals:
        newDataProcessed: обработка данных завершена.
        
    """
    newDataProcessed = pyqtSignal()
    updateCounter = pyqtSignal(int)
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings

        # для хранения данных
        self._epochs = []
        self._timestamps = []
        self._n_epoch = 0


        # self._n_samples = n_samples

        # флаги режимов
        self.average_data = False
        self.process_new_data = True
        self.use_eeg = bool(getattr(settings.processing_settings, "use_eeg", True))

        # функции-трансформации
        self._baseline = lambda x: x
        self._lowpass_filter = lambda x: x
        self._referef = lambda x: x
        self._car = lambda x: x
        self._transform = lambda x: x

        # данные для усреднения
        self.average_functions = None
        self.average_functions_mep = None
        self.average_mep_data = False       # overview panel
        self.average_tep_data = False       # overview panel

        # параметры усреднения
        self._n_aver_max = settings.n_aver if hasattr(settings, "n_aver") else 100
        self._aver_all = getattr(settings, "aver_all", True)
        self.aver_method = "mean"  # default, можно менять

        self._ms_to_sample = lambda x: int(x / 1000 * settings.speed.Fs)                                  # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(settings.speed.window_end - settings.speed.window_start)      # длина эпохи в сэмплах
        self._time_shift = self._ms_to_sample(0 - settings.speed.window_start)                             # смещение относительно нуля для графиков в сэпмлах

        self.aver_empty_func = {                                        # dict с функциями для усреднения
            "mean": lambda x, y, z: RollingMean(x, y, z), 
            "median": lambda x, y, z: RollingMedian(x, y, z), 
            "trimmean": lambda x, y, z: RollingTrimMean(x, y, save_all=z)
        }
        self.configure_speed()


    @pyqtSlot(object, float)
    def add_epoch(self, epoch, ts):
        """
        
        :param self: Description
        :param epoch: Description       ndarray [n_channels, n_samples]
        :param ts: Description

        Signals:
            newDataProcessed: новая эпоха добавлена.
        """

        if self.process_new_data:
            self._sync_epoch_shape(epoch)

            self._epochs.append(epoch)
            self._timestamps.append(ts)
            self._n_epoch += 1
            self.updateCounter.emit(self._n_epoch)

            if self.use_eeg and (self.average_data or self.average_tep_data):
                recreated = self._ensure_average_functions(which="TEPs")
                TEPs2plot = self._transform(epoch[:-2, :] * 1e6)     # without emg channels
                if not recreated:
                    self.update_average_functions(TEPs2plot)
            
            if self.average_mep_data:
                recreated = self._ensure_average_functions(which="MEPs")
                emg = self._baseline(epoch[-2:, :] * 1e3)  # вычесть бейзлайн и перевести в мВ
                emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
                if not recreated:
                    self.update_average_functions(emg, which="MEPs")

            self.newDataProcessed.emit()        # --> plot_updater

    def delete_epoch(self, n_delete):
        """
        n_delete - номер эпохи для удаления
        """
        if n_delete < 1 or n_delete > len(self._epochs):
            return

        self._n_epoch -= 1
        self.updateCounter.emit(self._n_epoch)

        del self._epochs[n_delete-1]                     # минус один для учёта нумерации с нуля
        del self._timestamps[n_delete-1]

        if self.use_eeg and (self.average_data or self.average_tep_data):
            self.create_average_functions(which="TEPs")
        if self.average_mep_data:
            self.create_average_functions(which="MEPs")
        
        self.newDataProcessed.emit()        # --> plot_updater

    def update_average_functions(self, TEPs, which="TEPs"):
        """add new epoch"""
        if which == "TEPs":
            for i, ch_data in enumerate(TEPs):
                avg_funcs = self.average_functions[i]
                for j in range(min(len(avg_funcs), len(ch_data))):
                    avg_funcs[j].add(ch_data[j])
        else:   # MEPs
            avg_funcs = self.average_functions_mep
            for j in range(min(len(avg_funcs), len(TEPs))):
                avg_funcs[j].add(TEPs[j])

    def calculate_avg_TEP(self):
        """calculate averaged value based on current data"""
        self._ensure_average_functions(which="TEPs")
        data_aver = []
        for avg_funcs in self.average_functions:
            average_TEPs = [f.calculate() for f in avg_funcs]
            data_aver.append(average_TEPs)
        return np.array(data_aver)
    
    def calculate_avg_MEP(self):
        """calculate averaged value based on current data"""
        self._ensure_average_functions(which="MEPs")
        data_aver = [f.calculate() for f in self.average_functions_mep]
        return np.array(data_aver)

    def calculate_avg_MEP_stats(self):
        emg_epochs = self._mep_average_window(self.get_emg_epochs())
        if emg_epochs.size == 0:
            return np.array([]), np.array([])
        ddof = 1 if emg_epochs.shape[0] > 1 else 0
        return np.mean(emg_epochs, axis=0), np.std(emg_epochs, axis=0, ddof=ddof)

    # --- Конфигурация фильтров ---

    def configure_baseline(self, enabled=True, t_from=-75, t_to=-20, method="mean"):
        self._baseline_enabled = enabled
        if enabled:
            ind_from = self._time_shift + self._ms_to_sample(t_from)
            ind_to = self._time_shift + self._ms_to_sample(t_to)
            ind_from = max(0, min(self._n_samples, ind_from))
            ind_to = max(0, min(self._n_samples, ind_to))
            if ind_from >= ind_to:
                self._baseline = lambda x: x
                return
            func = np.mean if method == "mean" else np.median
            self._baseline = lambda x: x - func(x[:, ind_from:ind_to], axis=1, keepdims=True)
        else:
            self._baseline = lambda x: x

    def configure_lowpass(self, enabled=True, freq=250, Fs=None):
        if enabled:
            Fs = Fs or self.settings.speed.Fs
            nyquist = Fs / 2
            normalized_freq = max(
                np.nextafter(0.0, 1.0),
                min(freq / nyquist, np.nextafter(1.0, 0.0))
            )
            sos = signal.butter(2, normalized_freq, btype='lowpass', output='sos')
            self._lowpass_filter = lambda x: signal.sosfilt(sos, x, axis=1)
        else:
            self._lowpass_filter = lambda x: x

    def configure_rereference(self, enabled=False, channels=None):
        if enabled and channels:
            idx = [self.settings.channels.index(ch) for ch in channels]
            self._referef = lambda x: x - np.mean(x[idx, :], axis=0, keepdims=True)
        else:
            self._referef = lambda x: x

    def configure_car(self, enabled=False, channels=None):
        if enabled and channels:
            is_selected = np.array([ch in channels for ch in self.settings.channels])
            n_sel = is_selected.sum()
            if n_sel == 0:
                raise ValueError("Не выбраны каналы для CAR")
            n_channels = len(self.settings.channels)
            W = np.eye(n_channels) - (1/n_sel) * np.outer(np.ones(n_channels), is_selected.astype(float))
            self._car = lambda x: W @ x
        else:
            self._car = lambda x: x

    # --- Создание полного пайплайна ---

    def create_full_transform(self):
        self._transform = lambda x: self._referef(
            self._car(
                self._baseline(
                    self._lowpass_filter(x)
                )
            )
        )
    
    
    # --- Усреднение ---
    def get_eeg_epochs(self):
        if not self.use_eeg:
            return np.empty((0, len(self.settings.channels), self._n_samples))
        epochs = self._current_length_epochs()
        if len(epochs) == 0:
            return np.empty((0, len(self.settings.channels), self._n_samples))
        return np.stack([
            self._transform(np.array(TEPs[:-2, :] * 1e6, dtype=float))
            for TEPs in epochs
        ], axis=0)
    
    def get_emg_epochs(self):
        epochs = self._current_length_epochs()
        if len(epochs) == 0:
            return np.empty((0, self._n_samples))
        emg_epochs = np.stack([
            np.diff(self._baseline(np.asarray(epoch[-2:], dtype=float) * 10**3), axis=0).flatten()
            for epoch in epochs
        ], axis=0)
        return emg_epochs

    def _mep_average_window(self, data):
        if self._aver_all:
            return data
        return data[-self._n_aver_max:]

    def create_average_functions(self, which="TEPs"):
        """Создать функции для усреднения TEPs"""
        function = self.aver_empty_func[self.aver_method]   # пустой трафарет
        
        if which == 'TEPs' and not self.use_eeg:
            self.average_functions = None
            return

        if len(self._epochs) != 0:
            if which == 'TEPs':
                data = self.get_eeg_epochs()
                n_samples = data.shape[-1] if data.ndim == 3 else self._n_samples
                self._sync_n_samples(n_samples)
                self.average_functions = [
                    [function(data[:, i, j], self._n_aver_max, self._aver_all)
                    for j in range(self._n_samples)]
                    for i in range(len(self.settings.channels))
                ]
            else:
                data = self.get_emg_epochs()
                n_samples = data.shape[1] if data.ndim == 2 else self._n_samples
                self.average_functions_mep = [
                    function(data[:, j], self._n_aver_max, self._aver_all)
                    for j in range(n_samples)
                ]
        else:
            if which == 'TEPs':
                self.average_functions = [
                    [function([], self._n_aver_max, self._aver_all)
                    for _ in range(self._n_samples)]
                    for _ in range(len(self.settings.channels))
                ]
            else:
                n_samples = self._expected_mep_samples()
                self.average_functions_mep = [
                        function([], self._n_aver_max, self._aver_all)
                        for j in range(n_samples)
                    ]

    def _ensure_average_functions(self, which="TEPs"):
        if which == "TEPs":
            if not self.use_eeg:
                self.average_functions = None
                return False
            needs_create = (
                not self.average_functions
                or len(self.average_functions) != len(self.settings.channels)
                or any(len(avg_funcs) != self._n_samples for avg_funcs in self.average_functions)
            )
        else:
            n_samples = self._expected_mep_samples()
            needs_create = (
                not self.average_functions_mep
                or len(self.average_functions_mep) != n_samples
            )

        if needs_create:
            self.create_average_functions(which=which)
        return needs_create

    def _expected_mep_samples(self):
        if len(self._epochs) == 0:
            return self._n_samples
        return int(np.asarray(self._epochs[-1]).shape[-1])

    def configure_speed(self):
        """Refresh sample-rate dependent values after SPEED settings change."""
        speed = self.settings.speed
        fs = float(getattr(speed, "Fs", 0) or 0)
        self._ms_to_sample = lambda x: int(x / 1000 * fs)
        self._n_samples = self._ms_to_sample(speed.window_end - speed.window_start)
        self._time_shift = self._ms_to_sample(0 - speed.window_start)
        self.average_functions = None
        self.average_functions_mep = None

    def _sync_epoch_shape(self, epoch):
        self._sync_n_samples(int(np.asarray(epoch).shape[-1]))

    def _sync_n_samples(self, n_samples):
        if n_samples <= 0 or n_samples == self._n_samples:
            return
        self._n_samples = n_samples
        self.average_functions = None
        self.average_functions_mep = None

    def configure_use_eeg(self, enabled=True):
        self.use_eeg = bool(enabled)
        if not self.use_eeg:
            self.average_functions = None
            self.average_tep_data = False

    def _current_length_epochs(self):
        return [epoch for epoch, _ in self._current_length_epoch_records()]

    def _current_length_epoch_records(self):
        return [
            (epoch, ts)
            for epoch, ts in zip(self._epochs, self._timestamps)
            if int(np.asarray(epoch).shape[-1]) == self._n_samples
        ]
    
    def update_avg_mep(self, do_average):
        self.average_mep_data = do_average
        self.create_average_functions(which="MEPs")
    
    def update_avg_tep(self, do_average):
        self.average_tep_data = bool(do_average) and self.use_eeg
        if not self.average_data:
            self.create_average_functions(which="TEPs")
    

    def cut_mep_epoch(self, mep_epoch, xmin_ms, xmax_ms):
        x_min, x_max = self._ms_to_sample(xmin_ms), self._ms_to_sample(xmax_ms)
        return mep_epoch[self._time_shift+x_min:self._time_shift+x_max] 

    # --- Применение трансформации к данным ---

    def apply_transform(self, data):
        """Применить весь пайплайн к данным"""
        return self._transform(data)

    # --- Сброс сессий ---

    def reset_sessions(self):
        self._epochs = []
        self._timestamps = []
        
        self._n_epoch = 0
        self.updateCounter.emit(self._n_epoch)

        self.average_functions = None
        self.average_functions_mep = None

        if self.use_eeg and (self.average_data or self.average_tep_data):
            self.create_average_functions(which="TEPs")
        if self.average_mep_data:
            self.create_average_functions(which="MEPs")
