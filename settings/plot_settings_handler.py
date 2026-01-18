
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
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings):
        self.settings = settings
        self.plot_updater = None
        self.ui = None
    
    def setupUI(self, plot_updater):
        self.plot_updater = plot_updater
