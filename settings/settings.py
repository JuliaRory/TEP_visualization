from dataclasses import dataclass

@dataclass
class AveragingSettings:
    enable: bool = True
    n_epochs: int = 10

@dataclass
class FilterSettings:
    apply_baseline: bool = True
    lowpass_freq: float = 40.0
    rereference: str = "None"

@dataclass
class PlotSettings:
    show_topomap: bool = True
    scale_ymax: float = 10.0
    scale_ymin: float = -10.0

@dataclass
class Settings:
    """объект-хранилище настроек"""
    averaging: AveragingSettings = AveragingSettings()
    filters: FilterSettings = FilterSettings()
    plot: PlotSettings = PlotSettings()