
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
        self.update_averaging(apply=False)
        self.update_baseline(apply=False)
        self.update_lowpass(apply=False)
        self.update_rereference(apply=False)
        self.update_CAR(apply=False)
        self.update_mode(apply=False)
        self.update_mode_data(apply=False)

        self._apply()


    # --- Averaging ---

    def update_averaging(self, apply=True):
        s = self.settings.processing_settings
        s.do_averaging = self.ui.check_box_average.isChecked()
        s.curr_aver_method = self.ui.combo_box_aver.currentText()

        self.data_processor.average_data = s.do_averaging
        self.data_processor.aver_method = s.curr_aver_method
        if self.data_processor.average_data:
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
        if self.data_processor.average_data:
            self.data_processor.create_average_functions()
        if apply:
            self._apply(topoteps_draw=True)

    def update_mode_data(self, idx=0, apply=True):
        # ["Новые данные", "Сравнение"]
        self.data_processor.process_new_data = (idx == 0)
        self.data_processor.reset_sessions()

        if self.data_processor.average_data:
            self.data_processor.create_average_functions()

        if apply:
            self._apply(topoteps_draw=True)

    # --- Common apply ---

    def _apply(self, topoteps_draw=False, single_meps_draw=False, avg_teps_draw=False, avg_meps_draw=False):
        self.data_processor.create_full_transform()
        if self.data_processor.average_data:
            self.data_processor.create_average_functions()
        if self.data_processor.average_tep_data:
            self.data_processor.create_average_functions()
        if len(self.data_processor._epochs) != 0:
            if topoteps_draw:
                self.plot_updater.update_topoteps(self.data_processor)
            if single_meps_draw:
                self.plot_updater.update_meps(self.data_processor)
            if avg_teps_draw:
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
        self._load_speed_settings_json()
        if hasattr(self.data_processor, "configure_speed"):
            self.data_processor.configure_speed()
        self.sync_ui_from_settings()

        self.update_averaging(apply=False)
        self.update_baseline(apply=False)
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
            attr = getattr(obj, key)
            if is_dataclass(attr):
                self._apply_dict_to_settings(attr, value)
            else:
                setattr(obj, key, value)

    def _load_speed_settings_json(self):
        path = Path(getattr(self.settings, "SPEED_settings_path", ""))
        if not path:
            return
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._apply_dict_to_settings(self.settings.speed, data)


    def sync_ui_from_settings(self):
        s = self.settings.processing_settings

        self.ui.check_box_average.setChecked(s.do_averaging)
        self.ui.combo_box_aver.setCurrentText(s.curr_aver_method)
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
