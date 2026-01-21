
from dataclasses import is_dataclass
import json
from dataclasses import asdict

class NVXSettingsHandler:
    """
    «Связующее звено» между UI и логикой:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings):
        self.settings = settings
        self.ui = None

    def setupUI(self, nvx_control_panel):
        self.ui = nvx_control_panel

        self.configure_data_processor()

    
    # def _connect_ui(self):
        
        # self.ui.check_box_average.toggled.connect(self.update_averaging)
        # self.combo_box_aver.currentIndexChanged.connect(self.update_averaging)

        # self.ui.check_box_baseline.toggled.connect(self.update_baseline)
        # self.ui.spin_box_baseline_from.valueChanged.connect(self.update_baseline)
        # self.ui.spin_box_baseline_to.valueChanged.connect(self.update_baseline)
        # self.combo_box_baseline.currentIndexChanged.connect(self.update_baseline)

        # self.ui.check_box_lowpass.toggled.connect(self.update_lowpass)
        # self.ui.spin_box_lowpass.valueChanged.connect(self.update_lowpass)

        # self.ui.check_box_rereference.toggled.connect(self.update_rereference)

        # self.ui.check_box_car.toggled.connect(self.update_CAR)

        # self.ui.combo_box_mode.currentIndexChanged.connect(self.update_mode)
        # self.ui.combo_box_mode_data.currentIndexChanged.connect(self.update_mode_data)
    
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

        self.data_processor.average_data = s.do_averaging
        if self.data_processor.average_data:
            self.data_processor.create_average_functions()

        if apply:
            self._apply()

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
            self._apply()

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
            self._apply()

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
            self._apply()

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
            self._apply()

    # --- Modes ---

    def update_mode(self, idx=1, apply=True):
        # ["Усреднение", "Одиночные пробы"]
        self.data_processor.average_data = (idx == 0)
        if self.data_processor.average_data:
            self.data_processor.create_average_functions()
        if apply:
            self._apply()

    def update_mode_data(self, idx=0, apply=True):
        # ["Новые данные", "Сравнение"]
        self.data_processor.process_new_data = (idx == 0)
        self.data_processor.reset_sessions()

        if self.data_processor.average_data:
            self.data_processor.create_average_functions()

        if apply:
            self._apply()

    # --- Common apply ---

    def _apply(self):
        self.data_processor.create_full_transform()
        if len(self.data_processor._epochs) != 0:
            self.plot_updater.update_plots(self.data_processor)


    def load_from_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._apply_dict_to_settings(self.settings, data)
        self.sync_ui_from_settings()

        self.data_processor.create_full_transform()
        self.plot_updater.update_plots(self.data_processor)
    
    
    def save_to_json(self, path):
        # сделать сохранение настроек по закрытию программы и потом открытие последней версии настроек 
        # плюс сброс до дефолтных настроек
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.settings), f, indent=4, ensure_ascii=False)
        
    
    def _apply_dict_to_settings(self, obj, data: dict):
        for key, value in data.items():
            attr = getattr(obj, key)
            if is_dataclass(attr):
                self._apply_dict_to_settings(attr, value)
            else:
                setattr(obj, key, value)
            

    def sync_ui_from_settings(self):
        s = self.settings.processing_settings
        self.ui.check_box_averaging.setChecked(s.do_averaging)
        self.ui.check_box_baseline.setChecked(s.do_baseline_correction)
        self.ui.spin_box_baseline_from.setValue(s.baseline_from_ms)
        self.ui.spin_box_baseline_to.setValue(s.baseline_to_ms)