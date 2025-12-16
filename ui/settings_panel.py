from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import json

from utils.ui_helpers import (
    create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_lineedit
)
from utils.layout_utils import create_hbox, create_vbox


class SettingsPanel(QFrame):
    """ Панель с настройками."""

    def __init__(self, parent=None, callbacks=None, params=None, channels=None):
        super().__init__(parent)

        self.callbacks = callbacks or {}
        self.params = params or {}
        self.channels = channels

        self._init_ui()

    def _init_ui(self):
        """Создание структуры панели"""

        self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(150)

        self._setup_frame()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

        # Добавляем скролл-обёртку
        self.scroll = QScrollArea()
        self.scroll.setWidget(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

    def _setup_frame(self):
        self._create_epochs_manager_widgets()
        self._create_nvx_manager_widgets()
        self._create_stimuli_manager_widgets()
        self._create_data_processings_widgets()

    def _create_epochs_manager_widgets(self):
        self._epochs_manager_frame = QFrame(self)

        # --- Режим: усреднение или одиночные пробы ---
        self._label_epochs = QLabel("ПРОСМОТР ЭПОХ", self)
        self._label_data = QLabel("Выводить:", self)
        self.combo_box_mode_data = create_combo_box(items=["Новые данные", "Загруженные"], 
                                        curr_item_idx=self._params["curr_mode_data_idx"], parent=self)
        
        # --- Управление эпохами (сохранение, загрузка и тд) ---
        self.button_load = create_button(text='Load', disabled=False, parent=self)
        self.button_save = create_button(text='Save', disabled=True, parent=self)
        
        self.button_show_epoch = create_button('Show #', disabled=True, parent=self)
        self.spin_box_show_epoch = spin_box(0, 0, 0, parent=self)
        self.button_remove_epoch = create_button('Delete #', disabled=True, parent=self)
        self.spin_box_remove_epoch =spin_box(0, 0, 0, parent=self)
        
        self.button_restart = create_button(text='Очистить память', disabled=False, parent=self)

    def _create_nvx_manager_widgets(self):
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

    def _create_stimuli_manager_widgets(self):
        self._stimuli_manager_frame = QFrame(self)
        self._label_stimuli = QLabel("СТИМУЛЫ", self)
        self.button_create_stimuli = create_button(text='Создать стимулы', disabled=False, parent=self)

        label_monitor = QLabel("монитор", self)
        self.spin_box_monitor = spin_box(1, 3, self.params["stimuli"]["monitor"], parent=self)
        self._monitor = create_hbox([label_monitor, self.spin_box_monitor])

        
        self.button_stimuli = create_button(text='Показ стимулов', disabled=False, parent=self)
        self.check_box_stimuli_record = check_box(self.params["stimuli"]["stimuli_with_record"], 'Запись NVX', parent=self)
        self._stimuli_record = create_hbox([self.button_stimuli, self.check_box_stimuli_record])

        label_stimuli = QLabel("Выбрать: ", self)
        self.combo_box_stimuli = combo_box([], parent=self)
        # self.button_choose_stimuli = create_button(text='Выбрать', disabled=True, parent=self)
        self._button_update_stimuli = create_button(text='⟳', disabled=False, parent=self, w=30)
        self._stimuli = create_hbox([label_stimuli, self.combo_box_stimuli, self._button_update_stimuli])
        # self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)

    def _create_data_processings_widgets(self):
        self._processing_frame = QFrame(self)
        # --- Обработка эпох в приложении ---
        self._label_processing = QLabel("ОБРАБОТКА", self)
        self.button_processing = create_button('Применить', disabled=False, parent=self)

        self.check_box_average = create_check_box(self._proc_params["do_averaging"], 'Усреднение', parent=self)
        self.combo_box_aver = create_combo_box(self._proc_params['aver_methods'], curr_item=self._proc_params['curr_aver_method'], parent=self)

        self.check_box_lowpass = create_check_box(self._proc_params["do_lowpass_filtering"], 'ФНЧ', parent=self)
        self.spin_box_lowpass = create_spin_box(min=1, max=2500, value=self._proc_params["lowpass_freq_Hz"], parent=self)
        self._label_hz = QLabel("Гц", self)
        
        self.check_box_rereference = create_check_box(self._proc_params["do_rereferencing"], 'Референт:', parent=self)
        self.combo_box_rereference = create_checkable_combobox(self.channels, self._proc_params['rereference_channel'], status=True, parent=self)

        self.check_box_car = create_check_box(self._proc_params['do_CAR_filtering'], 'CAR', parent=self)
        self._label_CAR_except = QLabel("кроме:", self)
        self.combo_box_channels = create_checkable_combobox(self.channels, self._proc_params['CAR_except_channels'], w=70, parent=self)

        self.check_box_baseline = create_check_box(self._proc_params['do_baseline_correction'], 'Бейзлайн', parent=self)
        self.spin_box_baseline_from = create_spin_box(-1000, self._proc_params['baseline_to_ms'], self._proc_params['baseline_from_ms'], step=10, parent=self)
        self.spin_box_baseline_to = create_spin_box(self._proc_params['baseline_from_ms'], 0, self._proc_params['baseline_to_ms'], step=10, parent=self)
        self._label_start = QLabel("от", self)
        self._label_end = QLabel("до", self)
        self._label_ms = QLabel("мс", self)
        self.combo_box_baseline = create_combo_box(self._proc_params['baseline_methods'], 
                                            curr_item=self._proc_params["curr_baseline_method"],parent=self)
        
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
        # | processings      |
        # +------------------+

        self._setup_epochs_frame()
        self._setup_nvx_frame()
        self._setup_stimuli_frame()
        self._setup_processing_frame()

        layout = QVBoxLayout(self)
        layout.addWidget(self._epochs_manager_frame)
        layout.addWidget(self._nvx_control_frame)
        layout.addWidget(self._stimuli_manager_frame)
        layout.addWidget(self._processing_frame)
 
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


    def _setup_epochs_frame(self):
        layout_data = create_hbox([self._label_data, self.combo_box_mode_data])
        layout_control_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch, self.button_remove_epoch, self.spin_box_remove_epoch])

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
        layout.addWidget(self._label_stimuli)
        layout.addLayout(self._stimuli)                 # выбрать стимулы
        layout.addLayout(self._monitor)
        layout.addLayout(self._stimuli_record)          # начать проигрывать стимулы
        layout.addWidget(self.button_create_stimuli)    # создать новый видос со стимулами
        
    def _setup_processing_frame(self):
        layout = QVBoxLayout(self._processing_frame)

        layout.addWidget(self._label_aver_main)
        layout.addLayout(self._aver_mode)

        layout.addWidget(self._label_lowpass_main)
        layout.addLayout(self._lowpass)

        layout.addWidget(self._label_reref_main)
        layout.addLayout(self._rereference)

        layout.addWidget(self._label_CAR_main)
        layout.addLayout(self._car)

        layout.addWidget(self._label_baseline_main)
        layout.addLayout(self._baseline_range)
        layout.addLayout(self._baseline_mode)

    
    def _update_combo_box_stimuli(self):
        self.combo_box_stimuli.clear()
        try:
            with open(self.params["stimuli"]["stimuli_filename"], "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.combo_box_stimuli.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")
        
    # ──────────────────────────────────────────────
    # Ниже — примеры подпанелей, вынесенные в отдельные методы
    # ──────────────────────────────────────────────

    def _create_processing_box(self):
        """Блок обработки (усреднение, baseline, CAR и т.д.)"""
        box = QFrame(self)
        box.setFrameShape(QFrame.Box)
        box.setLineWidth(1)
        layout = QGridLayout(box)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Заголовок
        label = QLabel("Обработка сигналов", box)
        font = QFont("Helvetica", 14, QFont.Bold)
        label.setFont(font)
        layout.addWidget(label, 0, 0, 1, 2)

        # Пример кнопки
        btn_apply = self._create_button("Применить", self.callbacks.get("update_averaging"))
        layout.addWidget(btn_apply, 1, 0, 1, 2)

        return box

    def _create_speed_box(self):
        """Блок SPEED"""
        box = QFrame(self)
        box.setFrameShape(QFrame.Box)
        box.setLineWidth(1)
        layout = QGridLayout(box)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        label = QLabel("SPEED настройки", box)
        layout.addWidget(label, 0, 0, 1, 2)

        btn_save = self._create_button("Сохранить настройки", self.callbacks.get("launch_speed"))
        layout.addWidget(btn_save, 1, 0, 1, 2)

        return box

    def _setup_connections(self):
        self._button_update_stimuli.clicked.connect(self._update_combo_box_stimuli)


    def _finilize(self):
        self._update_combo_box_stimuli()

