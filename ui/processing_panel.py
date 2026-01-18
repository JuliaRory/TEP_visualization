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


class ProcessingPanel(QFrame):
    """ --- Обработка эпох в приложении --- """

    def __init__(self, settings, settings_handler, channels, parent=None):
        super().__init__(parent)

        self.setObjectName("settings_panel")    # для привязки стиля
        self.setMinimumWidth(150)

        self.settings = settings
        self.settings_handler = settings_handler 
        self.channels = channels

        self._init_ui()

    def _init_ui(self):   

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _init_state(self):
        """сохраняет начальное состояние настроек обработки данных
        для оперативного определения изменившихся параметров"""

        self._last_do_averaging = self.settings.do_averaging
        self._last_do_lowpass_filtering = self.settings.do_lowpass_filtering
        self._last_do_rereferencing = self.settings.do_rereferencing
        self._last_do_CAR_filtering = self.settings.do_CAR_filtering
        self._last_do_baseline_correction = self.settings.do_baseline_correction

        self._last_aver_method = self.settings.curr_aver_method
        self._last_lowpass_freq = self.settings.lowpass_freq_Hz
        self._last_rereference_channel = self.settings.rereference_channel
        self._last_CAR_except_channels = self.settings.car_except_channels
        self._last_baseline_method = self.settings.curr_baseline_method
        self._last_baseline_from = self.settings.baseline_from_ms
        self._last_baseline_to = self.settings.baseline_to_ms

    
    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        self.button_processing = create_button('Применить', disabled=False, parent=self)

        self.check_box_average = create_check_box(self.settings.do_averaging, 'Усреднение', parent=self)
        self.combo_box_aver = create_combo_box(self.settings.aver_methods, curr_item=self.settings.curr_aver_method, parent=self)

        self.check_box_lowpass = create_check_box(self.settings.do_lowpass_filtering, 'ФНЧ', parent=self)
        self.spin_box_lowpass = create_spin_box(min=1, max=2500, value=self.settings.lowpass_freq_Hz, parent=self)
        
        self.check_box_rereference = create_check_box(self.settings.do_rereferencing, 'Референт:', parent=self)
        self.combo_box_rereference = create_checkable_combobox(self.channels, self.settings.rereference_channel, status=True, parent=self)

        self.check_box_car = create_check_box(self.settings.do_CAR_filtering, 'CAR', parent=self)
        self.combo_box_channels = create_checkable_combobox(self.channels, self.settings.car_except_channels, w=70, parent=self)

        self.check_box_baseline = create_check_box(self.settings.do_baseline_correction, 'Бейзлайн', parent=self)
        self.spin_box_baseline_from = create_spin_box(-1000, self.settings.baseline_to_ms, self.settings.baseline_from_ms, step=10, parent=self)
        self.spin_box_baseline_to = create_spin_box(self.settings.baseline_from_ms, 0, self.settings.baseline_to_ms, step=10, parent=self)
        self.combo_box_baseline = create_combo_box(self.settings.baseline_methods, 
                                            curr_item=self.settings.curr_baseline_method,parent=self)

        
    # =======================
    # =====   LAYOUT    =====
    # =======================
    def _setup_layout(self):        

        layout_processing = create_hbox([QLabel("ОБРАБОТКА", self), self.button_processing])
        layout_aver_mode = create_hbox([self.check_box_average, self.combo_box_aver])
        layout_lowpass = create_hbox([self.check_box_lowpass, self.spin_box_lowpass, QLabel("Гц", self)])
        layout_rereference = create_hbox([self.check_box_rereference, self.combo_box_rereference])
        layout_car = create_hbox([self.check_box_car, QLabel("кроме:", self), self.combo_box_channels])
        layout_baseline_method = create_hbox([self.check_box_baseline, self.combo_box_baseline])
        layout_baseline_range = create_hbox([QLabel("от", self), self.spin_box_baseline_from, 
                                        QLabel("до", self), self.spin_box_baseline_to, QLabel("мс", self)
                                        ])
        layout_baseline = QVBoxLayout()
        layout_baseline.addLayout(layout_baseline_method)
        layout_baseline.addLayout(layout_baseline_range)
      
        
                                                               # Vertical layout
        layout = QVBoxLayout(self)                             # +------------------------------|
        layout.addLayout(layout_processing)                    # | ОБРАБОТКА ДАННЫХ  применить  |
        layout.addLayout(layout_aver_mode)                     # | _Усреднение: __mean__        |
        layout.addLayout(layout_lowpass)                       # | _ФНЧ:  _____ Гц              |
        layout.addLayout(layout_rereference)                   # | _Референт:  _____            |
        layout.addLayout(layout_car)                           # | _CAR кроме: _____            |
        layout.addLayout(layout_baseline)                      # | _Baseline метод: __mean__    |
                                                               # | от __ до __ мс               |
                                                               # +------------------------------+


        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_processing.clicked.connect(self._on_processing_button_click)

    # =======================
    # =====   Логика    =====
    # =======================

    def _on_processing_button_click(self):
        if ~are_equal(self.combo_box_aver.currentText(), self._last_aver_method):
            self._last_aver_method = self.combo_box_aver.currentText()
            self.settings_handler.update_averaging()
        
        if ~are_equal(self.spin_box_lowpass.value(), self._last_lowpass_freq):
            self._last_lowpass_freq = self.spin_box_lowpass.value()
            self.settings_handler.update_lowpass()
        
        if ~are_equal(self.combo_box_rereference.checkedItems(), self._last_rereference_channel):
            self._last_rereference_channel = self.combo_box_rereference.checkedItems()
            self.settings_handler.update_rereference()

        if ~are_equal(self.combo_box_channels.checkedItems(), self._last_CAR_except_channels):
            self._last_CAR_except_channels = self.combo_box_channels.checkedItems()
            self.settings_handler.update_CAR()

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
            self.settings_handler.update_baseline()
