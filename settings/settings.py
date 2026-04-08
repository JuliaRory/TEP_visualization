from dataclasses import dataclass, field
from typing import List


# --- Processing ---

@dataclass
class ProcessingSettings:
    do_averaging: bool = True
    do_lowpass_filtering: bool = True
    do_rereferencing: bool = False
    do_CAR_filtering: bool = True
    apply_ICA: bool = True
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

    ica_folder: str = r"D:/temp/ICA/Cleaned_epochs"


# --- Record & NVX control---


@dataclass
class RecordSettings:
    bat_file: str = "D:\Resonance\dist_2025\control.bat"
    bat_file_home: str = "C:/Users/hodor/Documents/lab-MSU/Works/2025.10_TMS/dist_2024_11_13_imp/control.bat"
    activate_bat: bool = True
    service_name: str = "nvx136"
    stream_name: str = "eeg"
    records_folder: str = "D:/2025 - TEP/data - raw/tests"

    bat_nvx136_25Hz: str = "D:/Resonance/distro-dual/msvc/NVX136.bat"
    bat_nvx136_impedance: str = "D:/Resonance/distro-dual/msvc/impedanceChecker_64_2.bat"

    use_number: bool = True
    use_subject: bool = True
    use_spot: bool = True
    use_coil: bool = True
    use_yaw_angle: bool = True
    use_power: bool = False
    use_comments: bool = False

    number: str = "01"
    subject: str = "AV"
    spot: str = "M1"
    coil: str = "qp"
    yaw_angle: str = "45"


# --- Stimuli ---

@dataclass
class StimuliSettings:
    monitor: int = 2
    stimuli_with_record: bool = True
    use_noise: bool = True
    stimuli_filename: str = "resources/saved_stimuli.json"
    video_folder: str = "resources/videoSamples"
    stimuli_volume: int = 60
    noise_volume: int = 37
    noise_folder: str = r"resources/noise/"
    #noise_filename: str = "TAAC_CN2_coil_42MSO_9minutes_louder.wav"     # standard
    noise_filename: str = "CN2_blocked_canal_M1_9min_cor.wav"
    # noise_filename: str = "CN2_blocked_canal_M1_9min_uncor.wav"
    # noise_filename: str = "CN2_blocked_canal_SMA_9min_cor.wav"
    # noise_filename: str = "CN2_blocked_canal_SMA_9min_uncor.wav"
    noise_type: List[str] = field(default_factory=lambda: ["1", "2", "3", "4"])
    white_noise: List[str] = field(default_factory=lambda: ["1", "2", "3", "4", "5"])
    
# --- Layout ---

@dataclass
class LayoutSettings:
    horizontal_ratios: List[float] = field(default_factory=lambda: [0.20, 0.60, 0.20])
    center_ratio: float = 0.75
    right_ratio: float = 0.50


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
    nvx_control: RecordSettings = field(default_factory=RecordSettings)
    stimuli_control: StimuliSettings = field(default_factory=StimuliSettings)
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
