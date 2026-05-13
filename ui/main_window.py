from PyQt5.QtCore import Qt, QTimer, pyqtSignal,  QEvent
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtGui import  QMouseEvent
from PyQt5.QtWidgets import QWidget, qApp, QSizePolicy, QSplitter, QApplication, QHBoxLayout, QFileDialog, QMessageBox
                             
import numpy as np
import pandas as pd

import os
import json
import time
import h5py

from ui import (SettingsPanel, ProcessingPanel, NVXControlPanel, StimuliControlPanel, SurveyPanel,
                TopoTEPsPanel, overviewPanel, MEPsPanel)
 
from logic.sources.stream import StreamSource
from logic.data_processor import DataProcessor
from logic.epoch_record_buffer import EpochRecordBuffer
from ui.widgets.mep_condition_analysis_window import MEPConditionAnalysisWindow
from ui.widgets.mep_movement_detection_window import MEPMovementDetectionWindow

from settings.settings import Settings 
from settings.plot_settings import PlotSettings 

from settings.settings_handler import SettingsHandler
from settings.plot_settings_handler import PlotSettingsHandler
from settings.record_settings_handler import RecordSettingsHandler

from logic.plot_updater import PlotUpdater

from utils.widget_placement import place_widget

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

    def __init__(self, input_stream, resonance, output_stream, filename_params):
        super().__init__()

        place_widget(self, monitor=1, coordinates=(50, 50))

        # == Параметры и структуры данных ==

        self._resonance = resonance                       # прокси для управления резонансными модулями
        self._output_stream = output_stream

        with open(filename_params) as json_data:          # вгрузить настройки приложения
            self.params = json.load(json_data)  
        
        self.settings = Settings()                                                   # Хранилище настроек
        self.settings_plot = PlotSettings()                                        # Хранилище настроек для отрисовки графиков

        self._input_stream = StreamSource(input_stream)                              # Приёмник (онлайн) данных
        #self._load_data = FileSource()                                              # Приёмник загружаемых данных
        
        self._data_processor = DataProcessor(self.settings)                                       # Обработчик данных (эпох)
        self._epoch_record_buffer = EpochRecordBuffer(self.settings.speed)
      
        self._settings_handler = SettingsHandler(self.settings, self._data_processor)                      # Обработчик настроек
        
        self._settings_handler_plots = PlotSettingsHandler(self.settings_plot)                      # Обработчик настроек
        # self._settings_handler_nvx = NVXSettingsHandler(self.settings.nvx_control)                      # Обработчик настроек
        
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
        """Инициализирует начальное состояние переменных"""

        self._session_loaded = []                              # список с подгруженными датасетами
        self._session_loaded_labels = []                       # список с названиями подгруженных файлов (для легенды)
        self._mep_movement_detection_window = None
        self._mep_condition_analysis_window = None

        # отображение эпох
        self._specific_epoch = False                         # флаг для отслеживания режима показа определенной эпохи или стандартного
        
        self.SPEED = self.params['SPEED']
        self._ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])                                  # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])       # длина эпохи в сэмплах
        self._time_shift = self._ms_to_sample(0 - self.SPEED["window_start"])                             # смещение относительно нуля для графиков в сэпмлах

        hor_ratio = self.settings.layout.horizontal_ratios
        cen_ratio = self.settings.layout.center_ratio

        self._center_plots_width = int(hor_ratio[1] * WIDTH_SET)
        self._center_plots_height = int(cen_ratio*HEIGHT_SET)
        self._center_meps_height = int((1-cen_ratio)*HEIGHT_SET)

        self._right_panel_width = int(hor_ratio[2] * WIDTH_SET)
        self._left_panel_width = int(hor_ratio[0] * WIDTH_SET)

        

    # --- UI: WIDGETS---
    def _setup_ui(self):
        """Создаёт все элементы интерфейса"""

        self._nvx_control_panel = NVXControlPanel(parent=self,
                                                settings=self.settings.nvx_control,
                                                resonance=self._resonance)
    
        self._stimuli_control_panel = StimuliControlPanel(parent=self,
                                                settings=self.settings.stimuli_control,
                                                output_stream=self._output_stream)

        self._survey_panel = SurveyPanel(
            parent=self,
            participant_id_getter=lambda: self._nvx_control_panel.lineedit_subject.text()
        )

        self._settings_panel = SettingsPanel(parent=self,
                                             settings=self.settings,
                                             settings_handler=self._settings_handler,
                                             channels=self.settings.channels,
                                             control_nvx_panel=self._nvx_control_panel,
                                             control_stimuli_panel=self._stimuli_control_panel,
                                             survey_panel=self._survey_panel)
        
        self._processing_panel = ProcessingPanel(parent=self,
                                             settings=self.settings.processing_settings,
                                             settings_handler=self._settings_handler,
                                             channels=self.settings.channels)
        
        
        self._topo_teps_panel = TopoTEPsPanel(parent=self,
                                         settings=self.settings_plot.topo_teps, 
                                         speed_settings=self.settings.speed,
                                         settings_handler=self._settings_handler,
                                         processing_ui=self._processing_panel,
                                         init_size=[self._center_plots_width, self._center_plots_height])
        
        self._meps_panel = MEPsPanel(parent=self,
                                    Fs=self.settings.speed.Fs,
                                    settings=self.settings_plot.single_meps,
                                    settings_dl=self.settings_plot.meps_deeper_look,
                                    init_size=[self._center_plots_width, self._center_meps_height])
        
        self._overview_panel = overviewPanel(parent=self,
                                         settings=self.settings_plot.overview_panel, 
                                         Fs=self.settings.speed.Fs,
                                         init_size=[self._right_panel_width, HEIGHT_SET])
         
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

        # === центральная часть - вертикальный === 

        splitter_center = QSplitter(Qt.Vertical, parent=self)        

        splitter_center.addWidget(self._topo_teps_panel)
        splitter_center.addWidget(self._meps_panel)

        splitter_center.setCollapsible(0, False)
        splitter_center.setOpaqueResize(False)

        splitter_center.setSizes([self._center_plots_height, self._center_meps_height])   # Можно задать начальные пропорции
        splitter_center.setStretchFactor(0, 7)
        splitter_center.setStretchFactor(1, 3) 

        splitter_center.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._overview_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._settings_panel.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # === основной - горизонтальный === 

        self.splitter = QSplitter(Qt.Horizontal, parent=self)       

        self.splitter.addWidget(self._settings_panel.scroll)
        self.splitter.addWidget(splitter_center)
        self.splitter.addWidget(self._overview_panel)

        self.splitter.setCollapsible(0, False)
        self.splitter.setOpaqueResize(False)
        
        self.splitter.setSizes([self._left_panel_width, self._center_plots_width, self._right_panel_width])   
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1) # растягивается в два раза сильнее
        self.splitter.setStretchFactor(2, 1)
        
        self.splitter.setGeometry(0, 0, WIDTH_SET, HEIGHT_SET)  #  вручную задаём положение и размер

        # фильтр событий на splitter
        self.splitter.installEventFilter(self)

    # --- Connections ---
    def _setup_connections(self):
        # работа с потоками данных
        self._input_stream.dataReady.connect(self._epoch_record_buffer.add_epoch)
        self._input_stream.dataReady.connect(lambda epoch, ts: self._data_processor.add_epoch(epoch, ts))
        self._data_processor.newDataProcessed.connect(lambda: self._plot_updater.update_plots(self._data_processor))

        # отрисовка изменений в количестве эпох
        self._data_processor.updateCounter.connect(lambda n: self._update_label_counter(n))

        # подключение окна MEPDeeperLook
        self._meps_panel.deeperLookActivate.connect(lambda: self._plot_updater.add_mep_deeper_look(self._meps_panel._deeper_look_window))
        self._meps_panel.movementDetectionActivate.connect(self._on_mep_movement_detection_button_click)
        self._meps_panel.conditionAnalysisActivate.connect(self._on_mep_condition_analysis_button_click)

        # начальная замедленная инициализиация всех вычислений для уменьшения подтупливаний при запуске приложения
        # self.start_calc_signal.connect(self._initial_calculations)

        # работа с эпохами
        # self._settings_panel.combo_box_mode_data.currentIndexChanged[int].connect(self._on_change_mode_data)
        self._settings_panel.button_save.clicked.connect(self._on_button_save_click)
        # self._settings_panel.button_load.clicked.connect(self._on_button_load_click)
        self._settings_panel.button_restart.clicked.connect(self._on_restart_button_click)
        self._settings_panel.button_remove_epoch.clicked.connect(self._on_remove_epoch_button_click)
        self._settings_panel.button_show_epoch.clicked.connect(self._on_show_epoch_button_click)

        # сигнал для обновления состояния надписи REC в центральных графиках
        self._nvx_control_panel.recording.connect(self._on_recording_status_changed_signal)
        self._nvx_control_panel.recordingFileChanged.connect(self._on_nvx_recording_file_changed)

        # сигнал для управления записью nvx одновременно с показом стимулов
        self._stimuli_control_panel.stimuliPresentation.connect(self._on_stimuli_presenation_status_changed_signal)
                      
        # изменение масштаба для визуализации 
        for spin_box in self._overview_panel.spinbox_ts:
            spin_box.valueChanged.connect(self._update_topoplots)
        self._topo_teps_panel.scale_changed.connect(self._on_change_main_scale)

    def _on_stimuli_presenation_status_changed_signal(self, presentation_status):
        """связь между показом стимулов и записью nvx"""
        self._nvx_control_panel.change_record_status(stimuli=True)
        if not presentation_status:
            self._nvx_control_panel.update_next_record_number()

    def _on_nvx_recording_file_changed(self, recording_status, record_path):
        if recording_status:
            self._epoch_record_buffer.start(record_path)
            return

        try:
            saved_path = self._epoch_record_buffer.stop_and_save()
            if saved_path:
                print(f"Saved TEP epochs to {saved_path}")
        except Exception as exc:
            print(f"Could not save TEP epochs to {record_path}: {exc}")

    def _on_mep_movement_detection_button_click(self):
        epoch_record_path = self._epoch_record_path_from_record_line()
        if not os.path.exists(epoch_record_path):
            QMessageBox.information(self, "MEP delays", f"Файл эпох не найден:\n{epoch_record_path}")
            print("No saved epoch file for MEP movement detection")
            return

        if (
            self._mep_movement_detection_window is not None
            and self._mep_movement_detection_window.isVisible()
        ):
            if self._mep_movement_detection_window.epoch_path == epoch_record_path:
                self._mep_movement_detection_window.raise_()
                self._mep_movement_detection_window.activateWindow()
                return
            self._mep_movement_detection_window.close()

        self._mep_movement_detection_window = MEPMovementDetectionWindow(
            epoch_record_path,
            parent=None,
        )
        self._mep_movement_detection_window.show()
        self._mep_movement_detection_window.raise_()

    def _epoch_record_path_from_record_line(self):
        filename = self._nvx_control_panel.lineedit_record.text().strip()
        if not filename:
            return os.path.join("data", "records", "rec.hdf5")
        if os.path.isabs(filename):
            return filename
        return os.path.join("data", "records", filename)

    def _on_mep_condition_analysis_button_click(self):
        epoch_record_path = self._epoch_record_path_from_record_line()
        if not os.path.exists(epoch_record_path):
            QMessageBox.information(self, "MEP conditions", f"Файл эпох не найден:\n{epoch_record_path}")
            print("No saved epoch file for MEP condition analysis")
            return

        stimuli_filename = getattr(self.settings.stimuli_control, "stimuli_filename", "resources/saved_stimuli.json")
        if (
            self._mep_condition_analysis_window is not None
            and self._mep_condition_analysis_window.isVisible()
        ):
            if self._mep_condition_analysis_window.epoch_path == epoch_record_path:
                self._mep_condition_analysis_window.raise_()
                self._mep_condition_analysis_window.activateWindow()
                return
            self._mep_condition_analysis_window.close()

        self._mep_condition_analysis_window = MEPConditionAnalysisWindow(
            epoch_record_path,
            stimuli_filename=stimuli_filename,
            parent=None,
        )
        self._mep_condition_analysis_window.show()
        self._mep_condition_analysis_window.raise_()

    # --- Логика ---
    
    # === работа с эпохами === 
    def _on_restart_button_click(self):
        """обновить все графики и удалить всё из памяти"""
        self._data_processor.reset_sessions()
        self._plot_updater.clear_plots()

    def _on_show_epoch_button_click(self):
        if self._specific_epoch: # если был режим показа отдельной эпохи - вернуться к стандартному отображению
            self._plot_updater.set_show_epoch_mode(not self._specific_epoch)
            """отрисовать заново графики"""
            self._plot_updater.update_topoteps(self._data_processor)
            self._plot_updater.update_avg_teps(self._data_processor)
            self._plot_updater.update_avg_meps(self._data_processor)

            self._settings_panel.button_show_epoch.setText("Показать эпоху")
            self._add_specific_epoch_on_label(None)
        else:                   # если не был включён режим показа отдельной эпохи - показать её
            self._plot_updater.set_show_epoch_mode(not self._specific_epoch)
            n_show = self._settings_panel.spin_box_show_epoch.value()    # номер эпохи для просмотра
            self._plot_updater.plot_epoch(n_show, self._data_processor)
            
            self._settings_panel.button_show_epoch.setText("Стандартный режим")
            self._add_specific_epoch_on_label(n_show)
        
        self._specific_epoch = not self._specific_epoch
        

    def _on_remove_epoch_button_click(self):
        n_delete = self._settings_panel.spin_box_remove_epoch.value()    # номер эпохи для удаления 
        if n_delete == 1:
            self._on_restart_button_click()
        else:
            self._data_processor.delete_epoch(n_delete)
        

    # === обновление надписей на центральных графиках === 
    def _on_recording_status_changed_signal(self, recording_status):
        status_label = "🔴REC" if recording_status else ""
        self._topo_teps_panel.label_record.setText(status_label)
    
    def _update_label_counter(self, n_epoch):
        self._topo_teps_panel.label_n_epoch.setText('Количество эпох: {}. '.format(n_epoch))
        
        qApp.processEvents()    # для обновления отображения в Qt-приложении

        # если эпохи есть, то разрешить их очистку из памяти по нажатию кнопки 
        
        active_status = True if n_epoch > 0 else False      
        self._settings_panel.button_restart.setEnabled(active_status)
        # self._settings_panel.shortcut_restart.setEnabled(active_status)
        self._settings_panel.button_remove_epoch.setEnabled(active_status)
        #self.shortcut_remove_epoch.setEnabled(True)
        self._settings_panel.button_show_epoch.setEnabled(active_status)
        self._settings_panel.button_save.setEnabled(active_status)
        
        self._settings_panel.spin_box_show_epoch.setMaximum(n_epoch)
        self._settings_panel.spin_box_show_epoch.setValue(n_epoch)
        self._settings_panel.spin_box_remove_epoch.setMaximum(n_epoch)
        self._settings_panel.spin_box_remove_epoch.setValue(n_epoch)

    def _add_specific_epoch_on_label(self, n_epoch):
        new_label = f"Показана эпоха #{n_epoch}." if n_epoch is not None else ""
        self._topo_teps_panel.label_n_epoch_specific.setText(new_label)
        qApp.processEvents()    # для обновления отображения в Qt-приложении
    
    # def _update_data(self):
    #     self._restart_plots()
    #     # если есть что нарисовать и режим отображения "новых данных"
    #     if self._n_epoch > 0 and self._process_new_data:
    #         self._update_plots()
    #     # если есть что нарисовать и режим отобраения "загруженных данных"
    #     if len(self._session_loaded) != 0 and not self._process_new_data:
    #         self._draw_loaded_data()

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
        
        data2save = np.array(self._data_processor._epochs[:]).transpose(0, 2, 1).reshape(-1, 66)      # (n_samples, n_channels)
        ts2save = np.array(self._data_processor._timestamps)
        # если выбран файл
        with h5py.File(file_path, "w") as h5f:
            data = h5f.create_dataset("epochs", data=data2save, dtype='float32')      # для эпох (64 EEG + 2 EMG)
            data.attrs["Fs"] = self.SPEED["Fs"]
            data.attrs["n_samples"] = self._n_samples
            data.attrs["n_epochs"] = len(self._data_processor._epochs)
            
            tdata = h5f.create_dataset("timestamps", data=ts2save, dtype='int64')      # для таймстемпов резонанса (в нс)
            tdata.attrs["units"] = "ns"

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
        
        self._settings_handler.setupUI(self._processing_panel, self._plot_updater)

        self._settings_handler_plots.setup_plot_updater(self._data_processor, self._plot_updater)
        self._settings_handler_plots.setup_overview_panel(self._overview_panel)
        # self._settings_handler_plots.setupUI(self._plot_updater)

        self._overview_panel.figure_TEP.set_x_shift(-self._time_shift, self._n_samples, signal="TEP")
        self._overview_panel.figure_MEP.set_x_shift(-self._time_shift, self._n_samples, signal="MEP")

        self._on_change_main_scale()

        self._settings_handler_record = RecordSettingsHandler(self.settings.nvx_control, self._nvx_control_panel)
        self._settings_handler_record.load_from_json(default=True)

        self._settings_handler.load_from_json(default=True)
        self._stimuli_control_panel.sync_ui_from_settings()

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
    
    # def keyPressEvent(self, event):
    #     if event.key() == Qt.Key_Up+Qt.Key_N:                  # -- volume up
    #         new_value = min(100, self._audio_player.volume + 5)
    #         self._on_change_noise_volume(new_value)   
        
    #     # elif event.key() == Qt.Key_Down:                # -- volume down
    #     #     new_value = max(0, self._volume - 1)
    #     #     self.update_volume(new_value)

    #     # elif event.key() == Qt.Key_M:                   # -- mute
    #     #     self._player.audio_toggle_mute()
    #     #     self.playerIsMuted.emit()

    #     else:
    #         super().keyPressEvent(event)
             
    def closeEvent(self, event):
        self._settings_handler_record.sync_settings_from_ui()
        self._settings_handler.save_to_json(default=True)
        self._settings_handler_record.save_to_json(default=True)

        if self.settings.nvx_control.activate_bat:
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
    
    

