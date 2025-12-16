from PyQt5.QtCore import pyqtSignal, QObject
from typing import List, Tuple, Optional
from numpy import ndarray

class DataSource(QObject):
    """
    Базовый класс для источника данных.

    Attributes: 
        is_active (bool): флаг запущен ли приёмщик 
        n_epoch (int): счётчик активного количества эпох
        epochs (list): signle-trial TEPs [n_epoch x n_samples x n_channels]
        timestamps (list): время прихода пакета (от резонанса) --> для сохранения эпох only [n_epoch]

    Signals:
        dataReady(object, float): испускается с аргументами epoch и timestamp

    Methods: 
        start(): Запускает источник данных 
        stop(): Останавливает источник данных
    
    Properties:
        all_epochs: Все сохранённые эпохи.
            Returns: 
                list of tuples: [(epoch, timestamp), ...]
        latest_epoch: Последняя добавленная эпоха.
            Returns:
                tuple or None: (epoch, timestamp)
                None, если эпох ещё нет

    """
    dataReady = pyqtSignal(object, float)  # epoch, timestamp

    def __init__(self):
        super().__init__()
        self.is_active = False  

        self.epochs = []                          
        self.timestamps = [] 
        self.n_epoch = 0           

    def start(self): 
        self.is_active = True

    def stop(self): 
        self.is_active = False
    
    @property
    def latest_epoch(self) -> Optional[Tuple[ndarray, float]]:
        if self.epochs:
            return self.epochs[-1], self.timestamps[-1]
        return None

    @property
    def all_epochs(self) -> List[Tuple[ndarray, float]]:
        return list(zip(self.epochs, self.timestamps))