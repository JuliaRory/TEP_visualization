
from dataclasses import is_dataclass
import json
from dataclasses import asdict
from PyQt5.QtCore import pyqtSignal

class PlotSettingsHandler:
    """
    «Связующее звено» между UI и логикой:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater, чтобы применить новые настройки

    Args:
        settings(Settings): settings_plot
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings):
        self.settings = settings
        self.plot_updater = None
        self.ui_overview_panel = None
        self.ui_mep_dl = None # mep deepr look widget
        self.ui_center_panel = None
        self.ui_mep_panel = None
    
    def setup_plot_updater(self, data_processor, plot_updater):
        self.plot_updater = plot_updater
        self.data_processor = data_processor
    
    def setup_mep_dl(self, mep_dl_window):
        self.ui_mep_dl = mep_dl_window

    def setup_overview_panel(self, overview_panel):
        self.ui_overview_panel = overview_panel
        self._setup_connections()

        self._update_averaging_teps()
    
    def _setup_connections(self):
        self.ui_overview_panel.checkbox_average_teps.toggled.connect(self._update_averaging_teps)
        self.ui_overview_panel.checkbox_average_meps.toggled.connect(self._update_averaging_meps)
    
    def _update_averaging_teps(self):
        s = self.settings.overview_panel.butts_plot.TEP
        s.do_averaging = self.ui_overview_panel.checkbox_average_teps.isChecked()

        self.data_processor.update_avg_tep(s.do_averaging)

        if len(self.data_processor._epochs) != 0:
            self.plot_updater.update_avg_teps(self.data_processor)
    
    def _update_averaging_meps(self):
        s = self.settings.overview_panel.butts_plot.MEP
        s.do_averaging = self.ui_overview_panel.checkbox_average_meps.isChecked()

        self.data_processor.update_avg_mep(s.do_averaging)

        if len(self.data_processor._epochs) != 0:
            self.plot_updater.update_avg_meps(self.data_processor)

    def update_mep_thr(self, thr):
        s = self.settings.meps_deeper_look
        s.thr = self.ui_mep_dl.spinbox_thr.value()
        
