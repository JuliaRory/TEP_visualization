
from dataclasses import is_dataclass
import json
from dataclasses import asdict

class PlotSettingsHandler:
    """
    «Связующее звено» между UI и логикой:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): settings_plot
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings):
        self.settings = settings
        self.plot_updater = None
        self.ui = None
        self.ui_mep_dl = None # mep deepr look widget
    
    # def setu(self, plot_updater):
    #     self.plot_updater = plot_updater
    
    def setup_mep_dl(self, mep_dl_window):
        self.ui_mep_dl = mep_dl_window
    
    def update_mep_thr(self, thr):
        s = self.settings.meps_deeper_look
        s.thr = self.ui_mep_dl.spinbox_thr.value()
        
