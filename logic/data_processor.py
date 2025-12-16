from PyQt5.QtCore import pyqtSignal, QObject

from ..settings.settings import Settings

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

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

        # для хранения данных
        self._epochs = []
        self._timestamps = []
        self._n_epoch = 0


        self.channels = channels
        self._n_samples = n_samples
 

        self.average_functions = []
        self.average_data = average_data

        # фильтры / трансформации
        self._baseline = lambda x: x
        self._lowpass_filter = lambda x: x
        self._referef = lambda x: x
        self._CAR = lambda x: x
        self._transform = lambda x: x

    def add_epoch(self, epoch, ts):
        data = np.array(epoch).T
        self._epochs.append(data)
        self._timestamps.append(ts)
        self._n_epoch += 1

        if self.average_data:
            TEPs2plot = self._transform(data[:-2, :] * 1e6)     # without emg channels
            self.update_average_functions(TEPs2plot)

        self.newDataProcessed.emit()

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

    def create_full_transform(self):
        self._transform = lambda x: self._referef(
            self._CAR(self._baseline(self._lowpass_filter(x)))
        )