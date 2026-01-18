from dataclasses import dataclass, field
from typing import List


# --- Processing ---

@dataclass
class ProcessingSettings:
    do_averaging: bool = False
    do_lowpass_filtering: bool = True
    do_rereferencing: bool = False
    do_CAR_filtering: bool = True
    do_baseline_correction: bool = True

    aver_methods: List[str] = field(default_factory=lambda: ["mean", "median", "trimmean"])
    curr_aver_method: str = "mean"

    lowpass_freq_Hz: int = 250

    rereference_channel: List[str] = field(default_factory=lambda: ["Fz"])
    car_except_channels: List[str] = field(default_factory=lambda: ["FT9", "FT10", "TP9", "TP10"])

    baseline_methods: List[str] = field(default_factory=lambda: ["mean", "median"])
    curr_baseline_method: str = "mean"
    baseline_from_ms: int = -75
    baseline_to_ms: int = -20


# --- Record ---

@dataclass
class RecordSettings:
    bat_file: str = "D:/Resonance/distro-dual/msvc/control.bat"
    bat_file_home: str = "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/dist_2024_11_13_imp/control.bat"
    activate_bat: bool = False
    service_name: str = "nvx136"
    records_folder: str = "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/TEP_visualization/data/records"


# --- Stimuli ---

@dataclass
class StimuliSettings:
    monitor: int = 3
    stimuli_with_record: bool = True
    stimuli_filename: str = "resources/saved_stimuli.json"
    video_folder: str = "resources/videoSamples"
    volume: int = 80


# --- Plots ---

@dataclass
class Scale:
    xmin: int = -10
    xmax: int = 30
    ymin: int = -100
    ymax: int = 100

@dataclass
class TopoTEPsPlotSettings:
    scale: Scale = field(default_factory=Scale)

@dataclass
class MEPPlotSettings:
    xmin_ms: int = -20
    xmax_ms: int = 60
    max_amp_mV: float = 1
    Fs: int = 5000
    n_plots: int = 5
    set_plot_ratio: float = 0.15
    amp_start_ms: int = 10
    amp_end_ms: int = 40

@dataclass
class TEPBlock:
    amp: float = 100
    units: str = "uV"
    title: str = "Averaged TEP"
    round: int = 0
    channels_nearest_n: List[int] = field(default_factory=lambda: [9, 36, 42, 38, 37])
    n_channels: int = 64


@dataclass
class MEPBlock:
    amp: float = 1
    units: str = "mV"
    title: str = "Averaged MEP"
    round: int = 1


@dataclass
class TopoplotSettings:
    draw: bool = True
    vmin: int = -15
    vmax: int = 15
    countours: int = 6
    image_interp: str = "cubic"
    sensors: bool = True
    sphere: float = 0.5


@dataclass
class TEPSupplPlotSettings:
    xmin_ms: int = -10
    xmax_ms: int = 50
    TEP: TEPBlock = field(default_factory=TEPBlock)
    MEP: MEPBlock = field(default_factory=MEPBlock)
    Fs: int = 5000
    topo_butt_ratio: float = 0.4
    n_plots: int = 3
    timestamps_ms: List[int] = field(default_factory=lambda: [30, 55, 80])
    channels_nearest: List[str] = field(default_factory=lambda: ["C3", "C5", "C1", "CP3", "FC3"])
    topoplot: TopoplotSettings = field(default_factory=TopoplotSettings)


    
# --- Layout ---

@dataclass
class LayoutSettings:
    horizontal_ratios: List[float] = field(default_factory=lambda: [0.10, 0.60, 0.30])
    center_ratio: float = 0.75
    right_ratio: float = 0.5



# --- SPEED ---

@dataclass
class SpeedSettings:
    window_start: int = -100
    window_end: int = 300
    artifact: bool = True
    artifact_start: int = -5
    artifact_end: int = 15
    notch: bool = False
    notch_fr: int = 50
    highpass: bool = False
    low_freq: int = 1
    lowpass: bool = True
    high_freq: int = 2500
    resampling: bool = True
    Fs_orig: int = 25000
    Fs: int = 5000


# --- Root ---

@dataclass
class Settings:

    curr_mode_data_idx: int = 0
    n_max_save: int = 1000
    n_save: int = 2
    save_all: bool = True

    n_aver: int = 100
    aver_all: bool = True
    aver_mode: bool = False
    aver_methods: List[str] = field(default_factory=lambda: ["mean", "median", "trimmean"])

    CAR: bool = True
    bad_channels: List[str] = field(default_factory=lambda: ["FT9", "FT10", "TP9", "TP10"])

    baseline: bool = True
    baseline_methods: List[str] = field(default_factory=lambda: ["mean", "median"])
    baseline_start: int = -75
    baseline_end: int = -20

    lowpass: bool = True
    high_freq: int = 250

    rereference: bool = False
    rereference_channel: List[str] = field(default_factory=lambda: ["Fz"])

    processing_settings: ProcessingSettings = field(default_factory=ProcessingSettings)
    record: RecordSettings = field(default_factory=RecordSettings)
    stimuli: StimuliSettings = field(default_factory=StimuliSettings)
    # topo_teps_plot: TopoTEPsPlotSettings = field(default_factory=TopoTEPsPlotSettings)
    layout: LayoutSettings = field(default_factory=LayoutSettings)
    # MEP_plot: MEPPlotSettings = field(default_factory=MEPPlotSettings)
    # TEP_suppl_plot: TEPSupplPlotSettings = field(default_factory=TEPSupplPlotSettings)
    speed: SpeedSettings = field(default_factory=SpeedSettings)

    SPEED_settings_path: str = "./SPEED_settings.json"

    channels: List[str] = field(default_factory=lambda: ['T7', 'TP9', 'P7', 'CP5', 'FT9', 'F7', 'FC5', 'F3', 'P3', 'C3', 'CP1', 'O1', 'Fp1',
                                                            'FC1', 'Fz', 'Fp2', 'Cz', 'FC2', 'CP2', 'Pz', 'O2', 'Oz', 'C4', 'P4', 'F4', 'FC6',
                                                            'F8', 'FT10', 'CP6', 'P8', 'T8', 'TP10', 'FT7', 'TP7', 'AF7', 'F5', 'C5', 'FC3',
                                                            'CP3', 'P5', 'PO3', 'PO7', 'C1', 'P1', 'AF3', 'F1', 'AF4', 'Fpz', 'FCz', 'F2', 'CPz',
                                                            'C2', 'POz', 'P2', 'PO8', 'PO4', 'P6', 'CP4', 'FC4', 'C6', 'F6', 'AF8', 'FT8', 'TP8'])
