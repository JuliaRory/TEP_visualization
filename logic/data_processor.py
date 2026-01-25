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
            "trimmean": lambda x, y, z: RollingTrimMean(x, y, z)
        }


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

            self._epochs.append(epoch)
            self._timestamps.append(ts)
            self._n_epoch += 1
            self.updateCounter.emit(self._n_epoch)

            if self.average_data or self.average_tep_data:
                TEPs2plot = self._transform(epoch[:-2, :] * 1e6)     # without emg channels
                self.update_average_functions(TEPs2plot)
            
            if self.average_mep_data:
                emg = self._baseline(epoch[-2:, :] * 1e3)  # вычесть бейзлайн и перевести в мВ
                emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
                self.update_average_functions(emg, which="MEPs")

            self.newDataProcessed.emit()        # --> plot_updater

    def delete_epoch(self, n_delete):
        """
        n_delete - номер эпохи для удаления
        """
        self._n_epoch -= 1
        self.updateCounter.emit(self._n_epoch)

        del self._epochs[n_delete-1]                     # минус один для учёта нумерации с нуля
        del self._timestamps[n_delete-1]
        
        self.newDataProcessed.emit()        # --> plot_updater

    def update_average_functions(self, TEPs, which="TEPs"):
        """add new epoch"""
        if which == "TEPs":
            for i, ch_data in enumerate(TEPs):
                avg_funcs = self.average_functions[i]
                for j in range(len(avg_funcs)):
                    avg_funcs[j].add(ch_data[j])
        else:   # MEPs
            avg_funcs = self.average_functions_mep
            for j in range(len(avg_funcs)):
                avg_funcs[j].add(TEPs[j])

    def calculate_avg_TEP(self):
        """calculate averaged value based on current data"""
        data_aver = []
        for avg_funcs in self.average_functions:
            average_TEPs = [f.calculate() for f in avg_funcs]
            data_aver.append(average_TEPs)
        return np.array(data_aver)
    
    def calculate_avg_MEP(self):
        """calculate averaged value based on current data"""
        data_aver = [f.calculate() for f in self.average_functions_mep]
        return np.array(data_aver)

    # --- Конфигурация фильтров ---

    def configure_baseline(self, enabled=True, t_from=-75, t_to=-20, method="mean"):
        self._baseline_enabled = enabled
        if enabled:
            ind_from = t_from  # Здесь можно перевести в сэмплы, если нужно
            ind_to = t_to
            func = np.mean if method == "mean" else np.median
            self._baseline = lambda x: x - func(x[:, ind_from:ind_to], axis=1, keepdims=True)
        else:
            self._baseline = lambda x: x

    def configure_lowpass(self, enabled=True, freq=250, Fs=5000):
        if enabled:
            sos = signal.butter(2, freq/Fs*2, btype='lowpass', output='sos')
            self._lowpass_filter = lambda x: signal.sosfilt(sos, x, axis=0)
        else:
            self._lowpass_filter = lambda x: x

    def configure_rereference(self, enabled=False, channels=None):
        if enabled and channels:
            idx = [self.settings.channels.index(ch) for ch in channels]
            n_channels = len(self.settings.channels)
            e_r = np.zeros((n_channels, len(idx)))
            for i, idc in enumerate(idx):
                e_r[idc, i] = 1
            R = np.eye(n_channels) - e_r @ e_r.T / len(idx)
            self._referef = lambda x: R @ x
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
        return np.array([self._transform(np.array(TEPs[:-2, :] * 1e6, dtype=float)) for TEPs in self._epochs])
    
    def get_emg_epochs(self):
        epochs = np.array(self._epochs)[:, -2:] * 10**3
        emg_epochs = np.array([np.diff(self._baseline(emg), axis=0).flatten() for emg in epochs])
        return emg_epochs

    def create_average_functions(self, which="TEPs"):
        """Создать функции для усреднения TEPs"""
        function = self.aver_empty_func[self.aver_method]   # пустой трафарет
        
        if len(self._epochs) != 0:
            if which == 'TEPs':
                data = self.get_eeg_epochs()
                self.average_functions = [
                    [function(data[:, i, j], self._n_aver_max, self._aver_all)
                    for j in range(self._n_samples)]
                    for i in range(len(self.settings.channels))
                ]
            else:
                data = self.get_emg_epochs()
                self.average_functions_mep = [
                    function(data[:, j], self._n_aver_max, self._aver_all)
                    for j in range(self._n_samples)
                ]
        else:
            if which == 'TEPs':
                self.average_functions = [
                    [function([], self._n_aver_max, self._aver_all)
                    for _ in range(self._n_samples)]
                    for _ in range(len(self.settings.channels))
                ]
            else:
                self.average_functions_mep = [
                        function([], self._n_aver_max, self._aver_all)
                        for j in range(self._n_samples)
                    ]
    
    def update_avg_mep(self, do_average):
        self.average_mep_data = do_average
        self.create_average_functions(which="MEPs")
    
    def update_avg_tep(self, do_average):
        self.average_tep_data = do_average
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

        self.average_functions = []
        self.average_functions_mep = []