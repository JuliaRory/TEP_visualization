import importlib

def _lazy_import(name, module):
    """Создаёт функцию-фабрику для ленивого импорта класса"""
    def factory(*args, **kwargs):
        mod = importlib.import_module(f".{module}", package=__name__)
        cls = getattr(mod, name)
        return cls(*args, **kwargs)
    return factory


# Определяем все панели как ленивые функции
SettingsPanel = _lazy_import("SettingsPanel", "settings_panel")
ProcessingPanel = _lazy_import("ProcessingPanel", "processing_panel")
NVXControlPanel = _lazy_import("NVXControlPanel", "nvx_control_panel")
StimuliControlPanel = _lazy_import("StimuliControlPanel", "stimuli_control_panel")
SurveyPanel = _lazy_import("SurveyPanel", "survey_panel")
TopoTEPsPanel = _lazy_import("TopoTEPsPanel", "topo_teps_panel")
overviewPanel = _lazy_import("overviewPanel", "overview_panel")
MEPsPanel = _lazy_import("MEPsPanel", "meps_panel")
