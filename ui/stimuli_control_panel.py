from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QShortcut
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence

import json
import os

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_shortcut
from utils.layout_utils import create_hbox, create_vbox

from .video_player import StimuliPresentation_one_by_one
from .video_player_bci import StimuliPresentation_BCI
from .stimuli_window import StimuliCreation
from .widgets.bci_mep_bins_window import BCIMEPDelayWindow
from ui.widgets.slider_with_labels import VerticalSliderWithLabel, HorizontalSliderWithLabel
from .audio_player import AudioPlayer

PLAY_LABEL = "▶"
STOP_LABEL = "⏸"


class StimuliControlPanel(QFrame):
    """ --- UI для контроля за стимулами --- """

    stimuliPresentation = pyqtSignal(bool)

    def __init__(self, settings, output_stream, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setMinimumWidth(200)

        self.settings = settings
        self.output_stream = output_stream

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

    def _init_state(self):
        self._restart_stimuli = False
        self._player_window = None

        audio_file = os.path.join(r"resources\noise", self.settings.noise_filename)
        self._audio_player = AudioPlayer(audio_file, initial_volume=self.settings.noise_volume)

    def _setup_ui(self):
        self._settings_panel = QFrame(self)
        self.button_create_stimuli = create_button(text="Создать", disabled=False, parent=self, w=100)

        self.combo_box_stimuli = create_combo_box([], parent=self, tooltips=True)
        self._button_update_stimuli = create_button(text="⟳", disabled=False, parent=self, w=30)

        self.combo_box_noise_type = create_combo_box(self.settings.noise_type, parent=self, tooltips=True)
        self.combo_box_white_noise = create_combo_box(self.settings.white_noise, parent=self, tooltips=True)
        self.combo_box_rest_video = create_checkable_combobox(
            self.settings.rest_video_variants,
            self.settings.rest_video_selected,
            status=True,
            w=190,
            parent=self,
        )

        self.spin_box_monitor = create_spin_box(1, 3, self.settings.monitor, parent=self)
        self.spin_box_isi_min = create_spin_box(
            0.1, 30.0, self.settings.isi_min_s, data_type="float", step=0.1, decimals=1, parent=self
        )
        self.spin_box_isi_max = create_spin_box(
            0.1, 30.0, self.settings.isi_max_s, data_type="float", step=0.1, decimals=1, parent=self
        )

        self.check_box_stimuli_record = create_check_box(self.settings.stimuli_with_record, "Запись NVX", parent=self)
        self.check_box_noise = create_check_box(self.settings.use_noise, "Шум", parent=self)
        self.button_noise = create_button(text=PLAY_LABEL, disabled=False, parent=self)

        self.button_stimuli = create_button(text="Запуск", disabled=False, parent=self, w=100)
        self.button_stimuli_restart = create_button(text="Заново", disabled=True)
        self.button_stimuli_pause = create_button(text=PLAY_LABEL, disabled=True, parent=self)

        self.label_stimuli_idx = QLabel("", self)
        self.label_stimuli_idx.setObjectName("label_stimulus_idx")

        self.stimuli_volume_slider = VerticalSliderWithLabel("S")
        self.stimuli_volume_slider.slider.setValue(self.settings.stimuli_volume)

        self.noise_volume_slider = VerticalSliderWithLabel("N")
        self.noise_volume_slider.slider.setValue(self.settings.noise_volume)

        create_shortcut("N+Up", self._up_noise_volume, parent=self.parent)
        create_shortcut("N+Down", self._down_noise_volume, parent=self.parent)
        create_shortcut("S+Up", self._up_stimuli_volume, parent=self.parent)
        create_shortcut("S+Down", self._down_stimuli_volume, parent=self.parent)

        self.button_bci_stimuli = create_button(text="Запуск BCI", disabled=False, parent=self)
        self.button_bci_mep_bins = create_button(text="MEP bins", disabled=False, parent=self)

    def _setup_layout(self):
        layout_stimuli_creation = create_vbox([QLabel("СТИМУЛЫ", self), self.button_create_stimuli])
        layout_stimuli = create_hbox([self.combo_box_stimuli, self._button_update_stimuli])
        layout_monitor = create_hbox([QLabel("монитор", self), self.spin_box_monitor])
        layout_nvx = create_hbox([self.check_box_stimuli_record])
        layout_noise = create_hbox(
            [self.check_box_noise, self.button_noise, QLabel("Тип:"), self.combo_box_noise_type, QLabel("var:"), self.combo_box_white_noise]
        )
        layout_rest_video = create_hbox([QLabel("REST", self), self.combo_box_rest_video])
        layout_isi = create_hbox(
            [QLabel("ISI, s", self), self.spin_box_isi_min, QLabel("min", self), self.spin_box_isi_max, QLabel("max", self)]
        )

        layout_stimuli_launch = create_hbox([self.button_stimuli])
        layout_stimuli_control = create_hbox([self.button_stimuli_pause, self.button_stimuli_restart])
        layout_volume = create_hbox([self.stimuli_volume_slider, self.noise_volume_slider])

        layout_params = QVBoxLayout()
        layout_params.addLayout(layout_monitor)
        layout_params.addLayout(layout_nvx)
        layout_params.addLayout(layout_stimuli_launch)
        layout_params.addLayout(layout_stimuli_control)
        layout_params.addWidget(self.button_bci_stimuli)
        layout_params.addWidget(self.button_bci_mep_bins)
        layout_params.addWidget(self.label_stimuli_idx)

        layout_center = QHBoxLayout()
        layout_center.addLayout(layout_params)
        layout_center.addLayout(layout_volume)

        layout = QVBoxLayout(self._settings_panel)
        layout.addLayout(layout_stimuli_creation)
        layout.addLayout(layout_stimuli)
        layout.addLayout(layout_noise)
        layout.addLayout(layout_rest_video)
        layout.addLayout(layout_isi)
        layout.addLayout(layout_center)

        layout = QHBoxLayout(self)
        layout.addWidget(self._settings_panel)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_connections(self):
        self.button_create_stimuli.clicked.connect(self._on_create_stimuli_button_click)
        self.button_stimuli.clicked.connect(self._on_stimuli_button_click)
        self.button_stimuli_pause.clicked.connect(self._on_pause_stimuli_button_click)
        self.button_stimuli_restart.clicked.connect(self._on_restart_stimuli_presentation)

        self.button_noise.clicked.connect(self._on_noise_button_click)

        self.stimuli_volume_slider.valueChanged.connect(self._on_change_stimuli_volume)
        self.noise_volume_slider.valueChanged.connect(self._on_change_noise_volume)
        self.spin_box_isi_min.valueChanged.connect(self._on_change_isi_range)
        self.spin_box_isi_max.valueChanged.connect(self._on_change_isi_range)

        self._button_update_stimuli.clicked.connect(self._update_combo_box_stimuli)
        self.combo_box_noise_type.currentTextChanged[str].connect(self._change_audio_filename)
        self.combo_box_white_noise.currentTextChanged[str].connect(self._change_audio_filename)
        self.combo_box_rest_video.textChanged.connect(self._on_change_rest_video_variants)

        self.button_bci_stimuli.clicked.connect(self._on_bci_stimmuli_button_click)
        self.button_bci_mep_bins.clicked.connect(self._on_bci_mep_bins_button_click)

    def _update_connections(self):
        self._player_window.stimuliStarted.connect(self._on_start_stimuli)
        self._player_window.stimuliPaused.connect(self._change_button_pause_stimuli_text)
        self._player_window.stimuliFinished.connect(self._on_finish_stimuli)

        self._player_window.currIdxChanged.connect(self._on_stimuli_idx_changed)
        self._player_window.stimulus.connect(self._on_stimuli_order_changed)

        self._player_window.volumeChanged.connect(self._on_player_volume_changed)
        self._player_window.playerIsMuted.connect(self._on_player_muted)

    def _on_create_stimuli_button_click(self):
        self._create_stimuli_window = StimuliCreation()
        self._create_stimuli_window.show()

    def _on_bci_stimmuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden() and not self._restart_stimuli:
            self.button_stimuli.setText("Запуск")
            self.button_stimuli_restart.setEnabled(True)
            self._player_window.finish()
        else:
            self._player_window = StimuliPresentation_BCI(
                    monitor=self.spin_box_monitor.value(),
                    volume=self.stimuli_volume_slider.slider.value(),
                    rest_stimulus_variants=self.settings.rest_video_selected,
                    settings=self.settings
                )
            self._player_window.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
            self._player_window.show()
            self._player_window.raise_()

            self._update_connections()

            self._player_window.set_rest_stimulus_variants(self.settings.rest_video_selected)
            seq_name = "0"  # self.combo_box_stimuli.currentText()
            sequence = self._get_sequence_bci(seq_name)
            self._player_window.set_sequence(sequence, seq_name)

            self._player_window.restart_sequence()

            self.button_stimuli_pause.setEnabled(True)
            self.button_stimuli_pause.setText(PLAY_LABEL)

    def _on_bci_mep_bins_button_click(self):
        if (
            getattr(self, "_bci_mep_bins_window", None) is not None
            and self._bci_mep_bins_window.isVisible()
        ):
            self._bci_mep_bins_window.raise_()
            self._bci_mep_bins_window.activateWindow()
            return

        root_settings = getattr(self.parent, "settings", None)
        speed_settings = getattr(root_settings, "speed", None)
        self._bci_mep_bins_window = BCIMEPDelayWindow(self.settings, speed_settings=speed_settings)
        self._bci_mep_bins_window.show()
        self._bci_mep_bins_window.raise_()

        processor = getattr(self.parent, "_data_processor", None)
        if processor is not None:
            self.update_bci_mep_epoch(processor)

    def update_bci_mep_epoch(self, processor):
        window = getattr(self, "_bci_mep_bins_window", None)
        if window is None or not window.isVisible():
            return
        window.update_from_processor(processor)

    def _on_stimuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden() and not self._restart_stimuli:
            self.button_stimuli.setText("Запуск")
            self.button_stimuli_restart.setEnabled(True)
            self._player_window.finish()
        else:
            if not self._restart_stimuli:
                self._player_window = StimuliPresentation_one_by_one(
                    monitor=self.spin_box_monitor.value(),
                    volume=self.stimuli_volume_slider.slider.value(),
                    rest_stimulus_variants=self.settings.rest_video_selected,
                )
                self._player_window.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
                self._player_window.show()
                self._player_window.raise_()

                self._update_connections()

            seq_name = self.combo_box_stimuli.currentText()
            sequence = self._get_sequence(seq_name)

            self._player_window.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
            self._player_window.set_rest_stimulus_variants(self.settings.rest_video_selected)
            self._player_window.set_sequence(sequence, seq_name)
            self._player_window.restart_sequence()

            self.button_stimuli_pause.setEnabled(True)
            self.button_stimuli_pause.setText(PLAY_LABEL)
            self.button_stimuli.setText("Закрыть")

            self._restart_stimuli = False

    def _change_audio_filename(self, _level):
        noise_type = self.combo_box_noise_type.currentText()
        noise_var = self.combo_box_white_noise.currentText()
        filename = os.path.join(r"resources/noise", f"testNoise_type{noise_type}_var{noise_var}.wav")
        print(filename)
        self._audio_player.set_audiofile(filename)

    def _on_noise_button_click(self):
        new_label = STOP_LABEL
        if self._audio_player.is_active:
            self._audio_player.pause()
            new_label = PLAY_LABEL
        elif self._audio_player.is_paused:
            self._audio_player.resume()
        else:
            self._audio_player.start_playback()

        self.button_noise.setText(new_label)

    def _change_button_pause_stimuli_text(self):
        status = PLAY_LABEL if self._player_window.is_paused else STOP_LABEL
        self.button_stimuli_pause.setText(status)
        self.button_stimuli_restart.setEnabled(self._player_window.is_paused)

        if self.check_box_noise.isChecked() and self._player_window.is_paused and self._audio_player.is_active:
            self._on_noise_button_click()

        if self.check_box_noise.isChecked() and not self._player_window.is_paused and self._audio_player.is_paused:
            self._on_noise_button_click()

    def _on_pause_stimuli_button_click(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget):
            self._player_window.pause_video()
            self._change_button_pause_stimuli_text()

    def _on_restart_stimuli_presentation(self):
        self._restart_stimuli = True
        self._on_stimuli_button_click()

    def _on_finish_stimuli(self):
        if self.check_box_stimuli_record.isChecked():
            self.stimuliPresentation.emit(False)

        self.label_stimuli_idx.setText("")
        self.button_stimuli_pause.setText(PLAY_LABEL)
        self.button_stimuli_restart.setEnabled(True)

        if self.check_box_noise.isChecked() and self._audio_player.is_active:
            self._on_noise_button_click()

    def _on_start_stimuli(self):
        if self.check_box_stimuli_record.isChecked():
            self.stimuliPresentation.emit(True)

        self.button_stimuli_pause.setText(STOP_LABEL)
        self.button_stimuli_restart.setEnabled(False)

        if self.check_box_noise.isChecked() and not self._audio_player.is_active:
            self._on_noise_button_click()

    def _on_stimuli_idx_changed(self, idx):
        self.label_stimuli_idx.setText(f"#{idx}")

    def _on_stimuli_order_changed(self, filename):
        message = {"stimulus": filename}
        print(message)
        self.output_stream(json.dumps(message))

    def _on_player_volume_changed(self, value):
        self.stimuli_volume_slider.slider.setValue(value)

    def _on_player_muted(self):
        cur_volume = self.stimuli_volume_slider.slider.value()
        volume = self._player_window.get_last_volume() if cur_volume == 0 else 0
        self.stimuli_volume_slider.slider.setValue(volume)

    def _on_change_stimuli_volume(self, value):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.update_volume(value)

    def _on_change_noise_volume(self, value):
        self._audio_player.set_volume(value)

    def _on_change_isi_range(self, _value):
        min_s = self.spin_box_isi_min.value()
        max_s = self.spin_box_isi_max.value()
        if min_s > max_s:
            min_s, max_s = max_s, min_s
            self.spin_box_isi_min.blockSignals(True)
            self.spin_box_isi_max.blockSignals(True)
            self.spin_box_isi_min.setValue(min_s)
            self.spin_box_isi_max.setValue(max_s)
            self.spin_box_isi_min.blockSignals(False)
            self.spin_box_isi_max.blockSignals(False)

        self.settings.isi_min_s = min_s
        self.settings.isi_max_s = max_s

        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.set_isi_range(min_s, max_s)

    def _on_change_rest_video_variants(self, selected):
        if not selected:
            selected = [self.settings.rest_video_variants[0]]
            self._set_rest_video_checked_items(selected)

        self.settings.rest_video_selected = selected

        pw = getattr(self, "_player_window", None)
        if isinstance(pw, QWidget) and not pw.isHidden():
            self._player_window.set_rest_stimulus_variants(selected)

    def _set_rest_video_checked_items(self, selected):
        selected = set(selected)
        model = self.combo_box_rest_video.model()
        model.blockSignals(True)
        for i in range(model.rowCount()):
            item = model.item(i)
            state = Qt.Checked if item.text() in selected else Qt.Unchecked
            item.setCheckState(state)
        model.blockSignals(False)

    def _up_noise_volume(self):
        new_value = min(100, self._audio_player.volume + 5)
        self.noise_volume_slider.setValue(new_value)
        self._on_change_noise_volume(new_value)

    def _down_noise_volume(self):
        new_value = max(0, self._audio_player.volume - 5)
        self.noise_volume_slider.setValue(new_value)
        self._on_change_noise_volume(new_value)

    def _up_stimuli_volume(self):
        if self._player_window is None:
            return
        new_value = min(100, self._player_window.get_last_volume() + 5)
        self.stimuli_volume_slider.setValue(new_value)
        self._on_change_stimuli_volume(new_value)

    def _down_stimuli_volume(self):
        if self._player_window is None:
            return
        new_value = max(0, self._player_window.get_last_volume() - 5)
        self.stimuli_volume_slider.setValue(new_value)
        self._on_change_stimuli_volume(new_value)

    def _get_sequence(self, seq_name):
        if not seq_name:
            return None
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        return data.get(seq_name)
    
    def _get_sequence_bci(self, seq_name):
        if not seq_name:
            return None
        try:
            with open(self.settings.stimuli_bci_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        return data.get(seq_name)

    def _update_combo_box_stimuli(self):
        self.combo_box_stimuli.clear()
        try:
            with open(self.settings.stimuli_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.combo_box_stimuli.addItems(data.keys())
        except (FileNotFoundError, json.JSONDecodeError):
            print("файл пока пустой")

    def _update_combo_box_noise(self):
        return

    def _finilize(self):
        self._update_combo_box_stimuli()

    def sync_ui_from_settings(self):
        available = set(self.settings.rest_video_variants)
        selected = [item for item in self.settings.rest_video_selected if item in available]
        if not selected:
            selected = [self.settings.rest_video_variants[0]]
        self.settings.rest_video_selected = selected
        self._set_rest_video_checked_items(selected)
