
from dataclasses import is_dataclass
import json
from dataclasses import asdict
from pathlib import Path

class SettingsHandler:
    """
    «Связующее звено» между UI и логикой processing:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings, data_processor):
        self.data_processor = data_processor
        self.settings = settings
        self.plot_updater = None
        self.ui = None

    def setupUI(self, processing_panel, plot_updater):
        self.ui = processing_panel
        self.plot_updater = plot_updater

        self.configure_data_processor()

    # -- Configure data processor --
    def configure_data_processor(self):
        # configure data processor according to current settings
        self.update_sampling(apply=False)
        self.update_use_eeg(apply=False)
        self.update_averaging(apply=False)
        self.update_baseline(apply=False)
        self.update_highpass(apply=False)
        self.update_lowpass(apply=False)
        self.update_rereference(apply=False)
        self.update_CAR(apply=False)
        self.update_mode(apply=False)
        self.update_mode_data(apply=False)

        self._apply()


    # --- Averaging ---

    def update_use_eeg(self, apply=True):
        s = self.settings.processing_settings
        s.use_eeg = self.ui.check_box_use_eeg.isChecked()
        self.data_processor.configure_use_eeg(s.use_eeg)
        if apply:
            if s.use_eeg:
                self._apply(topoteps_draw=True, avg_teps_draw=True)
            else:
                if self.plot_updater is not None and hasattr(self.plot_updater, "clear_eeg_plots"):
                    self.plot_updater.clear_eeg_plots()
                self._apply()

    def update_averaging(self, apply=True):
        s = self.settings.processing_settings
        s.do_averaging = self.ui.check_box_average.isChecked()
        s.curr_aver_method = self.ui.combo_box_aver.currentText()

        self.data_processor.average_data = s.do_averaging
        self.data_processor.aver_method = s.curr_aver_method
        if self.data_processor.use_eeg and self.data_processor.average_data:
            self.data_processor.create_average_functions()

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True, avg_meps_draw=True)

    # --- Baseline ---

    def update_baseline(self, apply=True):
        s = self.settings.processing_settings

        s.do_baseline_correction = self.ui.check_box_baseline.isChecked()
        s.baseline_from_ms = self.ui.spin_box_baseline_from.value()
        s.baseline_to_ms = self.ui.spin_box_baseline_to.value()
        s.curr_baseline_method = self.ui.combo_box_baseline.currentText()

        self.data_processor.configure_baseline(
            enabled=s.do_baseline_correction,
            t_from=s.baseline_from_ms,
            t_to=s.baseline_to_ms,
            method=s.curr_baseline_method,
        )

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True, avg_meps_draw=True)

    # --- Sampling ---

    def update_sampling(self, apply=True):
        s = self.settings.processing_settings
        s.epoch_window_start_ms = self.ui.spin_box_epoch_window_start.value()
        s.epoch_window_end_ms = self.ui.spin_box_epoch_window_end.value()
        s.current_sampling_rate_Hz = self.ui.spin_box_current_sampling_rate.value()
        s.do_resampling = self.ui.check_box_resampling.isChecked()
        s.resample_freq_Hz = self.ui.spin_box_resampling.value()

        self.data_processor.configure_sampling()
        if self.plot_updater is not None and hasattr(self.plot_updater, "_sync_plot_timebase"):
            self.plot_updater._sync_plot_timebase(self.data_processor)
        self.update_baseline(apply=False)
        self.update_highpass(apply=False)
        self.update_lowpass(apply=False)

        if apply:
            self._apply(
                topoteps_draw=True,
                single_meps_draw=True,
                avg_teps_draw=True,
                avg_meps_draw=True,
            )

    # --- Highpass ---

    def update_highpass(self, apply=True):
        s = self.settings.processing_settings
        s.do_highpass_filtering = self.ui.check_box_highpass.isChecked()
        s.highpass_freq_Hz = self.ui.spin_box_highpass.value()

        self.data_processor.configure_highpass(
            enabled=s.do_highpass_filtering,
            freq=s.highpass_freq_Hz,
        )

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True)

    # --- Lowpass ---

    def update_lowpass(self, apply=True):
        s = self.settings.processing_settings
        s.do_lowpass_filtering = self.ui.check_box_lowpass.isChecked()
        s.lowpass_freq_Hz = self.ui.spin_box_lowpass.value()

        self.data_processor.configure_lowpass(
            enabled=s.do_lowpass_filtering,
            freq=s.lowpass_freq_Hz,
        )

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True)

    # --- Rereference ---

    def update_rereference(self, apply=True):
        s = self.settings.processing_settings
        s.do_rereferencing = self.ui.check_box_rereference.isChecked()
        s.rereference_channel = self.ui.combo_box_rereference.checkedItems()

        self.data_processor.configure_rereference(
            enabled=s.do_rereferencing,
            channels=s.rereference_channel,
        )

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True)

    # --- CAR ---

    def update_CAR(self, apply=True):
        s = self.settings.processing_settings
        s.do_CAR_filtering = self.ui.check_box_car.isChecked()
        s.car_except_channels = self.ui.combo_box_channels.checkedItems()

        self.data_processor.configure_car(
            enabled=s.do_CAR_filtering,
            channels=s.car_except_channels,
        )

        if apply:
            self._apply(topoteps_draw=True, avg_teps_draw=True)

    # --- Modes ---

    def update_mode(self, idx=1, apply=True):
        # ["Усреднение", "Одиночные пробы"]
        self.data_processor.average_data = (idx == 0)
        if self.data_processor.use_eeg and self.data_processor.average_data:
            self.data_processor.create_average_functions()
        if apply:
            self._apply(topoteps_draw=True)

    def update_mode_data(self, idx=0, apply=True):
        # ["Новые данные", "Сравнение"]
        self.data_processor.process_new_data = (idx == 0)
        self.data_processor.reset_sessions()

        if self.data_processor.use_eeg and self.data_processor.average_data:
            self.data_processor.create_average_functions()

        if apply:
            self._apply(topoteps_draw=True)

    # --- Common apply ---

    def _apply(self, topoteps_draw=False, single_meps_draw=False, avg_teps_draw=False, avg_meps_draw=False):
        self.data_processor.create_full_transform()
        use_eeg = getattr(self.data_processor, "use_eeg", True)
        if use_eeg and self.data_processor.average_data:
            self.data_processor.create_average_functions()
        if use_eeg and self.data_processor.average_tep_data:
            self.data_processor.create_average_functions()
        if len(self.data_processor._epochs) != 0:
            if use_eeg and topoteps_draw:
                self.plot_updater.update_topoteps(self.data_processor)
            if single_meps_draw:
                self.plot_updater.update_meps(self.data_processor)
            if use_eeg and avg_teps_draw:
                self.plot_updater.update_avg_teps(self.data_processor)
            if avg_meps_draw:
                self.plot_updater.update_avg_meps(self.data_processor)


    def load_from_json(self, path=None, default=True):
        if default:
            path = r"data/settings/processing_default.json"

        import os
        if not os.path.exists(path):
            print(f"{path} does not exist.")
            return 
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._apply_dict_to_settings(self.settings, data)
        self.sync_ui_from_settings()

        self.update_sampling(apply=False)
        self.update_use_eeg(apply=False)
        self.update_averaging(apply=False)
        self.update_baseline(apply=False)
        self.update_highpass(apply=False)
        self.update_lowpass(apply=False)
        self.update_rereference(apply=False)
        self.update_CAR(apply=False)
        self._apply()
        if len(self.data_processor._epochs) != 0:
            self.plot_updater.update_plots(self.data_processor)

    
    def save_to_json(self, path=None, default=True):
        if default:
            path = r"data/settings/processing_default.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.settings), f, indent=4, ensure_ascii=False)
        
    
    def _apply_dict_to_settings(self, obj, data: dict):
        for key, value in data.items():
            if not hasattr(obj, key):
                continue
            attr = getattr(obj, key)
            if is_dataclass(attr):
                self._apply_dict_to_settings(attr, value)
            else:
                setattr(obj, key, value)

    def save_speed_settings_to_json(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self.settings.speed), f, indent=4, ensure_ascii=False)
        return path


    def sync_ui_from_settings(self):
        s = self.settings.processing_settings

        self.ui.check_box_average.setChecked(s.do_averaging)
        self.ui.check_box_use_eeg.setChecked(getattr(s, "use_eeg", True))
        self.ui.combo_box_aver.setCurrentText(s.curr_aver_method)
        self.ui.spin_box_epoch_window_start.setValue(getattr(s, "epoch_window_start_ms", -100))
        self.ui.spin_box_epoch_window_end.setValue(getattr(s, "epoch_window_end_ms", 500))
        self.ui.spin_box_current_sampling_rate.setValue(getattr(s, "current_sampling_rate_Hz", 5000))
        self.ui.check_box_resampling.setChecked(getattr(s, "do_resampling", False))
        self.ui.spin_box_resampling.setValue(getattr(s, "resample_freq_Hz", 2000))
        self.ui.check_box_highpass.setChecked(getattr(s, "do_highpass_filtering", False))
        self.ui.spin_box_highpass.setValue(getattr(s, "highpass_freq_Hz", 1))
        self.ui.check_box_lowpass.setChecked(s.do_lowpass_filtering)
        self.ui.spin_box_lowpass.setValue(s.lowpass_freq_Hz)
        
        self.ui.check_box_rereference.setChecked(s.do_rereferencing)
        self.ui.combo_box_rereference.setCheckedItems(s.rereference_channel)

        self.ui.check_box_car.setChecked(s.do_CAR_filtering)
        self.ui.combo_box_channels.setCheckedItems(s.car_except_channels)

        self.ui.check_box_baseline.setChecked(s.do_baseline_correction)
        self.ui.spin_box_baseline_from.setValue(s.baseline_from_ms)
        self.ui.spin_box_baseline_to.setValue(s.baseline_to_ms)
        self.ui.combo_box_baseline.setCurrentText(s.curr_baseline_method)

        self.ui.sync_last_state_from_ui()
