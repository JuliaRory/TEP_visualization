from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

from utils.ui_helpers import create_button, spin_box, check_box, combo_box, checkable_combobox
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
        self._connect_signals()  

        # Добавляем скролл-обёртку
        self.scroll = QScrollArea()
        self.scroll.setWidget(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

    def _setup_frame(self):
        
        # --- Режим: усреднение или одиночные пробы ---
        self._label_mode = QLabel("РЕЖИМ", self)
        self.combo_box_mode = combo_box(items=["Усреднение", "Одиночные пробы"], 
                                        curr_item_idx=self.params["curr_mode_idx"], parent=self)
        self.combo_box_mode_data = combo_box(items=["Новые данные", "Сравнение"], 
                                        curr_item_idx=self.params["curr_mode_data_idx"], parent=self)
        self._mode = create_vbox([self.combo_box_mode_data, self.combo_box_mode])

        # --- Участок с управлением данными (сохранение, загрузка и тд) ---
        self._manager_frame = QFrame(self)

        self.button_load = create_button(text='Load', disabled=False, parent=self)
        self.button_save = create_button(text='Save', disabled=True, parent=self)
        self._records_history = create_hbox([self.button_load, self.button_save])

        self.button_show_epoch = create_button('Show #', disabled=True, parent=self)
        self.spin_box_show_epoch = spin_box(0, 0, 0, parent=self)
        self._show_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch])

        self.button_remove_epoch = create_button('Delete #', disabled=True, parent=self)
        self.spin_box_remove_epoch =spin_box(0, 0, 0, parent=self)
        self._remove_epoch = create_hbox([self.button_remove_epoch, self.spin_box_remove_epoch])

        self.button_restart = create_button(text='Очистить память', disabled=False, parent=self)
        # self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)

        self.button_nvx_record = create_button(text='Начать запись', disabled=False, parent=self)
        # self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)

        self._label_stimuli = QLabel("Стимулы", self)
        self.button_create_stimuli = create_button(text='Создать стимулы', disabled=False, parent=self)

        label_monitor = QLabel("монитор", self)
        self.spin_box_monitor = spin_box(1, 3, self.params["stimuli"]["monitor"], parent=self)
        self._monitor = create_hbox([label_monitor, self.spin_box_monitor])

        self.button_stimuli = create_button(text='Начать', disabled=False, parent=self)
        self.check_box_stimuli_record = check_box(self.params["stimuli"]["stimuli_with_record"], 'Запись', parent=self)
        self._stimuli_record = create_hbox([self.button_stimuli, self.check_box_stimuli_record])

        self.button_choose_stimuli = create_button(text='Выбрать', disabled=True, parent=self)
        self.label_stimuli = QLabel("", self)
        self._stimuli = create_hbox([self.button_choose_stimuli, self.label_stimuli])
        # self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)

        # --- Обработка эпох в приложении ---
        self._processing_frame = QFrame(self)
        self._label_aver_main = QLabel("Усреднение", self)
        self._label_aver = QLabel("Метод:", self)
        self.combo_box_aver = combo_box(self.params['aver_methods'], parent=self)
        self.button_aver = create_button('Ок', disabled=False, parent=self)
        self._aver_mode = create_hbox([self._label_aver, self.combo_box_aver, self.button_aver])

        self._label_lowpass_main = QLabel("Фильтр низких частот", self)
        self.check_box_lowpass = check_box(self.params["lowpass"], 'Исп?', parent=self)
        self.spin_box_lowpass = spin_box(min=1, max=2500, value=self.params["high_freq"], parent=self)
        _label_hz = QLabel("Гц", self)
        self.button_update_lowpass = create_button('Ок', disabled=False, parent=self)
        self._lowpass = create_hbox([self.check_box_lowpass, self.spin_box_lowpass, _label_hz, self.button_update_lowpass])
        
        self._label_reref_main = QLabel("Ре-референтация", self)
        self.check_box_rereference = check_box(self.params["rereference"], 'Исп?', parent=self)
        self.combo_box_rereference = checkable_combobox(self.channels, self.params['rereference_channel'], status=True, parent=self)
        self.button_update_rereference = create_button('Ок', disabled=False, parent=self)
        self._rereference = create_hbox([self.check_box_rereference, self.combo_box_rereference, self.button_update_rereference])

        self._label_baseline_main = QLabel("Вычетание бейзлайна", self)
        self.check_box_baseline = check_box(self.params['baseline'], 'Исп?', parent=self)
        self.spin_box_baseline_start = spin_box(-1000, self.params['baseline_end'], self.params['baseline_start'], step=10, parent=self)
        self.spin_box_baseline_end = spin_box(self.params['baseline_start'], 0, self.params['baseline_end'], step=10, parent=self)
        _label_start = QLabel("от", self)
        _label_end = QLabel("до", self)
        _label_ms = QLabel("мс", self)
        self._baseline_range = create_hbox([self.check_box_baseline,
                                            _label_start, self.spin_box_baseline_start, 
                                            _label_end, self.spin_box_baseline_end, _label_ms])

        label = QLabel("Метод:", self)
        self.combo_box_baseline = combo_box(self.params['baseline_methods'], parent=self)
        self.button_update_baseline = create_button('Ок', disabled=False, parent=self)
        self._baseline_mode = create_hbox([label, self.combo_box_baseline, self.button_update_baseline])

        self._label_CAR_main = QLabel("Common Average Reference", self)
        self.check_box_car = check_box(self.params['CAR'], 'Исп?', parent=self)
        self.button_car = create_button('Ок', disabled=False, parent=self)
        _label_car = QLabel("Каналы:")
        self.combo_box_channels = checkable_combobox(self.channels, self.params['bad_channels'], parent=self)
        self.combo_box_channels.setFixedWidth(70)
        self._car = create_hbox([self.check_box_car, _label_car, self.combo_box_channels, self.button_car])

        # delete!!!
        # _label3 = QLabel("Хранить", self)
        # self.spin_box_save_epoch = spin_box(0, self.params['n_max_save'], self.params['n_save'], parent=self, disabled=self.params['save_all'])
        # _label4 = QLabel("эпох.", self)
        # self.check_box_save_epoch = check_box(self.params['save_all'], 'все', parent=self, 
        #                 function=lambda: self.spin_box_save_epoch.setEnabled(not self.spin_box_save_epoch.isEnabled()))
        # self._save_epoch = create_hbox([_label3, self.spin_box_save_epoch, _label4, self.check_box_save_epoch])

        # self.check_box_aver_mode = check_box(self.params['aver_mode'], 'Усреднять по ', parent=self)
        # self.spin_box_aver_epoch = spin_box(0, 1000, self.params['n_aver'], parent=self, disabled=self.params['aver_all'])
        # _label6 = QLabel("эпохам.", self)
        # self.check_box_aver_epoch = check_box(self.params['aver_all'], 'всем', parent=self,
        #                 function=lambda: self.spin_box_aver_epoch.setEnabled(not self.spin_box_aver_epoch.isEnabled()))
        # self._aver_epoch = create_hbox([self.spin_box_aver_epoch, _label6, self.check_box_aver_epoch])


    def _setup_layout(self):
        self._setup_manager_frame()
        self._setup_processing_frame()

        layout = QVBoxLayout(self)

        layout.addWidget(self._manager_frame)
        layout.addWidget(self._processing_frame)
 

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


    def _setup_manager_frame(self):
        layout = QVBoxLayout(self._manager_frame)

        layout.addWidget(self._label_mode)
        layout.addLayout(self._mode)
        layout.addLayout(self._records_history)
        layout.addLayout(self._show_epoch)
        layout.addLayout(self._remove_epoch)
        layout.addWidget(self.button_restart)
        layout.addWidget(self.button_nvx_record)
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

    def _connect_signals(self):
        print("hi")
        
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


