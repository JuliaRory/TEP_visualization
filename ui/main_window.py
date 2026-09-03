from PyQt5.QtCore import Qt, QTimer, pyqtSignal,  QEvent
from PyQt5.QtGui import QGuiApplication, QKeySequence
from PyQt5.QtGui import  QMouseEvent
from PyQt5.QtWidgets import QWidget, qApp, QSizePolicy, QSplitter, QApplication, QHBoxLayout, QFileDialog, QMessageBox, QShortcut
                             
import numpy as np
import pandas as pd

import os
import json
import time
import h5py
from dataclasses import asdict, is_dataclass
from types import SimpleNamespace

from ui import (SettingsPanel, ProcessingPanel, NVXControlPanel, StimuliControlPanel, SurveyPanel,
                TopoTEPsPanel, overviewPanel, MEPsPanel)
 
from logic.sources.stream import StreamSource
from logic.sources.message import EpochLabelMessageSource
from logic.sources.file import load_record_epochs
from logic.data_processor import DataProcessor, LABEL_NOT_LABELED, LABEL_SOURCE_EXTERNAL, LABEL_SOURCE_STIMULUS
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

    def __init__(
        self,
        input_stream,
        resonance,
        output_stream,
        filename_params,
        feet_stim_stream=None,
        epoch_labels_stream=None,
        tension_wait_stream=None,
        tension_on_stream=None,
    ):
        super().__init__()

        place_widget(self, monitor=1, coordinates=(50, 50))

        # == Параметры и структуры данных ==

        self._resonance = resonance                       # прокси для управления резонансными модулями
        self._output_stream = output_stream
        self._feet_stim_stream = feet_stim_stream
        self._epoch_labels_stream = epoch_labels_stream
        self._tension_wait_stream = tension_wait_stream
        self._tension_on_stream = tension_on_stream

        with open(filename_params) as json_data:          # вгрузить настройки приложения
            self.params = json.load(json_data)  
        
        self.settings = Settings()                                                   # Хранилище настроек
        self.settings_plot = PlotSettings()                                        # Хранилище настроек для отрисовки графиков

        self._input_stream = StreamSource(input_stream)                              # Приёмник (онлайн) данных
        self._epoch_label_stream = EpochLabelMessageSource(epoch_labels_stream) if epoch_labels_stream is not None else None
        #self._load_data = FileSource()                                              # Приёмник загружаемых данных
        
        self._data_processor = DataProcessor(self.settings)                                       # Обработчик данных (эпох)
        self._epoch_record_buffer = EpochRecordBuffer(self.settings.processing_settings)
      
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
        self._setup_shortcuts()
                
        # == Показать окно ==
        self._post_init()

    # --- Инициализация ---
    def _init_state(self):
        """Инициализирует начальное состояние переменных"""

        self._session_loaded = []                              # список с подгруженными датасетами
        self._session_loaded_labels = []                       # список с названиями подгруженных файлов (для легенды)
        self._record_epoch_path = None
        self._record_epochs = None
        self._record_timestamps = None
        self._record_epoch_idx = 0
        self._mep_movement_detection_window = None
        self._mep_condition_analysis_window = None

        # отображение эпох
        self._specific_epoch = False                         # флаг для отслеживания режима показа определенной эпохи или стандартного
        
        self.SPEED = self.params['SPEED']
        processing = self.settings.processing_settings
        processing_fs = (
            processing.resample_freq_Hz
            if processing.do_resampling
            else processing.current_sampling_rate_Hz
        )
        self._ms_to_sample = lambda x: int(x / 1000 * processing_fs)                                      # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(processing.epoch_window_end_ms - processing.epoch_window_start_ms)
        self._time_shift = self._ms_to_sample(0 - processing.epoch_window_start_ms)                       # смещение относительно нуля для графиков в сэпмлах

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
                                                output_stream=self._output_stream,
                                                feet_stim_stream=self._feet_stim_stream,
                                                tension_wait_stream=self._tension_wait_stream,
                                                tension_on_stream=self._tension_on_stream)

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
        
        
        processing_timebase = SimpleNamespace(
            Fs=self.settings.processing_settings.current_sampling_rate_Hz,
            window_start=self.settings.processing_settings.epoch_window_start_ms,
            window_end=self.settings.processing_settings.epoch_window_end_ms,
        )

        self._topo_teps_panel = TopoTEPsPanel(parent=self,
                                         settings=self.settings_plot.topo_teps, 
                                         speed_settings=processing_timebase,
                                         settings_handler=self._settings_handler,
                                         processing_ui=self._processing_panel,
                                         init_size=[self._center_plots_width, self._center_plots_height])
        
        self._meps_panel = MEPsPanel(parent=self,
                                    Fs=self.settings.processing_settings.current_sampling_rate_Hz,
                                    settings=self.settings_plot.single_meps,
                                    settings_dl=self.settings_plot.meps_deeper_look,
                                    processing_settings=self.settings.processing_settings,
                                    init_size=[self._center_plots_width, self._center_meps_height])
        
        self.settings_plot.overview_panel.butts_plot.MEP.amp = self.settings_plot.single_meps.max_amp_mV
        self._overview_panel = overviewPanel(parent=self,
                                         settings=self.settings_plot.overview_panel, 
                                         Fs=self.settings.processing_settings.current_sampling_rate_Hz,
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
        self._data_processor.newDataProcessed.connect(lambda: self._stimuli_control_panel.update_bci_mep_epoch(self._data_processor))
        self._data_processor.labelsChanged.connect(self._sync_epoch_label_filter_options)
        self._data_processor.labelWarning.connect(self._show_epoch_label_warning)

        if self._epoch_label_stream is not None:
            self._epoch_label_stream.labelReady.connect(
                lambda label: self._on_epoch_label_received(label, LABEL_SOURCE_EXTERNAL)
            )
            self._epoch_label_stream.warning.connect(self._show_epoch_label_warning)
        self._stimuli_control_panel.stimulusLabelReady.connect(
            lambda label: self._on_epoch_label_received(label, LABEL_SOURCE_STIMULUS)
        )
        self._topo_teps_panel.epochLabelSourceChanged.connect(self._on_epoch_label_source_changed)
        self._topo_teps_panel.epochLabelFilterChanged.connect(self._on_epoch_label_filter_changed)

        # отрисовка изменений в количестве эпох
        self._data_processor.updateCounter.connect(lambda n: self._update_label_counter(n))

        # подключение окна MEPDeeperLook
        self._meps_panel.deeperLookActivate.connect(lambda: self._plot_updater.add_mep_deeper_look(self._meps_panel._deeper_look_window))
        self._meps_panel.movementDetectionActivate.connect(self._on_mep_movement_detection_button_click)
        self._meps_panel.conditionAnalysisActivate.connect(self._on_mep_condition_analysis_button_click)
        self._meps_panel.processingChanged.connect(self._on_mep_plot_settings_changed)
        self._meps_panel.emgProcessingApplyRequested.connect(self._on_emg_processing_apply_requested)

        # начальная замедленная инициализиация всех вычислений для уменьшения подтупливаний при запуске приложения
        # self.start_calc_signal.connect(self._initial_calculations)

        # работа с эпохами
        # self._settings_panel.combo_box_mode_data.currentIndexChanged[int].connect(self._on_change_mode_data)
        self._settings_panel.button_save.clicked.connect(self._on_button_save_click)
        # self._settings_panel.button_load.clicked.connect(self._on_button_load_click)
        self._settings_panel.button_next_record_epoch.clicked.connect(self._on_next_record_epoch_button_click)
        self._settings_panel.combo_box_record_file.currentTextChanged.connect(self._on_record_epoch_file_changed)
        self._settings_panel.combo_box_record_file.currentTextChanged.connect(self._settings_panel.combo_box_record_file.setToolTip)
        self._settings_panel.button_restart.clicked.connect(self._on_restart_button_click)
        self._settings_panel.button_remove_epoch.clicked.connect(self._on_remove_epoch_button_click)
        self._settings_panel.button_show_epoch.clicked.connect(self._on_show_epoch_button_click)
        self._settings_panel.speedApplyRequested.connect(self._on_speed_apply_requested)

        # сигнал для обновления состояния надписи REC в центральных графиках
        self._nvx_control_panel.recording.connect(self._on_recording_status_changed_signal)
        self._nvx_control_panel.recording.connect(self._stimuli_control_panel.set_recording_active)
        self._nvx_control_panel.recordingFileChanged.connect(self._on_nvx_recording_file_changed)

        # сигнал для управления записью nvx одновременно с показом стимулов
        self._stimuli_control_panel.stimuliPresentation.connect(self._on_stimuli_presenation_status_changed_signal)
                      
        # изменение масштаба для визуализации 
        for spin_box in self._overview_panel.spinbox_ts:
            spin_box.valueChanged.connect(self._update_topoplots)
        self._topo_teps_panel.scale_changed.connect(self._on_change_main_scale)

    def _setup_shortcuts(self):
        self._shortcuts = []
        shortcuts = [
            ("Ctrl+Up", lambda: self._topo_teps_panel.adjust_y_scale(-1)),
            ("Ctrl+Down", lambda: self._topo_teps_panel.adjust_y_scale(1)),
            ("Ctrl+Left", lambda: self._topo_teps_panel.adjust_right_time_scale(-1)),
            ("Ctrl+Right", lambda: self._topo_teps_panel.adjust_right_time_scale(1)),
        ]

        for key_sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key_sequence), self)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.setAutoRepeat(True)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

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

    def _on_emg_processing_apply_requested(self):
        self._meps_panel.sync_emg_processing_settings_from_ui()
        self._data_processor.configure_emg_processing()
        self._plot_updater._sync_plot_timebase(self._data_processor)
        self._plot_updater.update_meps(self._data_processor)
        self._plot_updater.update_avg_meps(self._data_processor)
        if getattr(self._plot_updater, "do_mep_deeper_look", False):
            self._plot_updater.update_mep_deeper_look(self._data_processor)

    def _on_mep_plot_settings_changed(self):
        self._plot_updater.update_meps(self._data_processor)
        self._plot_updater.update_avg_meps(self._data_processor)
        if getattr(self._plot_updater, "do_mep_deeper_look", False):
            self._plot_updater.update_mep_deeper_look(self._data_processor)

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
    def _on_record_epoch_file_changed(self, *_args):
        self._record_epoch_path = None
        self._record_epochs = None
        self._record_timestamps = None
        self._record_epoch_idx = 0

    def _selected_record_epoch_path(self):
        filename = self._settings_panel.combo_box_record_file.currentText().strip()
        if not filename:
            return None
        return os.path.join("data", "records", filename)

    def _on_next_record_epoch_button_click(self):
        path = self._selected_record_epoch_path()
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "Record epochs", f"Файл не найден:\n{path}")
            return

        try:
            if self._record_epoch_path != path or self._record_epochs is None:
                self._record_epochs, self._record_timestamps = load_record_epochs(
                    path,
                    expected_channels=len(self.settings.channels) + 2,
                    eeg_channels=len(self.settings.channels),
                )
                self._record_epoch_path = path
                self._record_epoch_idx = 0

            if len(self._record_epochs) == 0:
                QMessageBox.information(self, "Record epochs", f"В файле нет эпох:\n{path}")
                return

            idx = self._record_epoch_idx % len(self._record_epochs)
            epoch = self._record_epochs[idx]
            timestamp = float(self._record_timestamps[idx]) if self._record_timestamps is not None else float(idx)
            self._record_epoch_idx = (idx + 1) % len(self._record_epochs)
            self._data_processor.add_epoch(epoch, timestamp)
        except Exception as exc:
            QMessageBox.warning(self, "Record epochs", f"Не удалось взять эпоху из файла:\n{path}\n\n{exc}")

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
        n_displayed = self._data_processor.displayed_epoch_count()
        self._topo_teps_panel.label_n_epoch.setText('Количество эпох: {}. '.format(n_displayed))
        
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

    def _on_epoch_label_received(self, label, source):
        self._data_processor.add_epoch_label(label, source=source)

    def _on_epoch_label_source_changed(self, source):
        self._data_processor.set_epoch_label_source(source)

    def _on_epoch_label_filter_changed(self, label):
        self._data_processor.set_epoch_label_filter(label)
        self._update_label_counter(self._data_processor._n_epoch)
        self._refresh_label_filtered_plots()

    def _sync_epoch_label_filter_options(self):
        labels = self._data_processor.available_epoch_labels()
        current = list(getattr(self._data_processor, "epoch_label_filters", ["all"]))
        if current != ["all"]:
            current = [label for label in current if label in labels]
        if not current:
            current = ["all"]
            self._data_processor.set_epoch_label_filter(current)
        self._topo_teps_panel.set_epoch_label_options(
            labels,
            current=current,
        )
        self._topo_teps_panel.set_epoch_label_counts(self._data_processor.epoch_label_counts())
        self._update_label_counter(self._data_processor._n_epoch)

    def _refresh_label_filtered_plots(self):
        self._plot_updater.clear_plots()
        self._plot_updater.update_plots(self._data_processor)
        if getattr(self._plot_updater, "do_mep_deeper_look", False):
            self._plot_updater.update_mep_deeper_look(self._data_processor)

    def _show_epoch_label_warning(self, message):
        QMessageBox.warning(self, "Epoch labels", str(message))

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
        
        raw_epoch_records = self._data_processor.raw_epoch_records()
        raw_epochs = [epoch for epoch, _ in raw_epoch_records]
        if len(raw_epochs) == 0:
            print("---> Нет эпох для сохранения")
            return None

        return self._save_epochs_export(file_path, raw_epoch_records, raw_epochs)

        # shape_counts = {}
        # for epoch in epochs_to_save:
        #     shape = tuple(np.asarray(epoch).shape)
        #     shape_counts[shape] = shape_counts.get(shape, 0) + 1
        # save_shape = max(shape_counts, key=shape_counts.get)
        # if len(shape_counts) > 1:
        #     print(f"---> Эпохи имеют разные исходные формы {shape_counts}; сохраняю форму {save_shape}")
        #     epoch_records = [
        #         (epoch, ts)
        #         for epoch, ts in epoch_records
        #         if tuple(np.asarray(epoch).shape) == save_shape
        #     ]
        #     epochs_to_save = [epoch for epoch, _ in epoch_records]

        # n_channels = int(np.asarray(epochs_to_save[0]).shape[0])
        # data2save = np.array(epochs_to_save).transpose(0, 2, 1).reshape(-1, n_channels)      # (n_samples, n_channels)
        # ts2save = np.array([ts for _, ts in epoch_records])
        # # если выбран файл
        # with h5py.File(file_path, "w") as h5f:
        #     h5f.create_dataset("processed_epochs", data=self._data_processor.processed_epoch_records(), dtype='float32')      # для эпох (64 EEG + 2 EMG)

        #     data = h5f.create_dataset("epochs", data=data2save, dtype='float32')      # для эпох (64 EEG + 2 EMG)
        #     data.attrs["Fs"] = self.settings.processing_settings.current_sampling_rate_Hz
        #     data.attrs["source_Fs"] = self.settings.processing_settings.current_sampling_rate_Hz
        #     data.attrs["effective_Fs"] = getattr(
        #         self._data_processor,
        #         "effective_sampling_rate_Hz",
        #         getattr(
        #             self._data_processor,
        #             "_sampling_rate_Hz",
        #             self.settings.processing_settings.current_sampling_rate_Hz,
        #         ),
        #     )
        #     data.attrs["resampled"] = False
        #     data.attrs["n_samples"] = int(np.asarray(epochs_to_save[0]).shape[-1])
        #     data.attrs["n_epochs"] = len(epochs_to_save)
        #     data.attrs["n_channels"] = n_channels
            
        #     tdata = h5f.create_dataset("timestamps", data=ts2save, dtype='int64')      # для таймстемпов резонанса (в нс)
        #     tdata.attrs["units"] = "ns"

    def _save_epochs_export(self, file_path, raw_epoch_records, raw_epochs):
        raw_timestamps = np.asarray([ts for _, ts in raw_epoch_records], dtype=np.int64)
        epoch_labels = list(getattr(self._data_processor, "epoch_labels", []))
        processed_eeg_epochs = self._data_processor.get_eeg_epochs(filter_by_label=False)
        processed_emg_epochs = self._data_processor.get_processed_emg_channel_epochs(filter_by_label=False)
        processed_mep_epochs = self._data_processor.get_emg_epochs(filter_by_label=False)
        processing_settings = self.settings.processing_settings

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

        with h5py.File(file_path, "w") as h5f:
            h5f.attrs["source"] = "TEP_visual"
            h5f.attrs["created_at_unix"] = time.time()
            h5f.attrs["format_version"] = "2"

            self._write_epoch_group(
                h5f,
                "raw_epochs",
                raw_epochs,
                raw_timestamps,
                epoch_labels,
                {
                    "description": "Unprocessed epochs as received from the input stream",
                    "units": "V",
                    "sampling_rate_Hz": float(getattr(processing_settings, "current_sampling_rate_Hz", 0) or 0),
                    "window_start_ms": float(getattr(processing_settings, "epoch_window_start_ms", 0)),
                    "window_end_ms": float(getattr(processing_settings, "epoch_window_end_ms", 0)),
                },
            )
            self._write_epoch_group(
                h5f,
                "processed_eeg_epochs",
                processed_eeg_epochs,
                raw_timestamps[: len(processed_eeg_epochs)],
                epoch_labels[: len(processed_eeg_epochs)],
                {
                    "description": "Processed EEG epochs after EEG pipeline",
                    "units": "uV",
                    "sampling_rate_Hz": float(getattr(self._data_processor, "effective_sampling_rate_Hz", 0) or 0),
                    "n_channels": len(self.settings.channels),
                },
            )
            self._write_epoch_group(
                h5f,
                "processed_emg_epochs",
                processed_emg_epochs,
                raw_timestamps[: len(processed_emg_epochs)],
                epoch_labels[: len(processed_emg_epochs)],
                {
                    "description": "Processed EMG channel epochs after EMG pipeline",
                    "units": "V",
                    "sampling_rate_Hz": float(getattr(self._data_processor, "mep_sampling_rate_Hz", 0) or 0),
                },
            )
            self._write_epoch_group(
                h5f,
                "processed_mep_epochs",
                processed_mep_epochs,
                raw_timestamps[: len(processed_mep_epochs)],
                epoch_labels[: len(processed_mep_epochs)],
                {
                    "description": "Derived MEP epochs computed as channel difference from processed EMG channels",
                    "units": "mV",
                    "sampling_rate_Hz": float(getattr(self._data_processor, "mep_sampling_rate_Hz", 0) or 0),
                },
            )
            self._write_json_group(h5f, "eeg_processing_metadata", self._eeg_processing_metadata())
            self._write_json_group(h5f, "emg_processing_metadata", self._emg_processing_metadata())
            self._write_legacy_epochs_dataset(h5f, raw_epoch_records)

            tdata = h5f.create_dataset("timestamps", data=raw_timestamps, dtype="int64")
            tdata.attrs["units"] = "ns"
            h5f.create_dataset(
                "epoch_labels",
                data=np.asarray(epoch_labels, dtype=object),
                dtype=h5py.string_dtype(encoding="utf-8"),
            )

        print(f"---> Р­РїРѕС…Рё СЃРѕС…СЂР°РЅРµРЅС‹: {file_path}")
        return file_path

    def _write_legacy_epochs_dataset(self, h5f, epoch_records):
        epochs_to_save = [epoch for epoch, _ in epoch_records]
        shape_counts = {}
        for epoch in epochs_to_save:
            shape = tuple(np.asarray(epoch).shape)
            shape_counts[shape] = shape_counts.get(shape, 0) + 1
        save_shape = max(shape_counts, key=shape_counts.get)
        if len(shape_counts) > 1:
            print(f"---> Epochs have different raw shapes {shape_counts}; legacy dataset keeps shape {save_shape}")
            epoch_records = [
                (epoch, ts)
                for epoch, ts in epoch_records
                if tuple(np.asarray(epoch).shape) == save_shape
            ]
            epochs_to_save = [epoch for epoch, _ in epoch_records]

        n_channels = int(np.asarray(epochs_to_save[0]).shape[0])
        data2save = np.asarray(epochs_to_save, dtype=np.float32).transpose(0, 2, 1).reshape(-1, n_channels)
        data = h5f.create_dataset("epochs", data=data2save, dtype="float32")
        data.attrs["Fs"] = self.settings.processing_settings.current_sampling_rate_Hz
        data.attrs["source_Fs"] = self.settings.processing_settings.current_sampling_rate_Hz
        data.attrs["effective_Fs"] = getattr(
            self._data_processor,
            "effective_sampling_rate_Hz",
            getattr(
                self._data_processor,
                "_sampling_rate_Hz",
                self.settings.processing_settings.current_sampling_rate_Hz,
            ),
        )
        data.attrs["resampled"] = False
        data.attrs["n_samples"] = int(np.asarray(epochs_to_save[0]).shape[-1])
        data.attrs["n_epochs"] = len(epochs_to_save)
        data.attrs["n_channels"] = n_channels
        data.attrs["shape_original"] = "[n_epochs, n_channels, n_samples]"
        data.attrs["shape_saved"] = "[n_epochs * n_samples, n_channels]"

    def _write_epoch_group(self, h5f, name, epochs, timestamps, labels, attrs):
        group = h5f.create_group(name)
        group.attrs.update(attrs)

        if isinstance(epochs, np.ndarray):
            epoch_list = [epochs[i] for i in range(epochs.shape[0])] if epochs.ndim > 0 else []
        else:
            epoch_list = list(epochs)

        timestamps = np.asarray(timestamps, dtype=np.int64)
        group.create_dataset("timestamps", data=timestamps[: len(epoch_list)], dtype="int64").attrs["units"] = "ns"
        label_list = list(labels)[: len(epoch_list)]
        if len(label_list) < len(epoch_list):
            label_list.extend([LABEL_NOT_LABELED] * (len(epoch_list) - len(label_list)))
            self._show_epoch_label_warning(
                f"Epoch labels count ({len(labels)}) does not match epochs count ({len(epoch_list)}) for {name}"
            )
        group.create_dataset(
            "labels",
            data=np.asarray(label_list, dtype=object),
            dtype=h5py.string_dtype(encoding="utf-8"),
        )
        group.attrs["n_epochs"] = len(epoch_list)

        if len(epoch_list) == 0:
            data = group.create_dataset("data", shape=(0,), dtype="float32")
            data.attrs["shape_original"] = "empty"
            return

        shapes = [tuple(np.asarray(epoch).shape) for epoch in epoch_list]
        if len(set(shapes)) == 1:
            data = np.asarray(epoch_list, dtype=np.float32)
            dataset = group.create_dataset("data", data=data, dtype="float32")
            dataset.attrs["shape_original"] = "[n_epochs, n_channels, n_samples]" if data.ndim == 3 else str(list(data.shape))
            dataset.attrs["n_epochs"] = data.shape[0]
            if data.ndim >= 2:
                dataset.attrs["n_samples"] = data.shape[-1]
            if data.ndim == 3:
                dataset.attrs["n_channels"] = data.shape[1]
            return

        group.attrs["variable_shapes"] = True
        group.attrs["epoch_shapes_json"] = json.dumps([list(shape) for shape in shapes])
        for i, epoch in enumerate(epoch_list):
            group.create_dataset(f"epoch_{i:06d}", data=np.asarray(epoch, dtype=np.float32), dtype="float32")

    def _write_json_group(self, h5f, name, payload):
        group = h5f.create_group(name)
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        dtype = h5py.string_dtype(encoding="utf-8")
        group.create_dataset("json", data=text, dtype=dtype)
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool, np.integer, np.floating)):
                group.attrs[key] = value

    def _eeg_processing_metadata(self):
        s = self.settings.processing_settings
        return {
            "kind": "EEG",
            "settings": self._settings_to_dict(s),
            "channels": list(self.settings.channels),
            "operations": [
                {
                    "name": "resampling",
                    "enabled": bool(getattr(s, "do_resampling", False)),
                    "source_Fs_Hz": float(getattr(s, "current_sampling_rate_Hz", 0) or 0),
                    "target_Fs_Hz": float(getattr(s, "resample_freq_Hz", 0) or 0),
                },
                {
                    "name": "highpass_filter",
                    "enabled": bool(getattr(s, "do_highpass_filtering", False)),
                    "freq_Hz": float(getattr(s, "highpass_freq_Hz", 0) or 0),
                },
                {
                    "name": "lowpass_filter",
                    "enabled": bool(getattr(s, "do_lowpass_filtering", False)),
                    "freq_Hz": float(getattr(s, "lowpass_freq_Hz", 0) or 0),
                },
                {
                    "name": "baseline_correction",
                    "enabled": bool(getattr(s, "do_baseline_correction", False)),
                    "from_ms": float(getattr(s, "baseline_from_ms", 0)),
                    "to_ms": float(getattr(s, "baseline_to_ms", 0)),
                    "method": getattr(s, "curr_baseline_method", "mean"),
                },
                {
                    "name": "CAR",
                    "enabled": bool(getattr(s, "do_CAR_filtering", False)),
                    "except_channels": list(getattr(s, "car_except_channels", []) or []),
                },
                {
                    "name": "rereference",
                    "enabled": bool(getattr(s, "do_rereferencing", False)),
                    "channels": list(getattr(s, "rereference_channel", []) or []),
                },
            ],
            "effective_sampling_rate_Hz": float(getattr(self._data_processor, "effective_sampling_rate_Hz", 0) or 0),
            "units": "uV",
        }

    def _emg_processing_metadata(self):
        s = self.settings.processing_settings
        return {
            "kind": "EMG",
            "settings": self._settings_to_dict(s),
            "operations": [
                {
                    "name": "resampling",
                    "enabled": bool(getattr(s, "do_emg_resampling", False)),
                    "source_Fs_Hz": float(getattr(s, "current_sampling_rate_Hz", 0) or 0),
                    "target_Fs_Hz": float(getattr(s, "emg_resample_freq_Hz", 0) or 0),
                },
                {
                    "name": "highpass_filter",
                    "enabled": bool(getattr(s, "do_emg_highpass_filtering", False)),
                    "freq_Hz": float(getattr(s, "emg_highpass_freq_Hz", 0) or 0),
                },
                {
                    "name": "lowpass_filter",
                    "enabled": bool(getattr(s, "do_emg_lowpass_filtering", False)),
                    "freq_Hz": float(getattr(s, "emg_lowpass_freq_Hz", 0) or 0),
                },
                {
                    "name": "baseline_correction",
                    "enabled": bool(getattr(s, "do_emg_baseline_correction", False)),
                    "from_ms": float(getattr(s, "emg_baseline_from_ms", 0)),
                    "to_ms": float(getattr(s, "emg_baseline_to_ms", 0)),
                    "method": "mean",
                },
                {
                    "name": "channel_difference",
                    "enabled": False,
                    "description": "Not part of processed_emg_epochs; saved separately as processed_mep_epochs",
                },
            ],
            "effective_sampling_rate_Hz": float(getattr(self._data_processor, "mep_sampling_rate_Hz", 0) or 0),
            "units": "V",
        }

    @staticmethod
    def _settings_to_dict(settings):
        if is_dataclass(settings):
            return asdict(settings)
        if hasattr(settings, "__dict__"):
            return {
                key: value
                for key, value in vars(settings).items()
                if not key.startswith("_")
            }
        return {}

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
        processor = self._data_processor
        if not getattr(processor, "use_eeg", True):
            return
        epochs = getattr(processor, "_eeg_epochs", [])
        if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
            if processor.process_new_data:
                plot = (len(epochs) != 0)
                if not processor.average_data:
                    data2plot = processor.transform_eeg_epoch(processor.get_eeg_epoch_by_index(-1))
                else:
                    data2plot = processor.calculate_avg_TEP()
            else:
                data2plot = []
                data_loaded = getattr(self, "_data_loaded", [])
                plot = (len(data_loaded) != 0)
                for data_raw in data_loaded:
                    if not processor.average_data:
                        data2plot.append(processor.transform_eeg_epoch(data_raw[-1]))     # последняя эпоха
                    else:
                        data = np.array([processor.transform_eeg_epoch(TEPs) for TEPs in data_raw])
                        data2plot.append(np.nanmean(data, axis=0))
        if plot:
            plot_data = data2plot[0] if isinstance(data2plot, list) else data2plot
            plot_data = np.asarray(plot_data)
            for i in range(3):
                ts = self._overview_panel.spinbox_ts[i].value()
                t = processor._time_shift + processor._ms_to_sample(ts)
                if plot_data.ndim != 2 or t < 0 or t >= plot_data.shape[-1]:
                    continue
                print(t, ts)
                
                self._overview_panel.figure_topo[i].plot_topomap(plot_data[:, t])

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
        self._meps_panel.sync_emg_processing_ui_from_settings()
        self._settings_panel.sync_speed_ui_from_settings()
        self._stimuli_control_panel.sync_ui_from_settings()

        self.show()

    def _on_speed_apply_requested(self):
        path = getattr(self.settings, "speed_settings_export_path", "")
        if not path:
            QMessageBox.warning(self, "SPEED", "Не задан путь для SPEED_settings.json")
            return

        try:
            saved_path = self._settings_handler.save_speed_settings_to_json(path)
        except OSError as exc:
            QMessageBox.warning(self, "SPEED", f"Не удалось сохранить SPEED_settings.json:\n{exc}")
            return

        QMessageBox.information(self, "SPEED", f"SPEED_settings.json сохранен:\n{saved_path}")

   
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
        self._settings_panel.sync_speed_settings_from_ui()
        self._settings_handler_record.sync_settings_from_ui()
        self._settings_handler.save_to_json(default=True)
        self._settings_handler_record.save_to_json(default=True)

        if self.settings.nvx_control.activate_bat:
            service = self._resonance.getService("Resonance-control")     # Берем сервис
            service.sendTransition('!terminate')
        event.accept()


    # --- неприкаянные функции ---
    
