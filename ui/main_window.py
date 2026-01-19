from PyQt5.QtCore import Qt, QTimer, pyqtSignal,  QEvent, QPoint
from PyQt5.QtGui import QFont, QFontMetrics, QMouseEvent
from PyQt5.QtWidgets import (QWidget, QGridLayout, QLabel, qApp, QFrame, QHBoxLayout, QSizePolicy, 
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
import subprocess

from .settings_panel import SettingsPanel
from .processing_panel import ProcessingPanel
from .topo_teps_panel import TopoTEPsPanel
from .overview_panel import overviewPanel
from .meps_panel import MEPsPanel
from .video_player import StimuliPresentation_one_by_one
from .stimuli_window import StimuliCreation

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean
from utils.concat_videos import concat_videos_by_order
 
from logic.sources.stream import StreamSource
from logic.data_processor import DataProcessor

from settings.settings import Settings 
from settings.plot_settings import PlotSettings 

from settings.settings_handler import SettingsHandler
from settings.plot_settings_handler import PlotSettingsHandler

from logic.plot_updater import PlotUpdater

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

    def __init__(self, input_stream, resonance, filename_params):
        super().__init__()

        # == Параметры и структуры данных ==

        self._resonance = resonance                       # прокси для управления резонансными модулями

        with open(filename_params) as json_data:          # вгрузить настройки приложения
            self.params = json.load(json_data)  
        
        self.settings = Settings()                                                   # Хранилище настроек
        self.settings_plot = PlotSettings()                                        # Хранилище настроек для отрисовки графиков

        self._input_stream = StreamSource(input_stream)                              # Приёмник (онлайн) данных
        #self._load_data = FileSource()                                              # Приёмник загружаемых данных
        
        self._data_processor = DataProcessor(self.settings)                                       # Обработчик данных (эпох)
      

        self._settings_handler = SettingsHandler(self.settings, self._data_processor)                      # Обработчик настроек
        self._settings_handler_plots = PlotSettingsHandler(self.settings_plot)                      # Обработчик настроек
        
        self._init_state()                                # инициализация начального состояния переменных
        
        # == Визуальная часть интерфейса ==
        self._setup_ui()                                  # создание всех виджетов

        self._plot_updater = PlotUpdater(self._topo_teps_panel, self._overview_panel, self._meps_panel, self.settings_plot)

        self._setup_main_grid()                           # расположение виджетов на экране
        
        # == Взаимосвязи между элементами интерфейса ==
        self._setup_connections()                         
                
        # == Показать окно ==
        self._post_init()

    # --- Инициализация ---
    def _init_state(self):
        """Инициализирует начальное состояние"""
        # == Внешний вид окна == 
        self.setWindowTitle("TEP visualization")
        self.resize(WIDTH_SET, HEIGHT_SET)
        #self.setWindowIcon(QtGui.QIcon(r"./pictures/icon.png"))
    
        # self._session_loaded = []                              # список с подгруженными датасетами
        # self._session_loaded_labels = []                       # список с названиями подгруженных файлов (для легенды)

        self._record_in_progress = False                    # флаг идёт ли запись
        if self.settings.record.activate_bat:
            # Запуск батника с qml-файлом для управления резонансными модулями
            
            try:
                cwd = os.path.dirname(self.settings.record.bat_file) # cwd = папка с батником
                subprocess.Popen([self.settings.record,bat_file], cwd=cwd)
            except:
                cwd = os.path.dirname(self.settings.record,bat_file_home) # cwd = папка с батником
                subprocess.Popen([self.settings.record.bat_file_home], cwd=cwd)

        self._player_window = None


        # self.average_functions = []

        # self.aver_empty_func = {                                        # dict с функциями для усреднения
        #     "mean": lambda x, y, z: RollingMean(x, y, z), 
        #     "median": lambda x, y, z: RollingMedian(x, y, z), 
        #     "trimmean": lambda x, y, z: RollingTrimMean(x, y, z)
        # }
        # self.aver_method = self.settings.aver_methods[0]
        # self._n_aver_max = self.settings.n_aver
        # self._aver_all = self.settings.aver_all

        # self._transform = lambda x: x

        # self._specific_epoch = False                         # флаг для отслеживания режима показа определенной эпохи или стандартного
        
        self.SPEED = self.params['SPEED']
        self._ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])                                  # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])       # длина эпохи в сэмплах
        self._time_shift = self._ms_to_sample(0 - self.SPEED["window_start"])                             # смещение относительно нуля для графиков в сэпмлах

        # # --- создать и открыть файл для автоматической записи получаемых данных ---
        # cur_time = datetime.now().strftime("%Y.%m.%d_%H.%M")
        # self.autosave_file = h5py.File(os.path.join("data/autosave", f"{cur_time}.h5"), "w")
        # self._dset = self.autosave_file.create_dataset("epochs", (0, 66), maxshape=(None, 66), dtype='float32')  # для эпох (64 EEG + 2 EMG)
        # self._tset = self.autosave_file.create_dataset("timestamps", (0, ), maxshape=(None, ), dtype='int64')    # для таймстемпов резонанса (в нс)

    # --- UI: WIDGETS---
    def _setup_ui(self):
        """Создаёт все элементы интерфейса"""

        hor_ratio = self.params["layout"]["horizontal_ratios"]
        cen_ratio = self.params["layout"]["center_ratio"]

        self._settings_panel = SettingsPanel(parent=self,
                                             settings=self.settings,
                                             settings_handler=self._settings_handler,
                                             channels=self.settings.channels)
        
        self._processing_panel = ProcessingPanel(parent=self,
                                             settings=self.settings.processing_settings,
                                             settings_handler=self._settings_handler,
                                             channels=self.settings.channels)
        
        
        self._topo_teps_panel = TopoTEPsPanel(parent=self,
                                         settings=self.settings_plot.topo_teps, 
                                         speed_settings=self.settings.speed,
                                         settings_handler=self._settings_handler,
                                         processing_ui=self._processing_panel,
                                         init_size=[int(hor_ratio[1] * WIDTH_SET), int(cen_ratio*HEIGHT_SET)])
        
        self._meps_panel = MEPsPanel(parent=self,
                                    Fs=self.settings.speed.Fs,
                                    settings=self.settings_plot.single_meps,
                                    settings_dl=self.settings_plot.meps_deeper_look,
                                    init_size=[int(hor_ratio[1] * WIDTH_SET), int((1-cen_ratio)*HEIGHT_SET)])
        
        self._overview_panel = overviewPanel(parent=self,
                                         params=self.params["TEP_suppl_plot"], 
                                         init_size=[int(hor_ratio[2] * WIDTH_SET), HEIGHT_SET])
        
        
        
        
    # --- UI: Layout ---
    def _setup_main_grid(self):
        # Grid layout (all widgets in splitters):
        # +-------+-------------------------+---------+ 
        # | set.  |                         |  topo   |
        # |       |     topo TEPs           |         |
        # |       |                         |  TEPs   |
        # |       |                         |         |
        # |       +-------------------------+         |
        # |       |      MEP epochs         |  MEPs   |
        # |       |                         |         |
        # +-------+-------------------------+---------+

        ratio = self.params["layout"]["center_ratio"]
        splitter_center = QSplitter(Qt.Vertical, parent=self)        # позволяет изменять размер
        splitter_center.addWidget(self._topo_teps_panel)
        splitter_center.addWidget(self._meps_panel)
        splitter_center.setCollapsible(0, False)
        splitter_center.setOpaqueResize(False)
        splitter_center.setSizes([int(ratio*HEIGHT_SET), int((1-ratio)*HEIGHT_SET)])   # Можно задать начальные пропорции
        splitter_center.setStretchFactor(0, 7)
        splitter_center.setStretchFactor(1, 3) # растягивается в два раза сильнее
        splitter_center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.splitter = QSplitter(Qt.Horizontal, parent=self)        # позволяет изменять размер
        # splitter.addWidget(self._settings_panel)
        self.splitter.addWidget(self._settings_panel.scroll)
        self.splitter.addWidget(splitter_center)
        self.splitter.addWidget(self._overview_panel)
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



    # --- Connections ---
    def _setup_connections(self):
        self._settings_handler.setupUI(self._processing_panel, self._plot_updater)
        # self._settings_handler_plots.setupUI(self._plot_updater)

        self._input_stream.dataReady.connect(lambda epoch, ts: self._data_processor.add_epoch(epoch, ts))
        self._data_processor.newDataProcessed.connect(lambda: self._plot_updater.update_plots(self._data_processor))

        self._meps_panel.deeperLookActivate.connect(lambda: self._plot_updater.add_mep_deeper_look(self._meps_panel._deeper_look_window))

        # начальная замедленная инициализиация всех вычислений для уменьшения подтупливаний при запуске приложения
        # self.start_calc_signal.connect(self._initial_calculations)

        # работа с эпохами
        # self._settings_panel.combo_box_mode_data.currentIndexChanged[int].connect(self._on_change_mode_data)
        # self._settings_panel.button_save.clicked.connect(self._on_button_save_click)
        # self._settings_panel.button_load.clicked.connect(self._on_button_load_click)
        # self._settings_panel.button_restart.clicked.connect(self._on_restart_button_click)
        # self._settings_panel.button_remove_epoch.clicked.connect(self._on_remove_epoch_button_click)

        # работа с nvx
        # self._settings_panel.button_nvx_record.clicked.connect(self._on_record_button_click)

        # работа со стимулами
        self._settings_panel.button_create_stimuli.clicked.connect(self._on_create_stimuli_button_click)
        self._settings_panel.button_stimuli.clicked.connect(self._on_stimuli_button_click)
        self._settings_panel.button_stimuli_pause.clicked.connect(self._on_pause_stimuli_button_click)
        self._settings_panel.button_stimuli_restart.clicked.connect(self._on_restart_stimuli_presentation)

        # self._settings_panel.button_show_epoch.clicked.connect(self._on_show_epoch_button_click)
               
        # изменение масштаба для визуализации 
        for spin_box in self._overview_panel.spinbox_ts:
            spin_box.valueChanged.connect(self._update_topoplots)
        self._topo_teps_panel.scale_changed.connect(self._on_change_main_scale)

        # self._settings_panel.volume_slider.slider.valueChanged.connect(self._on_change_volume)
        self._settings_panel.volume_slider.valueChanged.connect(self._on_change_volume)
        

    # --- Логика ---

    # def _get_data(self, msg, timestamp):
    #     # если режим обработки новых данных
    #     if self._process_new_data:
    #         self._save_data(msg, timestamp)     # сохранить новые данные
            
    #         # self._n_epoch += 1                   # обновить счётчик количества эпох
    #         self._update_label_counter(self._n_epoch)

    #         # распаковать "сообщение" в формате {"TEPs": list of EEG data in microvolt} 
    #         # data = np.array(json.loads(msg)["TEPs"]).T  # [n_channels x n_samples]
            
    #         # data = np.array(msg).T          # [n_channels x n_samples], n_channels = EEG_channels + 2 EMG_channels

    #         # self._epochs.append(data)        # добавить в список хранимых эпох -> [n_epoch x n_channels x n_samples]
    #         # self._ts.append(timestamp)       # только для сохранения таймстемпов резонанса в файлы

    #         if self._average_data:                    # если режим усреднения, обновить функции усреднения
    #             TEPs = data[:-2, :] * 10**6           # выделить только TEPs и преобразовать в мкВ
    #             TEPs2plot = self._transform(TEPs)     # нужные преобразования -> [n_channels x n_samples]
    #             self._update_average_functions(TEPs2plot)

    #         self._update_plots()
    

    
    def _update_data(self):
        self._restart_plots()
        # если есть что нарисовать и режим отображения "новых данных"
        if self._n_epoch > 0 and self._process_new_data:
            self._update_plots()
        # если есть что нарисовать и режим отобраения "загруженных данных"
        if len(self._session_loaded) != 0 and not self._process_new_data:
            self._draw_loaded_data()

    # def _draw_loaded_data(self):
    #     TEPs_sessions = []
    #     MEPs_sessions = []
    #     for data in self._session_loaded:
    #         if self._average_data:
    #             self._create_average_functions(data)
    #             TEPs2plot = self._calculate_avg_TEP()         # -> [n_channels x n_samples]    units=[uV]
    #         else:
    #             TEPs = data[-1][:-2, :] * 1E6         # выделить только одну последнюю эпоху с TEPs и преобразовать в мкВ
    #             TEPs2plot = self._transform(TEPs)             # нужные преобразования -> [n_channels x n_samples]   units=[uV]
    #         TEPs_sessions.append(TEPs2plot)

    #         emg_epochs = data[:, -2:, :] * 1E3        # -> [n_epoch x 2 x n_samples]    units=[mV]
    #         emg_epochs = np.array([np.diff(self._baseline(emg), axis=0).flatten() for emg in emg_epochs])    # -> [n_epoch x 1 x n_samples]    
    #         emg = np.mean(emg_epochs, axis=0)         # усреднённые по эпохам [1 x n_samples]
    #         MEPs_sessions.append(emg)

    #     # отобразить TEPs на центральном графике в режиме сравнения
    #     self._topo_teps_panel.figure.draw_loaded_TEPs(TEPs_sessions, self._session_loaded_labels)

    #     # если загружен один файл
    #     if len(TEPs_sessions) == 1:
    #         self._overview_panel.figure_TEP.update_TEPs(TEPs_sessions[0])
    #         self._overview_panel.figure_MEP.update_MEPs(MEPs_sessions[0])

    #         if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
    #             timestamps = self.params["TEP_suppl_plot"]["timestamps_ms"]
    #             for i, t_ms in enumerate(timestamps):
    #                 t = self._ms_to_sample(t_ms)
    #                 self._overview_panel.figure_topo[i].plot_topomap(TEPs_sessions[0][:, t])
                    
    #         self._update_label_counter(self._session_loaded[0].shape[0])

    #     else:   # если загружено несколько файлов
    #         self._overview_panel.figure_TEP.draw_loaded_multiple_sessions(TEPs_sessions, signal="TEP")
    #         self._overview_panel.figure_MEP.draw_loaded_multiple_sessions(MEPs_sessions, signal="MEP")

    #         self._update_label_counter("")

    # def _save_data(self, epoch, ts):
    #     n = self._dset.shape[0]
    #     self._dset.resize(n + epoch.shape[0], axis=0)
    #     self._dset[n:] = epoch
 
    #     self._tset.resize(self._tset.shape[0] + 1, axis=0)
    #     self._tset[-1] = ts

    # def _on_button_save_click(self):
    #     # открытие диалога для выбора названия и места хранения файла
    #     file_path, _ = QFileDialog.getSaveFileName(
    #         self,
    #         "Задайте имя файла",
    #         "data/exports",
    #         "HDF5 Files (*.h5);;All Files (*)"
    #     )

    #      # пользователь нажал Cancel
    #     if not file_path:
    #         print("---> Сохранение отменено")
    #         return None 
        
    #     data2save = np.array(self._epochs[:]).transpose(0, 2, 1).reshape(-1, 66)      # (n_samples, n_channels)
    #     ts2save = np.array(self._ts)
    #     # если выбран файл
    #     with h5py.File(file_path, "w") as h5f:
    #         data = h5f.create_dataset("epochs", data=data2save, dtype='float32')      # для эпох (64 EEG + 2 EMG)
    #         data.attrs["Fs"] = self.SPEED["Fs"]
    #         data.attrs["n_samples"] = self._n_samples
    #         data.attrs["n_epochs"] = len(self._epochs)
            
    #         tdata = h5f.create_dataset("timestamps", data=ts2save, dtype='int64')      # для таймстемпов резонанса (в нс)
    #         tdata.attrs["units"] = "ns"

    # def _on_button_load_click(self):
    #     # очистить стек подгруженных данных
    #     self._session_loaded = []
    #     self._session_loaded_labels = []

    #     # открыть диалог для выбора файла/файлов
    #     paths, _ = QFileDialog.getOpenFileNames(
    #         self,
    #         "Выберите файлы",
    #         "data/exports",                     # стартовая директория
    #         "HDF5 (*.h5 *.hdf5);;Все файлы (*)"
    #     )
        
    #     # пользователь нажал Cancel
    #     if not paths:
    #         print("---> Подгрузка файлов отменена")
    #         return None  
        
    #     # если выбран файл/файлы - загрузить в память данные
    #     for file_path in paths:
    #         with h5py.File(file_path, "r") as h5f:
    #             stream = h5f['epochs'][:]
    #             n_epochs = h5f['epochs'].attrs["n_epochs"]
    #             n_samples = h5f['epochs'].attrs["n_samples"]

    #             epochs =  stream.reshape((n_epochs, n_samples, stream.shape[1])).transpose(0, 2, 1) # -> [n_epochs, n_channels, n_samples]
    #             self._session_loaded.append(epochs)

    #             name = os.path.splitext(os.path.basename(file_path))[0] # имя файла без разрешения
    #             self._session_loaded_labels.append(name)

    #             print(f"> {name} : n_epoch = {n_epochs} <")
        
    #     # self._update_label_counter(self._n_epoch)
    #     self._draw_loaded_data()

    # def _on_restart_button_click(self):
        # self._n_epoch = 0
        # self._update_label_counter(0)

        # self._epochs = []
        # self._ts = []
        # self._create_average_functions()

        # self._restart_plots()
    
    def _on_record_button_click(self):
        
        if not self._record_in_progress:    # если запись не была начата
            print("start nvx record")
            self._record_in_progress = True
            
            self._service = self._resonance.getService(self.params["record"]["service_name"])     # Берем сервис
            self._service.sendTransition('start')

            self._topo_teps_panel.label_record.setText("🔴REC")
            self._settings_panel.button_nvx_record.setText("Остановить")
        else:                               # если запись уже идёт
            print("finish nvx record")
            self._record_in_progress = False

            self._service.sendTransition('stop')

            self._topo_teps_panel.label_record.setText("")
            self._settings_panel.button_nvx_record.setText("Начать запись")

    def _change_button_pause_stimuli_text(self):
        status = "▶" if self._player_window.is_paused else "⏸"
        self._settings_panel.button_stimuli_pause.setText(status)

    def _on_pause_stimuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.pause_video()
            self._change_button_pause_stimuli_text()
        
    def _on_restart_stimuli_presentation(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.restart_sequence()
            self._settings_panel.button_stimuli_pause.setEnabled(True)

    def _on_finish_stimuli(self):
        if self._record_in_progress:
            self._on_record_button_click()
        
        self._settings_panel.label_stimuli_idx.setText(f"")
    
    def _on_start_stimuli(self):
        if self._settings_panel.check_box_stimuli_record.isChecked():
            self._on_record_button_click()  # начать запись
        self._settings_panel.button_stimuli_pause.setText("⏸")

    def _on_create_stimuli_button_click(self):
        self._create_stimuli_window = StimuliCreation()
        self._create_stimuli_window.show()
    
    def _on_stimuli_idx_changed(self, idx):
        self._settings_panel.label_stimuli_idx.setText(f"#{idx}")

    def _on_stimuli_button_click(self):
        # если стимул-презентейшн уже открыт -> хотим закрыть
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._settings_panel.button_stimuli.setText("Запуск")               # опять можно начать презентацию
            self._settings_panel.button_stimuli_restart.setEnabled(False)       # опять нельзя начать заново
            self._player_window.finish()                                        # like Escape
        # если не открыт -> хотим начать презентацию и возможно запись нвх
        else:
            

            seq_name = self._settings_panel.combo_box_stimuli.currentText()
            if not seq_name:
                return

            try:
                with open(self.params["stimuli"]["stimuli_filename"], "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}

            sequence = data.get(seq_name)

            n_monitor = self._settings_panel.spin_box_monitor.value()
            volume = self._settings_panel.volume_slider.slider.value()
            self._player_window = StimuliPresentation_one_by_one(sequence, n_monitor, volume=volume)

            self._player_window.show()
            self._player_window.raise_()

            
            self._player_window.stimuliStarted.connect(self._on_start_stimuli)
            self._player_window.stimuliPaused.connect(self._change_button_pause_stimuli_text)
            self._player_window.stimuliFinished.connect(self._on_finish_stimuli)                     # !!! настроить чтобы это было в коннекшенс остальных
            
            self._player_window.currIdxChanged.connect(self._on_stimuli_idx_changed)

            # self._player_window.activateWindow()
            self._player_window.volumeChanged.connect(self._on_player_volume_changed)
            self._player_window.playerIsMuted.connect(self._on_player_muted)

            # меняем кнопки
            self._settings_panel.button_stimuli_restart.setEnabled(True)        # можно начать заново
            self._settings_panel.button_stimuli_pause.setEnabled(True)

            self._settings_panel.button_stimuli.setText("Завершить")

    def _on_player_volume_changed(self, value):
        self._settings_panel.volume_slider.slider.setValue(value)
    
    def _on_player_muted(self):
        cur_volume = self._settings_panel.volume_slider.slider.value()
        if cur_volume == 0:
            volume = self._player_window.get_last_volume()
        else:
            volume = 0
        self._settings_panel.volume_slider.slider.setValue(volume)

    def _on_change_volume(self, value):
        # changes from slider
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.update_volume(value)


    # def _on_show_epoch_button_click(self):
    #     if self._specific_epoch: # если был режим показа отдельной эпохи - вернуться к стандартному отображению
    #         self._update_data()
    #         self._settings_panel.button_show_epoch.setText("Показать эпоху")
    #     else:                   # если не был включён режим показа отдельной эпохи - показать её
    #         n_show = self._settings_panel.spin_box_show_epoch.value()    # номер эпохи для просмотра
    #         data = self._transform(np.array(self._epochs[n_show-1])[:-2, :])
    #         self._update_plots(data)
    #         self._settings_panel.button_show_epoch.setText("Стандартный режим")
            
    #     self._specific_epoch = not self._specific_epoch

    # def _on_remove_epoch_button_click(self):  
    #     self._n_epoch -= 1
    #     self._update_label_counter(self._n_epoch)

    #     n_delete = self._settings_panel.spin_box_remove_epoch.value()    # номер эпохи для удаления 

    #     del self._epochs[n_delete-1]                     # минус один для учёта нумерации с нуля
    #     del self._ts[n_delete-1]
        
    #     self._update_data()

    # def _on_update_averaging_signal(self):
    #     """применение настроек для усреднения эпох"""
    #     if self._average_data and self._process_new_data:         # если режим усреднения
    #         data = self._epochs if self._n_epoch > 0 else None
    #         self._create_average_functions(data)            # создать новые функции

    #     self._update_data()                     # отобразить изменения

    # def _on_update_baseline_signal(self):
    #     apply_baseline = self._settings_panel.check_box_baseline.isChecked()   # вычитать ли бейзлайн
    #     if apply_baseline:
    #         baseline_from = self._settings_panel.spin_box_baseline_from.value()
    #         baseline_to  = self._settings_panel.spin_box_baseline_to.value()
    #         ind_from = self._ms_to_sample(baseline_from - self.SPEED["window_start"])
    #         ind_to = ind_from + self._ms_to_sample(baseline_to - baseline_from) + 1
    #         mean_function = self._settings_panel.combo_box_baseline.currentText()
    #         func = (lambda x: np.mean(x, axis=1)) if mean_function == 'mean' else (lambda x: np.median(x, axis=1))
    #         calculate_baseline = lambda x: func(x[:, ind_from:ind_to]).reshape((-1, 1))
        
    #     self._baseline = (lambda x: x - calculate_baseline(x)) if apply_baseline else (lambda x: x)
    #     # если усреднять и уже есть данные - создать новые функции
    #     if self._average_data and self._n_epoch > 0 and self._process_new_data:  
    #         self._create_average_functions(self._epochs)
        
    #     self._update_data()         # отобразить изменения
    
    # def _on_update_lowpass_signal(self):
    #     apply_filter = self._settings_panel.check_box_lowpass.isChecked()
    #     if apply_filter:
    #         f = self._settings_panel.spin_box_lowpass.value()
    #         sos_lowpass = signal.butter(2, f/self.SPEED["Fs"]*2, btype='lowpass', output='sos')
    #     self._lowpass_filter = (lambda x: signal.sosfilt(sos_lowpass, x, axis=0)) if apply_filter else (lambda x: x)    
    #     # если усреднять и уже есть данные - создать новые функции
    #     if self._average_data and self._n_epoch > 0 and self._process_new_data:  
    #         self._create_average_functions(self._epochs)
        
    #     self._update_data()         # отобразить изменения

    # def _on_update_rereference_signal(self):
    #     apply_reref = self._settings_panel.check_box_rereference.isChecked()
    #     reref_channel = self._settings_panel.combo_box_rereference.checkedItems()[0] # канал для ререферентации
    #     idx = np.where(CHANNELS == reref_channel)[0][0] # индекс канала для ререферентации

    #     n_channels = len(CHANNELS)  
    #     e_r = np.zeros((n_channels, 1)); 
    #     e_r[idx, 0] = 1.0
    #     R = np.eye(n_channels) - np.ones((n_channels, 1)) @ e_r.T

    #     self._referef = (lambda x: R @ x) if apply_reref else (lambda x: x)
    #     # если усреднять и уже есть данные - создать новые функции
    #     if self._average_data and self._n_epoch > 0 and self._process_new_data:  
    #         self._create_average_functions(self._epochs)
        
    #     self._update_data()         # отобразить изменения

    # def _on_update_CAR_signal(self):
    #     apply_CAR = self._settings_panel.check_box_car.isChecked()   # применять ли CAR
    #     if apply_CAR: 
    #         CAR_channels = self._settings_panel.combo_box_channels.checkedItems()
    #         n_sel = len(CAR_channels)
    #         if n_sel == 0:
    #             raise ValueError("Не отмечены каналы для построения CAR фильтра.")
    #         is_selected = np.array([ch in CAR_channels for ch in CHANNELS])
    #         n_channels = len(CHANNELS)
    #         W = np.eye(n_channels) - (1/n_sel) * np.outer(np.ones(n_channels), is_selected.astype(float)) # матрица фильтра CAR                 
    #     self._CAR = (lambda x: W @ x) if apply_CAR else (lambda x: x)           # функция для вычисления CAR
    #     # если усреднять и уже есть данные - создать новые функции
    #     if self._average_data and self._n_epoch > 0 and self._process_new_data:  
    #         self._create_average_functions(self._epochs)
        
    #     self._update_data()         # отобразить изменения

    # def _create_full_transform(self):
    #     self._transform = lambda x: self._referef(
    #         self._CAR(
    #             self._baseline(
    #                 self._lowpass_filter(
    #                     x
    #                     )
    #                 )
    #             )
    #         )

    # def _create_average_functions(self, new_data=None):
    #         """Создать функции для усреднения TEPs"""
    #         function = self.aver_empty_func[self.aver_method]   # пустой трафарет
    #         if new_data is not None:
    #             data = np.array([self._transform(np.array(TEPs[:-2, :], dtype=float) * 1E6) for TEPs in new_data])
    #             self.average_functions = [
    #                 [function(data[:, i, j], self._n_aver_max, self._aver_all)
    #                 for j in range(self._n_samples)]
    #                 for i in range(len(CHANNELS))
    #             ]
    #         else:
    #             self.average_functions = [
    #                 [function([], self._n_aver_max, self._aver_all)
    #                 for _ in range(self._n_samples)]
    #                 for _ in range(len(CHANNELS))
    #             ]

    # def _on_change_mode(self, idx):
    #     self._average_data = True if idx == 0 else False      # из  ["Усреднение", "Одиночные пробы"]
    #     if self._average_data:
    #         self._create_average_functions()    # обновить функции усреднения
    #     self._update_data() # отобразить изменения

    # def _on_change_mode_data(self, idx):        
    #     self._process_new_data = True if idx == 0 else False  # из ["Новые данные", "Сравнение"]

    #     self._session_loaded = []                              # список с подгруженными датасетами
    #     self._session_loaded_labels = []                       # список с названиями подгруженных файлов (для легенды)

    #     if self._average_data:
    #         data = self._epochs if self._process_new_data and self._n_epoch > 0 else None
    #         self._create_average_functions(data)    # обновить функции усреднения

    #     self._update_data()                         # отобразить изменения

    # def _restart_plots(self):
    #     self._topo_teps_panel.figure.refresh_plot()
    #     self._overview_panel.figure_TEP.refresh_plot()
    #     self._overview_panel.figure_MEP.refresh_plot()
        # TO BE ADDED:  mep plot refresh
        # TO BE ADDED:  topoplot refresh
    
    def _on_change_main_scale(self):
        ymax = self._topo_teps_panel.spin_box_scale_ymax.value()
        ymin = self._topo_teps_panel.spin_box_scale_ymin.value()

        xmin_ms = self._topo_teps_panel.spin_box_scale_xmin.value()
        xmax_ms = self._topo_teps_panel.spin_box_scale_xmax.value()

        self._overview_panel.figure_TEP.draw_rectangle(xmin_ms, xmax_ms, ymin, ymax)

    def _initial_calculations(self):
        t0 = time.perf_counter()

        self._on_update_CAR_signal()
        self._on_update_baseline_signal()
        self._on_update_lowpass_signal()
        self._on_update_rereference_signal()
        self._on_update_averaging_signal()

        self._create_full_transform()

        

        t5 = time.perf_counter()
        print(f"все предварительные рассчёты: {t5 - t0:.6f} сек")
    
    def _update_label_counter(self, n_epoch):
        self._topo_teps_panel.label_n_epoch.setText('Количество эпох: {}'.format(n_epoch))
        qApp.processEvents()    # для обновления отображения в Qt-приложении

        # если эпохи есть, то разрешить их очистку из памяти по нажатию кнопки 
        
        active_status = True if self._n_epoch > 0 else False      
        self._settings_panel.button_restart.setEnabled(active_status)
        # self._settings_panel.shortcut_restart.setEnabled(active_status)
        self._settings_panel.button_remove_epoch.setEnabled(active_status)
        #self.shortcut_remove_epoch.setEnabled(True)
        self._settings_panel.button_show_epoch.setEnabled(active_status)
        self._settings_panel.button_save.setEnabled(active_status)
        
        self._settings_panel.spin_box_show_epoch.setMaximum(self._n_epoch)
        self._settings_panel.spin_box_show_epoch.setValue(self._n_epoch)
        self._settings_panel.spin_box_remove_epoch.setMaximum(self._n_epoch)
        self._settings_panel.spin_box_remove_epoch.setValue(self._n_epoch)

    def _update_topoplots(self):
        plot = False
        if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
            if self._process_new_data:
                plot = (len(self._epochs) != 0)
                if not self._average_data:
                    data2plot = self._transform(self._epochs[-1, :-2]*10**6)
                else:
                    data_aver = []
                    for i in range(len(CHANNELS)):
                        average_TEPs = np.array([f.calculate() for f in self.average_functions[i]])  # усреднённые TEPs
                        data_aver.append(average_TEPs)
                    data2plot = np.array(data_aver)
            else:
                
                function = self.aver_empty_func[self.aver_method]
                data2plot = []
                plot = (len(self._data_loaded) != 0)
                for data_raw in self._data_loaded:
                    if not self._average_data:
                        data2plot.append(self._transform(data_raw[-1, :-2]*10**6))     # последняя эпоха
                    else:
                        data = np.array([self._transform(np.array(TEPs[:-2, :]*10**6, dtype=float)) for TEPs in data_raw])
                        data_aver = []

                        for i in range(len(CHANNELS)):
                            average_functions = [function(data[:, i, j], self.n_aver_max, self.aver_all)
                                for j in range(self._n_samples)
                            ]
                            average_TEPs = np.array([f.calculate() for f in average_functions])  # усреднённые TEPs
                            data_aver.append(average_TEPs)
                        data2plot.append(np.array(data_aver))
        if plot:
            for i in range(3):
                ts = self._overview_panel.spinbox_ts[i].value()
                t = self._ms_to_sample(ts)
                print(t, ts)
                
                self._overview_panel.figure_topo[i].plot_topomap(data2plot[0][:, t])

    # --- Финализация ---
    def _post_init(self):
        self._overview_panel.figure_TEP.set_x_shift(-self._time_shift, self._n_samples, signal="TEP")
        self._overview_panel.figure_MEP.set_x_shift(-self._time_shift, self._n_samples, signal="MEP")

        self._on_change_main_scale()

        # self.setWindowTitle("Demo App")
        # self.resize(400, 200)
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

            topoplots = self._overview_panel.figure_topo
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
            
            suppl_tep_plot = self._overview_panel.figure_TEP
            local_pos = suppl_tep_plot.mapFromGlobal(global_pos)
            if suppl_tep_plot.geometry().contains(suppl_tep_plot.mapFromGlobal(global_pos)):
                new_event = QMouseEvent(
                    event.type(), local_pos, global_pos,
                    event.button(), event.buttons(), event.modifiers()
                )
                QApplication.sendEvent(suppl_tep_plot, new_event)
                return True  # блокируем обработку splitter'ом

        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        try:
            n = self._tset.shape[0]
            file_path = self.autosave_file.filename
            self.autosave_file.close()
            if n == 0:      # удалить, если ничего не было сохранено
                os.remove(file_path)
            print("---> Autofile закрыт корректно.")
        except Exception as e:
            print(f"---> Ошибка закрытия autofile: {e}")

        if self.params["record"]["activate_bat"]:
            service = self._resonance.getService("Resonance-control")     # Берем сервис
            service.sendTransition('!terminate')
        event.accept()


    # --- неприкаянные функции ---
    

    
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

        self._ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])       # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])    # длина эпохи в сэмплах
        self._time_shift = self._ms_to_sample(0 - self.SPEED["window_start"])    # смещение относительно нуля для графиков в сэпмлах

        with open(self.params["SPEED_settings_path"], 'w') as f:
            json.dump(self.SPEED, f)
    
    

