from PyQt5.QtWidgets import QFrame,   QVBoxLayout, QLabel, QSizePolicy

import os 

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox
from utils.layout_utils import create_hbox
from utils.logic_helpers import are_equal


class ProcessingPanel(QFrame):
    """ --- Обработка эпох в приложении --- """

    def __init__(self, settings, settings_handler, channels, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
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
        self._last_use_eeg = getattr(self.settings, "use_eeg", True)
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

    def sync_last_state_from_ui(self):
        self._last_do_averaging = self.check_box_average.isChecked()
        self._last_use_eeg = self.check_box_use_eeg.isChecked()
        self._last_do_lowpass_filtering = self.check_box_lowpass.isChecked()
        self._last_do_rereferencing = self.check_box_rereference.isChecked()
        self._last_do_CAR_filtering = self.check_box_car.isChecked()
        self._last_do_baseline_correction = self.check_box_baseline.isChecked()

        self._last_aver_method = self.combo_box_aver.currentText()
        self._last_lowpass_freq = self.spin_box_lowpass.value()
        self._last_rereference_channel = self.combo_box_rereference.checkedItems()
        self._last_CAR_except_channels = self.combo_box_channels.checkedItems()
        self._last_baseline_method = self.combo_box_baseline.currentText()
        self._last_baseline_from = self.spin_box_baseline_from.value()
        self._last_baseline_to = self.spin_box_baseline_to.value()

    
    # =======================
    # =====     UI      =====
    # =======================
    def _setup_ui(self):
        
        self.button_processing = create_button('Применить', disabled=False, parent=self)

        self.check_box_use_eeg = create_check_box(getattr(self.settings, "use_eeg", True), 'Использовать EEG', parent=self)

        self.check_box_average = create_check_box(self.settings.do_averaging, 'Усреднение', parent=self)
        self.combo_box_aver = create_combo_box(self.settings.aver_methods, curr_item=self.settings.curr_aver_method, parent=self)

        self.check_box_lowpass = create_check_box(self.settings.do_lowpass_filtering, 'ФНЧ', parent=self)
        self.spin_box_lowpass = create_spin_box(min=1, max=2500, value=self.settings.lowpass_freq_Hz, parent=self)
        
        self.check_box_rereference = create_check_box(self.settings.do_rereferencing, 'Референт:', parent=self)
        self.combo_box_rereference = create_checkable_combobox(self.channels, self.settings.rereference_channel, status=True, parent=self)

        self.check_box_car = create_check_box(self.settings.do_CAR_filtering, 'CAR', parent=self)
        self.combo_box_channels = create_checkable_combobox(self.channels, self.settings.car_except_channels, w=70, parent=self)

        self.check_box_ica = create_check_box(self.settings.apply_ICA, 'ICA')
        self.combo_box_ica = create_combo_box([])
        self._button_update_ica = create_button(text='⟳', disabled=False, w=30)

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
        layout_use_eeg = create_hbox([self.check_box_use_eeg])
        layout_aver_mode = create_hbox([self.check_box_average, self.combo_box_aver])
        layout_lowpass = create_hbox([self.check_box_lowpass, self.spin_box_lowpass, QLabel("Гц", self)])
        layout_rereference = create_hbox([self.check_box_rereference, self.combo_box_rereference])
        layout_car = create_hbox([self.check_box_car, QLabel("кроме:", self), self.combo_box_channels])
        layout_ica = create_hbox([self.check_box_ica, self.combo_box_ica, self._button_update_ica])
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
        layout.addLayout(layout_use_eeg)                       # | _Использовать EEG             |
        layout.addLayout(layout_aver_mode)                     # | _Усреднение: __mean__        |
        layout.addLayout(layout_lowpass)                       # | _ФНЧ:  _____ Гц              |
        layout.addLayout(layout_rereference)                   # | _Референт:  _____            |
        layout.addLayout(layout_car)                           # | _CAR кроме: _____            |
        # layout.addLayout(layout_ica)                           # | _CAR кроме: _____            |
        layout.addLayout(layout_baseline)                      # | _Baseline метод: __mean__    |
                                                               # | от __ до __ мс               |
                                                               # +------------------------------+


        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_processing.clicked.connect(self._on_processing_button_click)
        self._button_update_ica.clicked.connect(self._update_ica_combobox)

    # =======================
    # =====   Логика    =====
    # =======================

    def _update_ica_combobox(self):
        # self.combo_box_ica.clear()
        folder = os.path.join(self.settings.ica_folder)
        print(self.settings.ica_folder)
        filenames = os.listdir(folder)
        filenames = [fl for fl in filenames if fl.find(".h5") != -1]
        self.combo_box_ica.addItems(filenames)


    def _on_processing_button_click(self):
        is_use_eeg_changed = not are_equal(self.check_box_use_eeg.isChecked(), self._last_use_eeg)
        if is_use_eeg_changed:
            self._last_use_eeg = self.check_box_use_eeg.isChecked()
            self.settings_handler.update_use_eeg()

        is_averaging_changed = not are_equal(self.check_box_average.isChecked(), self._last_do_averaging)
        is_aver_method_changed = not are_equal(self.combo_box_aver.currentText(), self._last_aver_method)
        if is_averaging_changed:
            self._last_do_averaging = self.check_box_average.isChecked()
        if is_aver_method_changed:
            self._last_aver_method = self.combo_box_aver.currentText()
        if is_averaging_changed or is_aver_method_changed:
            self.settings_handler.update_averaging()
        
        is_lowpass_changed = not are_equal(self.check_box_lowpass.isChecked(), self._last_do_lowpass_filtering)
        is_lowpass_freq_changed = not are_equal(self.spin_box_lowpass.value(), self._last_lowpass_freq)
        if is_lowpass_changed:
            self._last_do_lowpass_filtering = self.check_box_lowpass.isChecked()
        if is_lowpass_freq_changed:
            self._last_lowpass_freq = self.spin_box_lowpass.value()
        if is_lowpass_changed or is_lowpass_freq_changed:
            self.settings_handler.update_lowpass()
        
        is_rereference_changed = not are_equal(self.check_box_rereference.isChecked(), self._last_do_rereferencing)
        is_rereference_channels_changed = not are_equal(self.combo_box_rereference.checkedItems(), self._last_rereference_channel)
        if is_rereference_changed:
            self._last_do_rereferencing = self.check_box_rereference.isChecked()
        if is_rereference_channels_changed:
            self._last_rereference_channel = self.combo_box_rereference.checkedItems()
        if is_rereference_changed or is_rereference_channels_changed:
            self.settings_handler.update_rereference()

        is_car_changed = not are_equal(self.check_box_car.isChecked(), self._last_do_CAR_filtering)
        is_car_channels_changed = not are_equal(self.combo_box_channels.checkedItems(), self._last_CAR_except_channels)
        if is_car_changed:
            self._last_do_CAR_filtering = self.check_box_car.isChecked()
        if is_car_channels_changed:
            self._last_CAR_except_channels = self.combo_box_channels.checkedItems()
        if is_car_changed or is_car_channels_changed:
            self.settings_handler.update_CAR()

        is_baseline_changed = not are_equal(self.check_box_baseline.isChecked(), self._last_do_baseline_correction)
        is_baseline_method_changed = not are_equal(self.combo_box_baseline.currentText(), self._last_baseline_method)
        is_baseline_from_changed = not are_equal(self.spin_box_baseline_from.value(), self._last_baseline_from)
        is_baseline_to_changed = not are_equal(self.spin_box_baseline_to.value(), self._last_baseline_to)
        
        if is_baseline_changed:
            self._last_do_baseline_correction = self.check_box_baseline.isChecked()
        if is_baseline_method_changed:
            self._last_baseline_method = self.combo_box_baseline.currentText()
        if is_baseline_from_changed:
            self._last_baseline_from = self.spin_box_baseline_from.value()
        if is_baseline_to_changed:
            self._last_baseline_to = self.spin_box_baseline_to.value()

        if is_baseline_changed or is_baseline_method_changed or is_baseline_from_changed or is_baseline_to_changed:
            self.settings_handler.update_baseline()


    def _finilize(self):
        self._update_ica_combobox()
