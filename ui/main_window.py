from PyQt5.QtCore import Qt, QTimer, pyqtSignal,  QEvent, QPoint
from PyQt5.QtGui import QFont, QFontMetrics, QMouseEvent
from PyQt5.QtWidgets import (QWidget, QGridLayout,QLabel, qApp, QFrame, QHBoxLayout, QSizePolicy, 
                             QSplitter, QApplication, QFileDialog, QMessageBox)
import numpy as np
import pandas as pd

import os
import json
import h5py
from scipy import signal
import time
from datetime import datetime
from collections import deque

from .settings_panel import SettingsPanel
from .TEP_plot_area import TEPsPanel
from .TEP_suppl_plot_area import TEPsSupplPanel
from .MEP_plot_area import MEPsPanel

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean

WIDTH_SET, HEIGHT_SET = 1850, 900  # параметры изначального окна интерфейса
MICROVOLT = "\u03BC"+"V"
filename = r".\resources\mumeg_mks64.ced"
df = pd.read_csv(filename, sep="\t")
CHANNELS = df.labels.values

PALETTE = {
    "app_bg": "#f7f6f2",
    "border": "#d1cfc9",
    "text": "#2d2d2d",

    "panel_left": {
        "background": "#2b2e2e",
        "text": "#e8e8e3",
        "button": "#6a7b76",
        "button_hover": "#4b5754",
        "accent": "#a8c686"
    },

    "tep_plot": {
        "background": "#fbfbfa",
        "grid": "#d9d7d2",
        "lines": ["#697d63", "#b49b6e", "#8a9a9f"],
        "baseline": "#c4b59f"
    },

    "emg_plot": {
        "background": "#eae7e1",
        "grid": "#d0cdc7",
        "signal": "#b5646b",
        "baseline": "#948c75",
        "artifact": "#d8a47f"
    }
}

class MainWindow(QWidget):
    start_calc_signal = pyqtSignal()

    def __init__(self, input_stream, filename_params):
        super().__init__()

        """Внешний вид окна"""
        self.setWindowTitle("TEP visualization")
        self.resize(WIDTH_SET, HEIGHT_SET)
        #self.setWindowIcon(QtGui.QIcon(r"./pictures/icon.png"))

        """Параметры и структуры данных"""
        self.dispatcher = input_stream                    # пустая-функция обработчик входящего потока от резонанса     
        self.dispatcher.set_callback(self._get_data)      # установить новую функцию-обработчик входящего потока

        with open(filename_params) as json_data:          # вгрузить настройки приложения
            self.params = json.load(json_data)  
        
        self._init_state()                                # инициализация начального состояния переменных
        
        """Визуальная часть интерфейса"""
        self._setup_ui()                                  # создание всех виджетов
        self._setup_main_grid()                           # расположение виджетов на экране
        
        """Взаимосвязи между элементами интерфейса"""
        self._setup_connections()                         
                
        """Показать окно"""
        self.show()


    # --- Инициализация ---
    def _init_state(self):
        """Создаёт параметры и переменные"""
        self.n_epoch = 0                                    # счётчик количества хранимых в памяти эпох
        self.st_TEPs = []                                   # список для хранения всех signle-trial TEPs
        self.ts = []
        self.EMG = deque(maxlen=5)
        self.average_functions = []                         # список хранящий функции для расчёта средних

        self._data_loaded = []                              # список с подгруженными датасетами
        self._data_loaded_labels = []                       # список с названиями подгруженных файлов (для легенды)

        self.save_all = self.params["save_all"]             # флаг хранить ли все эпохи
        self.aver_method = self.params["aver_methods"][0]   # метод для усреднения эпох
        self.n_aver_max = self.params["n_aver"]             # количество эпох на усреднение
        self.aver_all = self.params["aver_all"]             # флаг нужно ли усреднять все эпохи

        self._average_data = True if self.params["curr_mode_idx"] == 0 else False           # 0 == "Усреднение" из  ["Усреднение", "Одиночные пробы"]
        self._process_new_data = True if self.params["curr_mode_data_idx"] == 0 else False  # 0 == "Новые данные" из ["Новые данные", "Сравнение"]

        self.aver_empty_func = {                                        # dict с функциями для усреднения
            "mean": lambda x, y, z: RollingMean(x, y, z), 
            "median": lambda x, y, z: RollingMedian(x, y, z), 
            "trimmean": lambda x, y, z: RollingTrimMean(x, y, z)
        }
        self._transform = lambda x: x

        self.specific_epoch = False                         # флаг для отслеживания режима показа определенной эпохи или стандартного

        self.SPEED = self.params["SPEED"]
        self.ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])                                  # функция для пересчёта мс в сэмплы
        self.n_samples = self.ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])       # длина эпохи в сэмплах
        self.time_shift = self.ms_to_sample(0 - self.SPEED["window_start"])                             # смещение относительно нуля для графиков в сэпмлах

        # --- создать и открыть файл для автоматической записи получаемых данных ---
        cur_time = datetime.now().strftime("%Y.%m.%d_%H.%M")
        self.autosave_file = h5py.File(os.path.join("data/autosave", f"{cur_time}.h5"), "w")
        self.dset = self.autosave_file.create_dataset("epochs", (0, 66), maxshape=(None, 66), dtype='float32')  # для эпох (64 EEG + 2 EMG)
        self.tset = self.autosave_file.create_dataset("timestamps", (0, ), maxshape=(None, ), dtype='int64')    # для таймстемпов резонанса (в нс)

    # --- UI ---
    def _setup_ui(self):
        """Создаёт всю визуальную часть интерфейса."""

        hor_ratio = self.params["layout"]["horizontal_ratios"]
        cen_ratio = self.params["layout"]["center_ratio"]
        rigth_ratio = self.params["layout"]["right_ratio"]

        self.settings_panel = SettingsPanel(parent=self,
                                            params=self.params,
                                            channels=CHANNELS)
        
        self.main_teps_panel = TEPsPanel(parent=self,
                                         params=self.params, 
                                         init_size=[int(hor_ratio[1] * WIDTH_SET), int(cen_ratio*HEIGHT_SET)])
        
        self.suppl_teps_panel = TEPsSupplPanel(parent=self,
                                         params=self.params["TEP_suppl_plot"], 
                                         init_size=[int(hor_ratio[2] * WIDTH_SET), HEIGHT_SET])
        
        self.meps_panel = MEPsPanel(parent=self,
                                    params=self.params["MEP_plot"], 
                                    init_size=[int(hor_ratio[1] * WIDTH_SET), int((1-cen_ratio)*HEIGHT_SET)])
        
        # self.topoplots_panel = TopoplotPanel()
        

    # --- Layout ---
    def _setup_main_grid(self):
        # Grid layout structure: 
        # +-------+-------------------------+---------+ 
        # | set.  |       TEP1              |  MEP    |
        # |       |                         |         |
        # |       |                         |         |
        # |       |                         |         |
        # |       |                         +---------+
        # |       |                         | topo    |
        # |       +-------------------------+         |
        # |       |      TEP2               |         |
        # |       |                         |         |
        # |       |                         |         |
        # +-------+-------------------------+---------+

        ratio = self.params["layout"]["center_ratio"]
        splitter_center = QSplitter(Qt.Vertical, parent=self)        # позволяет изменять размер
        splitter_center.addWidget(self.main_teps_panel)
        splitter_center.addWidget(self.meps_panel)
        splitter_center.setCollapsible(0, False)
        splitter_center.setOpaqueResize(False)
        splitter_center.setSizes([int(ratio*HEIGHT_SET), int((1-ratio)*HEIGHT_SET)])   # Можно задать начальные пропорции
        splitter_center.setStretchFactor(0, 7)
        splitter_center.setStretchFactor(1, 3) # растягивается в два раза сильнее
        splitter_center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ratio = self.params["layout"]["right_ratio"]
        # splitter_right = QSplitter(Qt.Vertical, parent=self)        # позволяет изменять размер
        # splitter_right.addWidget(self.topoplots_panel)
        # splitter_right.addWidget(self.suppl_teps_panel)
        # splitter_right.setCollapsible(0, False)
        # splitter_right.setOpaqueResize(False)
        # splitter_right.setSizes([int(ratio*HEIGHT_SET), int((1-ratio)*HEIGHT_SET)])   # Можно задать начальные пропорции
        # splitter_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.splitter = QSplitter(Qt.Horizontal, parent=self)        # позволяет изменять размер
        # splitter.addWidget(self.settings_panel)
        self.splitter.addWidget(self.settings_panel.scroll)
        self.splitter.addWidget(splitter_center)
        self.splitter.addWidget(self.suppl_teps_panel)
        self.splitter.setCollapsible(0, False)
        self.splitter.setOpaqueResize(False)
        
        ratio = self.params["layout"]["horizontal_ratios"]
        self.splitter.setSizes([int(ratio[0] * WIDTH_SET), int(ratio[1] * WIDTH_SET), int(ratio[2] * WIDTH_SET)])   # Можно задать начальные пропорции
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 5) # растягивается в два раза сильнее
        self.splitter.setStretchFactor(2, 3)
        self.splitter.setGeometry(0, 0, WIDTH_SET, HEIGHT_SET)  #  вручную задаём положение и размер

        # фильтр событий на splitter
        self.splitter.installEventFilter(self)

    # --- Сигналы ---
    def _setup_connections(self):
        self.start_calc_signal.connect(self._initial_calculations)

        self.settings_panel.button_save.clicked.connect(self._on_button_save_click)
        self.settings_panel.button_load.clicked.connect(self._on_button_load_click)
        self.settings_panel.button_restart.clicked.connect(self._on_restart_button_click)
        self.settings_panel.button_show_epoch.clicked.connect(self._on_show_epoch_button_click)
        self.settings_panel.button_remove_epoch.clicked.connect(self._on_remove_epoch_button_click)
        self.settings_panel.button_aver.clicked.connect(self._on_update_averaging_button_click)
        self.settings_panel.button_update_lowpass.clicked.connect(self._on_update_lowpass_button_click)
        self.settings_panel.button_update_rereference.clicked.connect(self._on_update_rereference_button_click)
        self.settings_panel.button_update_baseline.clicked.connect(self._on_update_baseline_button_click)
        self.settings_panel.button_car.clicked.connect(self._on_update_CAR_button_click)

        self.settings_panel.combo_box_mode.currentIndexChanged[int].connect(self._on_change_mode)
        self.settings_panel.combo_box_mode_data.currentIndexChanged[int].connect(self._on_change_mode_data)

    # --- Логика ---
    def _get_data(self, msg, timestamp):
        if not self._process_new_data:
            print("---> Включён режим загрузки старых данных. Новые данные не приняты.")
            return None
        
        # сохранить новые данные
        self._save_data(msg, timestamp) 

        # если не стоит флаг "хранить все" и эпох больше допустимого: True -- обрезать, False -- сохранить все
        trim_last = (not self.save_all) & (self.n_epoch + 1 > self.settings_panel.spin_box_save_epoch.value())

        if not trim_last:          # если не обрезать, то обновить счётчик количества эпох
            self.n_epoch += 1
            self._update_label_counter(self.n_epoch)
        else:                       # если обрезать
            self.st_TEPs = self.st_TEPS[1:]                     # удалить первую эпоху
            self.ts = self.ts[1:]

        # распаковать "сообщение" в формате {"TEPs": list of EEG data in microvolt} 
        # data = np.array(json.loads(msg)["TEPs"]).T  # [n_channels x n_samples]
        data = np.array(msg)[:, :-2].T * 10**6

        self.st_TEPs.append(data)                   # добавить новый массив в список хранимых TEPs  [n_epoch x n_channels x n_samples]
        self.ts.append(timestamp)

        # нужные преобразования
        
        data = self._transform(data)                    # [n_ch x n_samples] 
        
        if self._average_data:
            data_aver = []
            for i, ch_data in enumerate(data):
                avg_funcs = self.average_functions[i]
                n = len(avg_funcs)
                for j in range(n): # обновить сохранённые функции
                    avg_funcs[j].add(ch_data[j])
                average_TEPs = np.array([f.calculate() for f in avg_funcs])  # усреднённые TEPs
                data_aver.append(average_TEPs)
            data = np.array(data_aver)
        
        self._update_plots([data])

        emg = self.baseline(np.array(msg)[:, -2:].T)
        emg = np.diff(emg, axis=0).flatten()      # ЭМГ

        x_min, x_max = self.ms_to_sample(self.params["MEP_plot"]["xmin_ms"]), self.ms_to_sample(self.params["MEP_plot"]["xmax_ms"])
        emg2plot = emg[self.time_shift+x_min:self.time_shift+x_max] * 1E3
        self.meps_panel.figure.update_emg(emg2plot)

        t4 = time.perf_counter()

    def _save_data(self, epoch, ts):
        n = self.dset.shape[0]
        self.dset.resize(n + epoch.shape[0], axis=0)
        self.dset[n:] = epoch
 
        self.tset.resize(self.tset.shape[0] + 1, axis=0)
        self.tset[-1] = ts

    def _on_button_save_click(self):
        # открытие диалога для выбора названия и места хранения файла
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Задайте имя файла",
            "data/exports",
            "HDF5 Files (*.h5);;All Files (*)"
        )

         # пользователь нажал Cancel
        if not file_path:
            print("---> Сохранение отменено")
            return None 
        
        data2save = np.array(self.st_TEPs[:]).transpose(0, 2, 1).reshape(-1, 64)      # (n_samples, n_channels)
        ts2save = np.array(self.ts)
        # если выбран файл
        with h5py.File(file_path, "w") as h5f:
            data = h5f.create_dataset("epochs", data=data2save, dtype='float32')      # для эпох (64 EEG + 2 EMG)
            data.attrs["Fs"] = self.SPEED["Fs"]
            data.attrs["n_samples"] = self.n_samples
            data.attrs["n_epochs"] = len(self.st_TEPs)
            
            tdata = h5f.create_dataset("timestamps", data=ts2save, dtype='int64')      # для таймстемпов резонанса (в нс)
            tdata.attrs["units"] = "ns"

    def _on_button_load_click(self):
        # очистить стек подгруженных данных
        self._data_loaded = []
        self._data_loaded_labels = []

        # открыть диалог для выбора файла/файлов
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите файлы",
            "data/exports",                     # стартовая директория
            "HDF5 (*.h5 *.hdf5);;Все файлы (*)"
        )
        
        # пользователь нажал Cancel
        if not paths:
            print("---> Подгрузка файлов отменена")
            return None  
        
        # если выбран файл/файлы - загрузить в память данные
        for file_path in paths:
            with h5py.File(file_path, "r") as h5f:
                stream = h5f['epochs'][:]
                n_epochs = h5f['epochs'].attrs["n_epochs"]
                n_samples = h5f['epochs'].attrs["n_samples"]

                epochs =  stream.reshape((n_epochs, n_samples, stream.shape[1])).transpose(0, 2, 1)
                self._data_loaded.append(epochs)

                name = os.path.splitext(os.path.basename(file_path))[0] # имя файла без разрешения
                self._data_loaded_labels.append(name)

                print(f">> {name} : n_epoch = {n_epochs}")
        
        # self._update_label_counter(self.n_epoch)
        self._update_data()

    def _on_restart_button_click(self):
        raise Warning("Кнопка пока не работает Т_Т")
        # self.n_epoch = 0
        # self.update_label_counter()

        # self.st_TEPs = []
        # self.average_functions = []
        # self.update_averaging()

        # self.restart_plots()
    
    def _on_show_epoch_button_click(self):
        raise Warning("Кнопка пока не работает Т_Т")
        if self.specific_epoch: # если был режим показа отдельной эпохи - вернуться к стандартному отображению
            self._update_plots()
            self.settings_panel.button_show_epoch.setText("Показать эпоху")
        else:                   # если не был включён режим показа отдельной эпохи - показать её
            n_show = self.settings_panel.spin_box_show_epoch.value()    # номер эпохи для просмотра
            data = self.CAR(self.baseline(self.st_TEPs[n_show-1]))
            for i in range(len(CHANNELS)):
                self.main_teps_panel.figure.update_data(i, data[i], self.time_shift)
            self.settings_panel.button_show_epoch.setText("Стандартный режим")
            self.main_teps_panel.figure.update_image()
        self.specific_epoch = not self.specific_epoch

    def _on_remove_epoch_button_click(self):  
        raise Warning("Кнопка пока не работает Т_Т")
        self.n_epoch -= 1
        self.update_label_counter()

        n_delete = self.settings_panel.spin_box_remove_epoch.value()    # номер эпохи для удаления 

        del self.st_TEPs[n_delete-1]                     # минус один для учёта нумерации с нуля

        if self._average_data:
            self.create_average_functions()
        if self.n_epoch > 0:
            self.update_plots()
        else:
            self.restart_plots()

    def _on_update_averaging_button_click(self):
        """применение настроек для усреднения эпох"""
        
        ## обновить количество сохранённых эпох
        self.save_all = self.settings_panel.check_box_save_epoch.isChecked()   # флаг нужно ли хранить все эпохи
        max_value = self.settings_panel.spin_box_save_epoch.value()            # максимальное значение эпох на сохранение
        if (not self.save_all) & (self.n_epoch > max_value):    # если нужно обрезать 
            d = self.n_epoch - max_value                        # сколько лишних
            self.st_TEPs = self.st_TEPs[d:]                     # обрезать list с хранимыми TEPs
            self.n_epoch = max_value                            # обновить счётчик эпох
            self.update_label_counter()                         

        ## обновить отображение усреднённых или сингл-трайл графиков
        self.aver_mode = self.settings_panel.check_box_aver_mode.isChecked()   # флаг усреднять (True) или single-trial (False)
        self.aver_all = self.settings_panel.check_box_aver_epoch.isChecked()   # флаг нужно ли усреднять все эпохи
        self.aver_method = self.settings_panel.combo_box_aver.currentText()    # текущий выбранный метод усреднения
        self.n_aver_max = self.settings_panel.spin_box_aver_epoch.value()      # количество эпох на усреднение
        
        if self._average_data:  # если усреднять - создать новые функции
            self._create_average_functions()

        if self.n_epoch > 0:        # если есть накопленные эпохи - нарисовать
            self._update_data()

    def _on_update_baseline_button_click(self):
        self.apply_baseline = self.settings_panel.check_box_baseline.isChecked()   # вычитать ли бейзлайн
        if self.apply_baseline:
            self.baseline_start, self.baseline_end = self.settings_panel.spin_box_baseline_start.value(), self.settings_panel.spin_box_baseline_end.value()
            ind_start = self.ms_to_sample(self.baseline_start - self.SPEED["window_start"])
            ind_end = ind_start + self.ms_to_sample(self.baseline_end - self.baseline_start) + 1
            func = (lambda x: np.mean(x, axis=1)) if self.settings_panel.combo_box_baseline.currentText() == 'mean' else (lambda x: np.median(x, axis=1))
            self.calculate_baseline = lambda x: func(x[:, ind_start:ind_end]).reshape((-1, 1))
        self.baseline = (lambda x: x - self.calculate_baseline(x)) if self.apply_baseline else (lambda x: x)
        if self._average_data and self.n_epoch > 0:  # если усреднять - создать новые функции
            self._create_average_functions()
        if self.n_epoch > 0:
            self._update_data()
    
    def _on_update_lowpass_button_click(self):
        
        self.apply_filter = self.settings_panel.check_box_lowpass.isChecked()
        if self.apply_filter:
            self.sos_lowpass = signal.butter(2, self.settings_panel.spin_box_lowpass.value()/self.SPEED["Fs"]*2, btype='lowpass', output='sos')
        self.lowpass_filter = (lambda x: signal.sosfilt(self.sos_lowpass, x, axis=0)) if self.apply_filter else (lambda x: x)           # функция для применения фильтра
        if self._average_data and self.n_epoch > 0:  # если усреднять - создать новые функции
            self._create_average_functions()
        if self.n_epoch > 0:
            self._update_data()

    def _on_update_rereference_button_click(self):
        self.apply_reref = self.settings_panel.check_box_rereference.isChecked()
        self.reref_channel = self.settings_panel.combo_box_rereference.checkedItems()[0]
        ind = np.where(CHANNELS == self.reref_channel)[0][0]

        n_channels = len(CHANNELS)
        e_r = np.zeros((n_channels, 1)); 
        e_r[ind, 0] = 1.0
        R = np.eye(n_channels) - np.ones((n_channels, 1)) @ e_r.T

        #self.referef = (lambda x: x - x[ind]) if self.apply_reref else (lambda x: x)
        self.referef = (lambda x: R @ x) if self.apply_reref else (lambda x: x)
        if self._average_data and self.n_epoch > 0:  # если усреднять - создать новые функции
            self._create_average_functions()
        if self.n_epoch > 0:
            self._update_data()

    def _on_update_CAR_button_click(self):
        self.apply_CAR= self.settings_panel.check_box_car.isChecked()   # применять ли CAR
        if self.apply_CAR: 
            self.CAR_channels = self.settings_panel.combo_box_channels.checkedItems()
            n_sel = len(self.CAR_channels)
            if n_sel == 0:
                raise ValueError("Не отмечены каналы для построения CAR фильтра.")
            is_selected = np.array([ch in self.CAR_channels for ch in CHANNELS])
            n_channels = len(CHANNELS)
            W = np.eye(n_channels) - (1/n_sel) * np.outer(np.ones(n_channels), is_selected.astype(float)) # матрица фильтра CAR                 
        self.CAR = (lambda x: W @ x) if self.apply_CAR else (lambda x: x)           # функция для вычисления CAR
        if self._average_data and self.n_epoch > 0:  # если усреднять - создать новые функции
            self._create_average_functions()
        if self.n_epoch > 0:
            self._update_data()

    def _create_full_transform(self):
        self._transform = lambda x: self.referef(
            self.CAR(
                self.baseline(
                    self.lowpass_filter(
                        x
                        )
                    )
                )
            )

    def _create_average_functions(self):
        function = self.aver_empty_func[self.aver_method]
        if self.n_epoch != 0:
            d = self.n_epoch - self.n_aver_max if not self.aver_all else 0
            data = np.array([self._transform(np.array(TEPs, dtype=float)) for TEPs in self.st_TEPs[d:]])

            self.average_functions = [
                [function(data[:, i, j], self.n_aver_max, self.aver_all)
                for j in range(self.n_samples)]
                for i in range(len(CHANNELS))
            ]
        else:
            self.average_functions = [
                [function([], self.n_aver_max, self.aver_all)
                for _ in range(self.n_samples)]
                for _ in range(len(CHANNELS))
            ]

    def _update_data(self):

        if self._process_new_data:  
            if not self._average_data:
                data2plot = self._transform(self.st_TEPs[-1])
            else:
                data_aver = []
                for i in range(len(CHANNELS)):
                    average_TEPs = np.array([f.calculate() for f in self.average_functions[i]])  # усреднённые TEPs
                    data_aver.append(average_TEPs)
                data2plot = np.array(data_aver)

        else:
            function = self.aver_empty_func[self.aver_method]
            data2plot = []
            for data_raw in self._data_loaded:
                if not self._average_data:
                    data2plot.append(self._transform(data_raw[-1]))     # последняя эпоха
                else:
                    data = np.array([self._transform(np.array(TEPs, dtype=float)) for TEPs in data_raw])
                    data_aver = []

                    for i in range(len(CHANNELS)):
                        average_functions = [function(data[:, i, j], self.n_aver_max, self.aver_all)
                            for j in range(self.n_samples)
                        ]
                        average_TEPs = np.array([f.calculate() for f in average_functions])  # усреднённые TEPs
                        data_aver.append(average_TEPs)
                    data2plot.append(np.array(data_aver))
        
        self._update_plots(data2plot)

    def _update_plots(self, data):
        t0 = time.perf_counter()
        
        if self._process_new_data:
            self.main_teps_panel.figure.update_data(data)      # отобразить  TEPs в режиме реального времени
        else:
            self.main_teps_panel.figure.compare_data(data, self._data_loaded_labels)     # отобразить TEPs в режме сравнения
        
        t1 = time.perf_counter()

        if len(data) == 1:  # если загружен только один датасет
            data = data[0]
            x_min, x_max = self.ms_to_sample(self.params["TEP_suppl_plot"]["xmin_ms"]), self.ms_to_sample(self.params["TEP_suppl_plot"]["xmax_ms"])
            data2plot = data[:, self.time_shift+x_min:self.time_shift+x_max]
            self.suppl_teps_panel.figure.update_plot(data2plot)

            t2 = time.perf_counter()

            if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
                timestamps = self.params["TEP_suppl_plot"]["timestamps_ms"]
                for i, t_ms in enumerate(timestamps):
                    t = self.ms_to_sample(t_ms)
                    self.suppl_teps_panel.figure_topo[i].plot_topomap(data[:, t])
            t3 = time.perf_counter()
            
            print(f"update main tep plots: {t1 - t0:.6f} сек")
            print(f"update suppl_teps_panel (new epoch): {t2 - t1:.6f} сек")
            print(f"update topoplots_panel (new epoch): {t3 - t2:.6f} сек")
            # print(f"update meps_panel (new epoch): {t4 - t3:.6f} сек")
            # print(f"update whole (new epoch): {t4 - t0:.6f} сек")
    
    def _on_change_mode(self, idx):
        self._average_data = True if idx == 0 else False      # из  ["Усреднение", "Одиночные пробы"]
        
    def _on_change_mode_data(self, idx):
        print(idx)
        self._process_new_data = True if idx == 0 else False  # из ["Новые данные", "Сравнение"]


    def _initial_calculations(self):
        t0 = time.perf_counter()

        self._on_update_CAR_button_click()
        self._on_update_baseline_button_click()
        self._on_update_lowpass_button_click()
        self._on_update_rereference_button_click()
        self._on_update_averaging_button_click()

        self._create_full_transform()

        t5 = time.perf_counter()
        print(f"все предварительные рассчёты: {t5 - t0:.6f} сек")
 

    # --- Финализация ---
    def _post_init(self):
        self.setWindowTitle("Demo App")
        self.resize(400, 200)
        self.show()

   
    # --- События ---
    def resizeEvent(self, event):
        self.splitter.setGeometry(0, 0, self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(10, self.start_calc_signal.emit)

    def eventFilter(self, obj, event):
        if obj is self.splitter and event.type() in (
            QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            
            # преобразуем координаты
            global_pos = self.splitter.mapToGlobal(event.pos())

            topoplots = self.suppl_teps_panel.figure_topo
            for topoplot in topoplots:
                local_pos = topoplot.mapFromGlobal(global_pos)

                if topoplot.geometry().contains(topoplot.mapFromGlobal(global_pos)):
                    # создаём новое событие для frame
                    new_event = QMouseEvent(
                        event.type(), local_pos, global_pos,
                        event.button(), event.buttons(), event.modifiers()
                    )
                    QApplication.sendEvent(topoplot, new_event)
                    return True  # блокируем обработку splitter'ом
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        try:
            n = self.tset.shape[0]
            file_path = self.autosave_file.filename
            self.autosave_file.close()
            if n == 0:      # удалить, если ничего не было сохранено
                os.remove(file_path)
            print("---> Autofile закрыт корректно.")
        except Exception as e:
            print(f"---> Ошибка закрытия autofile: {e}")

        event.accept()


    # --- неприкаянные функции ---
    def restart_plots(self):
        self.main_teps_panel.figure.refresh()

    
    def launch_speed(self):
        """сохранить настройки SPEED"""
        self.SPEED = {}
        self.SPEED["window_start"] = self.spin_box_window_start.value()
        self.SPEED["window_end"] = self.spin_box_window_end.value()

        self.SPEED["artifact"] = self.check_box_artifact.isChecked()
        self.SPEED["artifact_start"] = self.spin_box_artifact_start.value()
        self.SPEED["artifact_end"] = self.spin_box_artifact_end.value()

        self.SPEED["notch"] = self.check_box_notch.isChecked()
        self.SPEED["notch_fr"] = self.spin_box_notch_fr.value()
        self.SPEED["highpass"] = self.check_box_highpass.isChecked()
        self.SPEED["low_freq"] = self.spin_box_highpass.value()
        self.SPEED["lowpass"] = self.check_box_lowpass.isChecked()
        self.SPEED["high_freq"] = self.spin_box_lowpass.value()

        self.SPEED["resampling"] = self.check_box_resampling.isChecked()
        self.SPEED["Fs_orig"] = self.spin_box_fs.value()
        self.SPEED["Fs"] = self.spin_box_resampling.value()

        self.ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])       # функция для пересчёта мс в сэмплы
        self.n_samples = self.ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])    # длина эпохи в сэмплах
        self.time_shift = self.ms_to_sample(0 - self.SPEED["window_start"])    # смещение относительно нуля для графиков в сэпмлах

        with open(self.params["SPEED_settings_path"], 'w') as f:
            json.dump(self.SPEED, f)
    
    def _update_label_counter(self, n_epoch):
        self.main_teps_panel.label_n_epoch.setText('Количество эпох: {}'.format(n_epoch))
        qApp.processEvents()    # для обновления отображения в Qt-приложении

        # если эпохи есть, то разрешить их очистку из памяти по нажатию кнопки 
        # active_status = True if self.n_epoch > 0 else False      
        # self.settings_panel.button_restart.setEnabled(active_status)
        # self.settings_panel.shortcut_restart.setEnabled(active_status)
        # self.settings_panel.button_remove_epoch.setEnabled(active_status)
        # #self.shortcut_remove_epoch.setEnabled(True)
        # self.settings_panel.button_show_epoch.setEnabled(active_status)

        # self.settings_panel.spin_box_show_epoch.setMaximum(self.n_epoch)
        # self.settings_panel.spin_box_show_epoch.setValue(self.n_epoch)
        # self.settings_panel.spin_box_remove_epoch.setMaximum(self.n_epoch)
        # self.settings_panel.spin_box_remove_epoch.setValue(self.n_epoch)


    def create_box_settings(self):
        """Настройки отображения"""

        self.label_n_epoch =  QLabel('Количество эпох: {}'.format(self.n_epoch), self)
        font = QFont('Helvetica', 16)
        font.setBold(True)
        self.label_n_epoch.setFont(font)
        text_width = QFontMetrics(font).horizontalAdvance('Количество эпох: 1000')  # ширина текста в пикселях
        text_height = QFontMetrics(font).height()
        self.label_n_epoch.setFixedSize(text_width, text_height)        # чтобы помещался текст с разным количеством эпох

        """настройки SPEED"""
        box_window = QFrame(self.box_settings)                         # window size
        box_window.setFrameShape(QFrame.Box)        
        box_window.setLineWidth(1) 
        layout_window = QHBoxLayout(box_window)
        layout_window.setSpacing(0)       # пробелы между виджетами
        layout_window.setContentsMargins(2, 2, 2, 2)       # отступы от края
        label = QLabel("Размер окна:", self)
        start, end = self.SPEED["window_start"], self.SPEED["window_end"]
        self.spin_box_window_start = self.spin_box(-1000, end, start, step=10, parent=box_window)
        self.spin_box_window_end = self.spin_box(start, 1000, end, step=10, parent=box_window)
        label_start = QLabel("от", box_window)
        label_end = QLabel("до", box_window)
        label_ms = QLabel("мс", box_window)
        layout_window.addWidget(label)
        layout_window.addWidget(label_start)
        layout_window.addWidget(self.spin_box_window_start)
        layout_window.addWidget(label_end)
        layout_window.addWidget(self.spin_box_window_end)
        layout_window.addWidget(label_ms)


        box_artifact = QFrame(self.box_settings)                         # TMS artifact
        box_artifact.setFrameShape(QFrame.Box)        
        box_artifact.setLineWidth(1) 
        layout_artifact = QGridLayout(box_artifact)
        layout_artifact.setSpacing(0)       # пробелы между виджетами
        layout_artifact.setContentsMargins(2, 2, 2, 2)       # отступы от края
        self.combo_box_artifact = self.create_combobox(['linear interpolation', 'zeros'], parent=box_artifact)
        self.check_box_artifact = self.check_box(self.SPEED['artifact'], 'ТМС артефакт', parent=box_artifact)
        start, end = self.SPEED["artifact_start"], self.SPEED["artifact_end"]
        self.spin_box_artifact_start = self.spin_box(self.SPEED["window_start"], end, start, step=1, parent=box_artifact)
        self.spin_box_artifact_end = self.spin_box(start, self.SPEED["window_end"], end, step=1, parent=box_artifact)
        label_start = QLabel("от", box_artifact)
        label_end = QLabel("до", box_artifact)
        label_ms = QLabel("мс", box_artifact)
        layout_artifact.addWidget(self.check_box_artifact, 0, 0, 1, 3)
        layout_artifact.addWidget(self.combo_box_artifact, 0, 3, 1, 2)
        layout_artifact.addWidget(label_start, 1, 0)
        layout_artifact.addWidget(self.spin_box_artifact_start, 1, 1)
        layout_artifact.addWidget(label_end, 1, 2)
        layout_artifact.addWidget(self.spin_box_artifact_end, 1, 3)
        layout_artifact.addWidget(label_ms, 1, 4)

        box_filtering = QFrame(self.box_settings)                            ## filtering
        box_filtering.setFrameShape(QFrame.Box)       
        box_filtering.setLineWidth(1)
        layout_filtering = QGridLayout(box_filtering)
        layout_filtering.setSpacing(0)
        layout_filtering.setContentsMargins(2, 2, 2, 2)       # отступы от края
        label = QLabel('Фильтрация', box_filtering)
        label_hz1 = QLabel('Гц', box_filtering)
        label_hz2 = QLabel('Гц', box_filtering)
        label_hz3 = QLabel('Гц', box_filtering)
        self.check_box_notch = self.check_box(self.SPEED["notch"], 'Notch', parent=box_filtering)
        self.spin_box_notch_fr = self.spin_box(min=0, max=100, value=self.SPEED["notch_fr"], parent=box_filtering)
        self.check_box_highpass = self.check_box(self.SPEED["highpass"], 'highpass', parent=box_filtering)
        self.spin_box_highpass = self.spin_box(min=1, max=100, value=self.SPEED["low_freq"], parent=box_filtering)
        self.check_box_lowpass = self.check_box(self.SPEED["lowpass"], 'lowpass', parent=box_filtering)
        self.spin_box_lowpass = self.spin_box(min=1, max=100, value=self.SPEED["high_freq"], parent=box_filtering)
        layout_filtering.addWidget(label, 0, 0, 1, 2)
        layout_filtering.addWidget(self.check_box_notch, 1, 0)
        layout_filtering.addWidget(self.spin_box_notch_fr, 1, 1)
        layout_filtering.addWidget(label_hz1, 1, 2)
        layout_filtering.addWidget(self.check_box_highpass, 2, 0)
        layout_filtering.addWidget(self.spin_box_highpass, 2, 1)
        layout_filtering.addWidget(label_hz2, 2, 2)
        layout_filtering.addWidget(self.check_box_lowpass, 3, 0)
        layout_filtering.addWidget(self.spin_box_lowpass, 3, 1)
        layout_filtering.addWidget(label_hz3, 3, 2)

        box_resampling = QFrame(self.box_settings)                               ## resampling
        box_resampling.setFrameShape(QFrame.Box)        
        box_resampling.setLineWidth(1) 
        layout_resampling = QGridLayout(box_resampling)
        layout_resampling.setSpacing(0)
        layout_resampling.setContentsMargins(2, 2, 2, 2)
        self.check_box_resampling = self.check_box(self.SPEED["resampling"], 'Ресемплинг', parent=box_resampling)
        label_hz1 = QLabel('Гц', box_resampling)
        label_hz2 = QLabel('Гц', box_resampling)
        self.spin_box_fs = self.spin_box(1000, 50000, self.SPEED["Fs_orig"], step=1000, parent=box_resampling)
        label_resample = QLabel('→', box_resampling)
        self.spin_box_resampling = self.spin_box(250, 25000, self.SPEED["Fs"], step=250, parent=box_resampling)
        layout_resampling.addWidget(self.check_box_resampling, 0, 0, 1, 3)
        layout_resampling.addWidget(self.spin_box_fs, 1, 0)
        layout_resampling.addWidget(label_hz1, 1, 1)
        layout_resampling.addWidget(label_resample, 1, 2)
        layout_resampling.addWidget(self.spin_box_resampling, 1, 3)
        layout_resampling.addWidget(label_hz2, 1, 4)

        box_SPEED = QFrame(self.box_settings)                            ## SPEED processing
        layout_SPEED = QGridLayout(box_SPEED)
        label = QLabel('SPEED settings', box_SPEED)
        self.button_speed = self.create_button("Сохранить настройки", self.launch_speed, True, box_SPEED)
        layout_SPEED.addWidget(label, 0, 0)
        layout_SPEED.addWidget(self.button_speed, 0, 1)
        layout_SPEED.addWidget(box_window, 1, 0, 1, 2)
        layout_SPEED.addWidget(box_artifact, 2, 0, 1, 2)
        layout_SPEED.addWidget(box_filtering, 3, 0, 1, 2)
        layout_SPEED.addWidget(box_resampling, 4, 0, 1, 2)
         


        

    
       # def showEvent(self, event):
        # QTimer.singleShot(10, self.initial_calculations)
