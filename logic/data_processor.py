from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from scipy import signal

from settings.settings import Settings

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
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

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

        # параметры усреднения
        self._n_aver_max = settings.n_aver if hasattr(settings, "n_aver") else 100
        self._aver_all = getattr(settings, "aver_all", True)
        self.aver_method = "mean"  # default, можно менять

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

            # if self.average_data:
            #     TEPs2plot = self._transform(data[:-2, :] * 1e6)     # without emg channels
            #     self.update_average_functions(TEPs2plot)

            self.newDataProcessed.emit()        # --> plot_updater

    def update_average_functions(self, TEPs):
        for i, ch_data in enumerate(TEPs):
            avg_funcs = self.average_functions[i]
            for j in range(len(avg_funcs)):
                avg_funcs[j].add(ch_data[j])

    def calculate_avg_TEP(self):
        data_aver = []
        for avg_funcs in self.average_functions:
            average_TEPs = [f.calculate() for f in avg_funcs]
            data_aver.append(average_TEPs)
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

    def create_average_functions(self, new_data=None):
        if new_data is not None:
            self._epochs = new_data

        n_samples = self._epochs.shape[1] if self._epochs is not None else 1
        n_channels = len(self.settings.channels)
        self.average_functions = [
            [self._transform(np.zeros((1, n_samples))) for _ in range(n_samples)]
            for _ in range(n_channels)
        ]

    # --- Применение трансформации к данным ---

    def apply_transform(self, data):
        """Применить весь пайплайн к данным"""
        return self._transform(data)

    # --- Сброс сессий ---

    def reset_sessions(self):
        self._epochs = []
        self.average_functions = []