from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy, QSlider
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt, pyqtSignal

import json

from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox
from utils.logic_helpers import are_equal

from ui.widgets.slider_with_labels import VerticalSliderWithLabel

class SettingsPanel(QFrame):
    
    """ Панель с настройками."""

    def __init__(self, settings, settings_handler, channels, parent=None, ):
        super().__init__(parent)

        self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(150)

        self.settings = settings
        self.settings_handler = settings_handler 
        self.channels = channels

        self._init_ui()

    def _init_ui(self):   

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

        # Добавляем скролл-обёртку
        self.scroll = QScrollArea()
        self.scroll.setWidget(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

    
    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        self._setup_epochs_manager_widgets()
        self._setup_nvx_manager_widgets()
        self._setup_stimuli_manager_widgets()


    def _setup_epochs_manager_widgets(self):
        self._epochs_manager_frame = QFrame(self)

        # --- Режим: усреднение или одиночные пробы ---
        self._label_epochs = QLabel("ПРОСМОТР ЭПОХ", self)
        self._label_data = QLabel("Выводить:", self)
        self.combo_box_mode_data = create_combo_box(items=["Новые данные", "Загруженные"], 
                                        curr_item_idx=self.settings.curr_mode_data_idx, parent=self)
        
        # --- Управление эпохами (сохранение, загрузка и тд) ---
        self.button_show_epoch = create_button('Show #', disabled=True, parent=self)
        self.spin_box_show_epoch = create_spin_box(0, 0, 0, parent=self)
        self.button_remove_epoch = create_button('Delete #', disabled=True, parent=self)
        self.spin_box_remove_epoch =create_spin_box(0, 0, 0, parent=self)

        self.button_load = create_button(text='Load', disabled=False, parent=self)
        self.button_save = create_button(text='Save', disabled=True, parent=self)
        self.button_restart = create_button(text='Clear', disabled=False, parent=self)
               
    def _setup_nvx_manager_widgets(self):
        self._nvx_control_frame = QFrame(self)

        # --- Управление NVX16 (запуск, запись и тд) ---
        self._label_nvx = QLabel("КОНТРОЛЬ NVX", self)
        self.button_nvx_control = create_button(text='Контроль qml', disabled=False, parent=self)   # запустить qml модуль для контроля над процессами
        self._label_nvx_control = QLabel("...", self)                                               # надпись для отображения состояния qml-процесса для контроля
        self.button_check_impedance = create_button(text='Импеданс', disabled=True, parent=self)
        self.button_nvx_launch = create_button(text='Старт', disabled=False, parent=self)           # launch and/or start
        self.button_nvx_stop = create_button(text='Стоп', disabled=False, parent=self)              # stop
        self.button_nvx_kill = create_button(text='kill', disabled=False, parent=self)              # !terminate
        self.lineedit_record = create_lineedit(parent=self)                                         # record name
        self.button_nvx_record = create_button(text='Запись', disabled=False, parent=self)          # recorder.start()      <-> "Остановить"

    def _setup_stimuli_manager_widgets(self):
        self._stimuli_manager_frame = QFrame(self)
        self._label_stimuli = QLabel("СТИМУЛЫ", self)
        self.button_create_stimuli = create_button(text='Создать', disabled=False, parent=self)

        self._label_monitor = QLabel("монитор", self)
        self.spin_box_monitor = create_spin_box(1, 3, self.settings.stimuli.monitor, parent=self)
        
        self.button_stimuli = create_button(text='Запуск', disabled=False, parent=self)
        self.check_box_stimuli_record = create_check_box(self.settings.stimuli.stimuli_with_record, 'Запись NVX', parent=self)

        self.button_stimuli_restart = create_button(text='Заново', disabled=True)
        self.button_stimuli_pause = create_button(text='▶', disabled=True, parent=self)

        self.label_stimuli_idx = QLabel("", self)

        self._label_stimuli_choose = QLabel("Выбрать: ", self)
        self.combo_box_stimuli = create_combo_box([], parent=self)
        self._button_update_stimuli = create_button(text='⟳', disabled=False, parent=self, w=30)

        self.volume_slider = VerticalSliderWithLabel()
        self.volume_slider.slider.setValue(self.settings.stimuli.volume)

        # self.volume_slider = QSlider(Qt.Vertical, self)
        # self.volume_slider.setRange(0, 100)
        # self.volume_slider.setValue(self.settings.stimuli.volume)

    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):
        # Vertical layout
        # +------------------|
        # | EPOCHS manager   |           
        # +------------------+
        # | NVX control      |
        # +------------------+
        # | STIMULI manager  |
        # +------------------+

        self._setup_epochs_frame()
        self._setup_nvx_frame()
        self._setup_stimuli_frame()

        layout = QVBoxLayout(self)
        layout.addWidget(self._epochs_manager_frame)
        layout.addWidget(self._nvx_control_frame)
        layout.addWidget(self._stimuli_manager_frame)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_epochs_frame(self):
        layout_data = create_hbox([self._label_data, self.combo_box_mode_data])
        layout_control_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch, self.button_remove_epoch, self.spin_box_remove_epoch])
        layout_records_history = create_hbox([self.button_load, self.button_save, self.button_restart])

                                                                # Vertical layout
        layout = QVBoxLayout(self._epochs_manager_frame)        # +-----------------------|
        layout.addWidget(self._label_epochs)                    # | ПРОСМОТР ЭПОХ         |
        layout.addLayout(layout_control_epoch)                  # | Show   #  Delete   #  |
        layout.addLayout(layout_data)                           # | Новые/Загрузить       |
        layout.addLayout(layout_records_history)                # | Load   Save   Clear   |
                                                                # +-----------------------+
    
    def _setup_nvx_frame(self):
        layout_qml_control = create_hbox([self.button_nvx_control, self._label_nvx_control])
        layout_nvx_control = create_hbox([self.button_nvx_launch, self.button_nvx_stop, self.button_nvx_kill])
        layout_record = create_hbox([self.lineedit_record, self.button_nvx_record])

                                                                # Vertical layout
        layout = QVBoxLayout(self._nvx_control_frame)           # +-----------------------|
        layout.addWidget(self._label_nvx)                       # | NVX control           |
        layout.addLayout(layout_qml_control)                    # | Контроль qml   ...    |
        layout.addWidget(self.button_check_impedance)           # | Проверить импеданс    |
        layout.addLayout(layout_nvx_control)                    # | start   stop    kill  |
        layout.addLayout(layout_record)                         # | record_name   Запись  |
                                                                # +-----------------------+

    def _setup_stimuli_frame(self):
        layout_stimuli_creation = create_hbox([self._label_stimuli, self.button_create_stimuli])
        layout_stimuli = create_hbox([self._label_stimuli_choose, self.combo_box_stimuli, self._button_update_stimuli])
        layout_monitor = create_hbox([self._label_monitor, self.spin_box_monitor, self.check_box_stimuli_record])
        layout_stimuli_control = create_hbox([self.button_stimuli, self.button_stimuli_pause, self.button_stimuli_restart, self.label_stimuli_idx])

                                                                # Vertical layout
        layout = QVBoxLayout()                                  # +-----------------------|
        layout.addLayout(layout_stimuli_creation)               # | Стимулы   Создать     |
        layout.addLayout(layout_stimuli)                        # | Выбрать __________ ⟳ |
        layout.addLayout(layout_monitor)                        # | Монитор __  _запись__ |
        layout.addLayout(layout_stimuli_control)                # | Запуск  Пауза  Заново |
        # layout.addWidget(self.button_create_stimuli)          # |                       |
                                                                # +-----------------------+

        final_layout = QHBoxLayout(self._stimuli_manager_frame)
        final_layout.addLayout(layout)
        final_layout.addWidget(self.volume_slider)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self._button_update_stimuli.clicked.connect(self._update_combo_box_stimuli)
        # self.button_processing.clicked.connect(self._on_processing_button_click)
        
        # self.combo_box_aver.currentTextChanged[str].connect(lambda text: setattr(self, "_last_aver_method", text))
        # self.spin_box_lowpass.valueChanged[int].connect(lambda value: setattr(self, "_last_lowpass_freq", value))
        # self.combo_box_rereference.textChanged[list].connect(lambda value: setattr(self, "_last_rereference_channel", value))
        # self.combo_box_channels.textChanged[list].connect(lambda value: setattr(self, "_last_CAR_except_channels", value))
        # self.combo_box_baseline.currentTextChanged[str].connect(lambda text: setattr(self, "_last_baseline_method", text))
        # self.spin_box_baseline_from.valueChanged[int].connect(lambda value: setattr(self, "_last_baseline_from", value))
        # self.spin_box_baseline_to.valueChanged[int].connect(lambda value: setattr(self, "_last_baseline_to", value))


    # =======================
    # =====   Логика    =====
    # =======================

    def _on_processing_button_click(self):
        if ~are_equal(self.combo_box_aver.currentText(), self._last_aver_method):
            self._last_aver_method = self.combo_box_aver.currentText()
            self.averagingChanged.emit()
        
        if ~are_equal(self.spin_box_lowpass.value(), self._last_lowpass_freq):
            self._last_lowpass_freq = self.spin_box_lowpass.value()
            self.lowpassChanged.emit()
        
        if ~are_equal(self.combo_box_rereference.checkedItems(), self._last_rereference_channel):
            self._last_rereference_channel = self.combo_box_rereference.checkedItems()
            self.rereferenceChanged.emit()

        if ~are_equal(self.combo_box_channels.checkedItems(), self._last_CAR_except_channels):
            self._last_CAR_except_channels = self.combo_box_channels.checkedItems()
            self.CARChanged.emit()

        is_baseline_method_changed = ~are_equal(self.combo_box_baseline.currentText(), self._last_baseline_method)
        is_baseline_from_changed = ~are_equal(self.spin_box_baseline_from.value(), self._last_baseline_from)
        is_baseline_to_changed = ~are_equal(self.spin_box_baseline_to.value(), self._last_baseline_to)
        
        if is_baseline_method_changed:
            self._last_baseline_method = self.combo_box_baseline.currentText()
        if is_baseline_from_changed:
            self._last_baseline_from = self.spin_box_baseline_from.value()
        if is_baseline_to_changed:
            self._last_baseline_to = self.spin_box_baseline_to.value()

        if is_baseline_method_changed or is_baseline_from_changed or is_baseline_to_changed:
            self.baselineChanged.emit()

        
    def _update_combo_box_stimuli(self):
        self.combo_box_stimuli.clear()
        try:
            with open(self.settings.stimuli.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.combo_box_stimuli.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")
        


    def _finilize(self):
        self._update_combo_box_stimuli()

