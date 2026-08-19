from PyQt5.QtWidgets import QFrame,   QVBoxLayout, QLabel, QSizePolicy
from pathlib import Path

import os 
import json

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox
from utils.layout_utils import create_hbox


class ProcessingPanel(QFrame):
    """ --- Обработка эпох в приложении --- """

    def __init__(self, settings, settings_handler, channels, parent=None):
        super().__init__(parent)

        # self.setObjectName("settings_panel")    # для привязки стиля
        self.setObjectName("processing_panel")
        self.setStyleSheet("""
            QFrame#processing_panel {
                background-color: rgba(70, 90, 100, 51);
                border: 1px solid rgba(70, 90, 100, 80);
                border-radius: 6px;
            }
        """)
        self.setMinimumWidth(150)

        self.settings = settings
        self.settings_handler = settings_handler 
        self.channels = channels
        self._processing_presets = self._load_processing_presets()
        self._details_visible = True

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
        self._last_epoch_window_start = getattr(self.settings, "epoch_window_start_ms", -100)
        self._last_epoch_window_end = getattr(self.settings, "epoch_window_end_ms", 500)
        self._last_current_sampling_rate = getattr(self.settings, "current_sampling_rate_Hz", 5000)
        self._last_do_resampling = getattr(self.settings, "do_resampling", False)
        self._last_resample_freq = getattr(self.settings, "resample_freq_Hz", 2000)
        self._last_do_highpass_filtering = getattr(self.settings, "do_highpass_filtering", False)
        self._last_do_lowpass_filtering = self.settings.do_lowpass_filtering
        self._last_do_rereferencing = self.settings.do_rereferencing
        self._last_do_CAR_filtering = self.settings.do_CAR_filtering
        self._last_do_baseline_correction = self.settings.do_baseline_correction

        self._last_aver_method = self.settings.curr_aver_method
        self._last_highpass_freq = getattr(self.settings, "highpass_freq_Hz", 1)
        self._last_lowpass_freq = self.settings.lowpass_freq_Hz
        self._last_rereference_channel = self.settings.rereference_channel
        self._last_CAR_except_channels = self.settings.car_except_channels
        self._last_baseline_method = self.settings.curr_baseline_method
        self._last_baseline_from = self.settings.baseline_from_ms
        self._last_baseline_to = self.settings.baseline_to_ms

    def sync_last_state_from_ui(self):
        self._last_do_averaging = self.check_box_average.isChecked()
        self._last_use_eeg = self.check_box_use_eeg.isChecked()
        self._last_epoch_window_start = self.spin_box_epoch_window_start.value()
        self._last_epoch_window_end = self.spin_box_epoch_window_end.value()
        self._last_current_sampling_rate = self.spin_box_current_sampling_rate.value()
        self._last_do_resampling = self.check_box_resampling.isChecked()
        self._last_resample_freq = self.spin_box_resampling.value()
        self._last_do_highpass_filtering = self.check_box_highpass.isChecked()
        self._last_do_lowpass_filtering = self.check_box_lowpass.isChecked()
        self._last_do_rereferencing = self.check_box_rereference.isChecked()
        self._last_do_CAR_filtering = self.check_box_car.isChecked()
        self._last_do_baseline_correction = self.check_box_baseline.isChecked()

        self._last_aver_method = self.combo_box_aver.currentText()
        self._last_highpass_freq = self.spin_box_highpass.value()
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
        self.button_toggle_details = create_button('ОБРАБОТКА ▾', disabled=False, parent=self)
        self.combo_box_processing_preset = create_combo_box(
            items=["Custom"] + list(self._processing_presets.keys()),
            parent=self,
        )

        self.check_box_use_eeg = create_check_box(getattr(self.settings, "use_eeg", True), 'ЭЭГ', parent=self)

        self.check_box_average = create_check_box(self.settings.do_averaging, 'Усреднение', parent=self)
        self.combo_box_aver = create_combo_box(self.settings.aver_methods, curr_item=self.settings.curr_aver_method, parent=self)

        self.spin_box_epoch_window_start = create_spin_box(
            min=-10000,
            max=10000,
            value=getattr(self.settings, "epoch_window_start_ms", -100),
            step=10,
            parent=self,
        )
        self.spin_box_epoch_window_end = create_spin_box(
            min=-10000,
            max=10000,
            value=getattr(self.settings, "epoch_window_end_ms", 500),
            step=10,
            parent=self,
        )

        self.spin_box_current_sampling_rate = create_spin_box(
            min=1,
            max=100000,
            value=getattr(self.settings, "current_sampling_rate_Hz", 5000),
            step=250,
            parent=self,
        )

        self.check_box_resampling = create_check_box(
            getattr(self.settings, "do_resampling", False),
            'Resampling',
            parent=self,
        )
        self.spin_box_resampling = create_spin_box(
            min=1,
            max=100000,
            value=getattr(self.settings, "resample_freq_Hz", 2000),
            step=250,
            parent=self,
        )

        self.check_box_highpass = create_check_box(
            getattr(self.settings, "do_highpass_filtering", False),
            'ФВЧ',
            parent=self,
        )
        self.spin_box_highpass = create_spin_box(
            min=0.01,
            max=2500,
            value=getattr(self.settings, "highpass_freq_Hz", 1),
            data_type='float',
            step=0.5,
            decimals=2,
            parent=self,
        )

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

        layout_processing = create_hbox([
            self.button_toggle_details,
            self.combo_box_processing_preset,
        ])
        layout_use_eeg = create_hbox([self.check_box_use_eeg, self.button_processing])
        layout_aver_mode = create_hbox([self.check_box_average, self.combo_box_aver])
        layout_epoch_window = create_hbox([
            QLabel("Epoch", self),
            self.spin_box_epoch_window_start,
            QLabel("to", self),
            self.spin_box_epoch_window_end,
            QLabel("ms", self),
        ])
        layout_current_sampling = create_hbox([
            QLabel("Fs current", self),
            self.spin_box_current_sampling_rate,
            QLabel("Гц", self),
        ])
        layout_resampling = create_hbox([
            self.check_box_resampling,
            self.spin_box_resampling,
            QLabel("Гц", self),
        ])
        layout_highpass = create_hbox([self.check_box_highpass, self.spin_box_highpass, QLabel("Гц", self)])
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
        self._details_frame = QFrame(self)
        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(2)
        details_layout.addLayout(layout_aver_mode)                     # | _Усреднение: __mean__        |
        details_layout.addLayout(layout_epoch_window)
        details_layout.addLayout(layout_current_sampling)
        details_layout.addLayout(layout_resampling)
        details_layout.addLayout(layout_highpass)
        details_layout.addLayout(layout_lowpass)                       # | _ФНЧ:  _____ Гц              |
        details_layout.addLayout(layout_rereference)                   # | _Референт:  _____            |
        details_layout.addLayout(layout_car)                           # | _CAR кроме: _____            |
        # details_layout.addLayout(layout_ica)                         # | _CAR кроме: _____            |
        details_layout.addLayout(layout_baseline)                      # | _Baseline метод: __mean__    |

        layout = QVBoxLayout(self)                             # +------------------------------|
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        layout.addLayout(layout_processing)                    # | ОБРАБОТКА  пресет             |
        layout.addLayout(layout_use_eeg)                       # | _ЭЭГ  применить               |
        layout.addWidget(self._details_frame)
                                                               # | от __ до __ мс               |
                                                               # +------------------------------+


        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # =======================
    # =====   Сигналы    ====
    # =======================
    def _setup_connections(self):
        self.button_processing.clicked.connect(self._on_processing_button_click)
        self.button_toggle_details.clicked.connect(self._toggle_details)
        self.combo_box_processing_preset.currentTextChanged.connect(self._on_processing_preset_changed)
        self._button_update_ica.clicked.connect(self._update_ica_combobox)

    # =======================
    # =====   Логика    =====
    # =======================

    def _load_processing_presets(self):
        path = Path("resources/processing_presets.json")
        if not path.exists():
            return {}

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        presets = data.get("presets", data) if isinstance(data, dict) else {}
        if not isinstance(presets, dict):
            return {}

        return {
            name: self._normalize_processing_preset(preset)
            for name, preset in presets.items()
            if isinstance(preset, dict)
        }

    def _toggle_details(self):
        self._set_details_visible(not self._details_visible)

    def _set_details_visible(self, visible):
        self._details_visible = bool(visible)
        self._details_frame.setVisible(self._details_visible)
        self.button_toggle_details.setText("ОБРАБОТКА ▾" if self._details_visible else "ОБРАБОТКА ▸")
        self.adjustSize()
        self.updateGeometry()
        parent = self.parent()
        if parent is not None:
            self.move(max(0, parent.width() - self.width()), self.y())

    def _normalize_processing_preset(self, preset):
        aliases = {
            "highpass": "do_highpass_filtering",
            "low_freq": "highpass_freq_Hz",
            "lowpass": "do_lowpass_filtering",
            "high_freq": "lowpass_freq_Hz",
            "resampling": "do_resampling",
            "Fs_orig": "current_sampling_rate_Hz",
            "Fs": "resample_freq_Hz",
        }
        return {
            aliases.get(key, key): value
            for key, value in preset.items()
        }

    def _on_processing_preset_changed(self, preset_name):
        if preset_name == "Custom":
            return

        preset = self._processing_presets.get(preset_name)
        if not preset:
            return

        self._apply_processing_preset_to_ui(preset)

    def _apply_processing_preset_to_ui(self, preset):
        widget_by_key = {
            "use_eeg": self.check_box_use_eeg,
            "do_averaging": self.check_box_average,
            "curr_aver_method": self.combo_box_aver,
            "epoch_window_start_ms": self.spin_box_epoch_window_start,
            "epoch_window_end_ms": self.spin_box_epoch_window_end,
            "current_sampling_rate_Hz": self.spin_box_current_sampling_rate,
            "do_resampling": self.check_box_resampling,
            "resample_freq_Hz": self.spin_box_resampling,
            "do_highpass_filtering": self.check_box_highpass,
            "highpass_freq_Hz": self.spin_box_highpass,
            "do_lowpass_filtering": self.check_box_lowpass,
            "lowpass_freq_Hz": self.spin_box_lowpass,
            "do_rereferencing": self.check_box_rereference,
            "rereference_channel": self.combo_box_rereference,
            "do_CAR_filtering": self.check_box_car,
            "car_except_channels": self.combo_box_channels,
            "do_baseline_correction": self.check_box_baseline,
            "curr_baseline_method": self.combo_box_baseline,
            "baseline_from_ms": self.spin_box_baseline_from,
            "baseline_to_ms": self.spin_box_baseline_to,
            "apply_ICA": self.check_box_ica,
        }

        for key, value in preset.items():
            widget = widget_by_key.get(key)
            if widget is None:
                continue

            if hasattr(widget, "setChecked"):
                widget.setChecked(bool(value))
            elif hasattr(widget, "setCheckedItems"):
                widget.setCheckedItems(value)
            elif hasattr(widget, "setCurrentText"):
                widget.setCurrentText(str(value))
            elif hasattr(widget, "setValue"):
                widget.setValue(value)

    def _update_ica_combobox(self):
        # self.combo_box_ica.clear()
        folder = os.path.join(self.settings.ica_folder)
        print(self.settings.ica_folder)
        filenames = os.listdir(folder)
        filenames = [fl for fl in filenames if fl.find(".h5") != -1]
        self.combo_box_ica.addItems(filenames)


    def _on_processing_button_click(self):
        self.settings.apply_ICA = self.check_box_ica.isChecked()

        self.settings_handler.update_use_eeg(apply=False)
        self.settings_handler.update_sampling(apply=False)
        self.settings_handler.update_baseline(apply=False)
        self.settings_handler.update_highpass(apply=False)
        self.settings_handler.update_lowpass(apply=False)
        self.settings_handler.update_rereference(apply=False)
        self.settings_handler.update_CAR(apply=False)
        self.settings_handler.update_averaging(apply=False)

        if not self.settings.use_eeg and self.settings_handler.plot_updater is not None:
            self.settings_handler.plot_updater.clear_eeg_plots()

        self.settings_handler._apply(
            topoteps_draw=True,
            single_meps_draw=True,
            avg_teps_draw=True,
            avg_meps_draw=True,
        )
        self.sync_last_state_from_ui()


    def _finilize(self):
        self._update_ica_combobox()
