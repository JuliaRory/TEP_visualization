from dataclasses import dataclass, field
from typing import List


# --- Plots ---

@dataclass
class Scale:
    xmin: int = -10
    xmax: int = 30
    ymin: int = -100
    ymax: int = 100

@dataclass
class TopoTEPsPlot:
    xmin: int = -10
    xmax: int = 30
    ymin: int = -100
    ymax: int = 100

@dataclass
class SingleMEPsPlot:
    xmin_ms: int = -20
    xmax_ms: int = 60
    max_amp_mV: float = 1
    n_plots: int = 5
    set_plot_ratio: float = 0.15
    amp_start_ms: int = 10
    amp_end_ms: int = 40

@dataclass
class SingleMEPsPlotDeeperLook:
    xmin_ms: int = -20
    xmax_ms: int = 60
    max_amp_mV: float = 1
    n_plots: int = 10
    set_plot_ratio: float = .15
    amp_start_ms: int = 10
    amp_end_ms: int = 40
    thr: float = .5
    n_plots_thr: int = 10

# @dataclass
# class ButtTEPsPlot:
#     amp: float = 100
#     units: str = "uV"
#     title: str = "Averaged TEP"
#     round: int = 0
#     channels_nearest_n: List[int] = field(default_factory=lambda: [9, 36, 42, 38, 37])
#     n_channels: int = 64

#     xmin_ms: int = -10
#     xmax_ms: int = 50
#     TEP: TEPBlock = field(default_factory=TEPBlock)
#     MEP: MEPBlock = field(default_factory=MEPBlock)
#     Fs: int = 5000
#     topo_butt_ratio: float = 0.4
#     n_plots: int = 3
#     timestamps_ms: List[int] = field(default_factory=lambda: [30, 55, 80])
#     channels_nearest: List[str] = field(default_factory=lambda: ["C3", "C5", "C1", "CP3", "FC3"])
#     topoplot: TopoplotSettings = field(default_factory=TopoplotSettings)


# @dataclass
# class ButtMEPsPlot:
#     amp: float = 1
#     units: str = "mV"
#     title: str = "Averaged MEP"
#     round: int = 1


# @dataclass
# class TopoPlot:
#     draw: bool = True
#     vmin: int = -15
#     vmax: int = 15
#     countours: int = 6
#     image_interp: str = "cubic"
#     sensors: bool = True
#     sphere: float = 0.5


# --- Root ---

@dataclass
class PlotSettings:

    scale: Scale = field(default_factory=Scale)

    topo_teps: TopoTEPsPlot = field(default_factory=TopoTEPsPlot)
    # butt_teps: ButtTEPsPlot = field(default_factory=ButtTEPsPlot)
    single_meps: SingleMEPsPlot = field(default_factory=SingleMEPsPlot)
    meps_deeper_look: SingleMEPsPlotDeeperLook = field(default_factory=SingleMEPsPlotDeeperLook)
    # butt_meps: ButtMEPsPlot = field(default_factory=ButtMEPsPlot)
    # topoplots = TopoPlot = field(default_factory=TopoPlot)

    channels: List[str] = field(default_factory=lambda: ['T7', 'TP9', 'P7', 'CP5', 'FT9', 'F7', 'FC5', 'F3', 'P3', 'C3', 'CP1', 'O1', 'Fp1',
                                                            'FC1', 'Fz', 'Fp2', 'Cz', 'FC2', 'CP2', 'Pz', 'O2', 'Oz', 'C4', 'P4', 'F4', 'FC6',
                                                            'F8', 'FT10', 'CP6', 'P8', 'T8', 'TP10', 'FT7', 'TP7', 'AF7', 'F5', 'C5', 'FC3',
                                                            'CP3', 'P5', 'PO3', 'PO7', 'C1', 'P1', 'AF3', 'F1', 'AF4', 'Fpz', 'FCz', 'F2', 'CPz',
                                                            'C2', 'POz', 'P2', 'PO8', 'PO4', 'P6', 'CP4', 'FC4', 'C6', 'F6', 'AF8', 'FT8', 'TP8'])
