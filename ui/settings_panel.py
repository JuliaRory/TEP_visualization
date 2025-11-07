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
        
        self.button_restart = create_button(text='Начать заново', checkable=False, parent=self)
        # self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)
        
        self.button_show_epoch = create_button('Показать эпоху', checkable=False, parent=self)
        self.spin_box_show_epoch = spin_box(0, 0, 0, parent=self)
        self._show_epoch = create_hbox([self.button_show_epoch, self.spin_box_show_epoch])

        self.button_remove_epoch = create_button('Удалить эпоху', checkable=False, parent=self)
        self.spin_box_remove_epoch =spin_box(0, 0, 0, parent=self)
        self._remove_epoch = create_hbox([self.button_remove_epoch, self.spin_box_remove_epoch])

        _label3 = QLabel("Хранить", self)
        self.spin_box_save_epoch = spin_box(0, self.params['n_max_save'], self.params['n_save'], parent=self, disabled=self.params['save_all'])
        _label4 = QLabel("эпох.", self)
        self.check_box_save_epoch = check_box(self.params['save_all'], 'все', parent=self, 
                        function=lambda: self.spin_box_save_epoch.setEnabled(not self.spin_box_save_epoch.isEnabled()))
        self._save_epoch = create_hbox([_label3, self.spin_box_save_epoch, _label4, self.check_box_save_epoch])

        self.check_box_aver_mode = check_box(self.params['aver_mode'], 'Усреднять по ', parent=self)
        self.spin_box_aver_epoch = spin_box(0, 1000, self.params['n_aver'], parent=self, disabled=self.params['aver_all'])
        _label6 = QLabel("эпохам.", self)
        self.check_box_aver_epoch = check_box(self.params['aver_all'], 'всем', parent=self,
                        function=lambda: self.spin_box_aver_epoch.setEnabled(not self.spin_box_aver_epoch.isEnabled()))
        self._aver_epoch = create_hbox([self.spin_box_aver_epoch, _label6, self.check_box_aver_epoch])

        self._label7 = QLabel("Метод усреднения:", self)
        self.combo_box_aver = combo_box(self.params['aver_methods'], parent=self)
        self.button_aver = create_button('Ок', checkable=True, parent=self)
        self._aver_mode = create_hbox([self.combo_box_aver, self.button_aver])

        self.check_box_lowpass = check_box(self.params["lowpass"], 'lowpass', parent=self)
        self.spin_box_lowpass = spin_box(min=1, max=2500, value=self.params["high_freq"], parent=self)
        _label_hz = QLabel("Гц", self)
        self.button_update_lowpass = create_button('Ок', checkable=True, parent=self)
        self._lowpass = create_hbox([self.spin_box_lowpass, _label_hz, self.button_update_lowpass])
        
        self.check_box_rereference = check_box(self.params["rereference"], 're-reference', parent=self)
        self.combo_box_rereference = checkable_combobox(self.channels, self.params['rereference_channel'], status=True, parent=self)
        self.button_update_rereference = create_button('Ок', checkable=True, parent=self)
        self._rereference = create_hbox([self.combo_box_rereference, self.button_update_rereference])

        self.check_box_baseline = check_box(self.params['baseline'], 'Бейзлайн', parent=self)
        self.combo_box_baseline = combo_box(self.params['baseline_methods'], parent=self)
        self.button_update_baseline = create_button('Ок', checkable=True, parent=self)
        self._baseline_mode = create_hbox([self.combo_box_baseline, self.button_update_baseline])

        self.spin_box_baseline_start = spin_box(-1000, self.params['baseline_end'], self.params['baseline_start'], step=10, parent=self)
        self.spin_box_baseline_end = spin_box(self.params['baseline_start'], 0, self.params['baseline_end'], step=10, parent=self)
        _label_start = QLabel("от", self)
        _label_end = QLabel("до", self)
        _label_ms = QLabel("мс", self)
        self._baseline_range = create_hbox([_label_start, self.spin_box_baseline_start, _label_end, self.spin_box_baseline_end, _label_ms])

        self.check_box_car = check_box(self.params['CAR'], 'Common Average Reference', parent=self)
        self.button_car = create_button('Ок', checkable=True, parent=self)
        _label_car = QLabel("Использовать каналы:")
        self.combo_box_channels = checkable_combobox(self.channels, self.params['bad_channels'], parent=self)
        self.combo_box_channels.setFixedWidth(70)
        self._car = create_hbox([self.combo_box_channels, self.button_car])

    def _setup_layout(self):
        layout = QVBoxLayout(self)

        layout.addWidget(self.button_restart)
        layout.addLayout(self._show_epoch)
        layout.addLayout(self._remove_epoch)
        layout.addLayout(self._save_epoch)

        layout.addWidget(self.check_box_aver_mode)
        layout.addLayout(self._aver_epoch)

        layout.addWidget(self._label7)
        layout.addLayout(self._aver_mode)
        

        layout.addWidget(self.check_box_lowpass)
        layout.addLayout(self._lowpass)
        
        layout.addWidget(self.check_box_rereference)
        layout.addLayout(self._rereference)

        layout.addWidget(self.check_box_baseline)
        layout.addLayout(self._baseline_range)
        layout.addLayout(self._baseline_mode)
        
        layout.addWidget(self.check_box_car)
        layout.addLayout(self._car)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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
