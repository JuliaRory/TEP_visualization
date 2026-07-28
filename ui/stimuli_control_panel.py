from PyQt5.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy, QShortcut
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QKeySequence

import json
import os
import socket

from utils.ui_helpers import create_button, create_spin_box, create_check_box, create_combo_box, create_checkable_combobox, create_shortcut, create_lineedit
from utils.layout_utils import create_hbox, create_vbox

from .video_player import StimuliPresentation_one_by_one
# from .video_player_antiponk import StimuliPresentationAntiponk
from .video_player_phases import StimuliPresentationPhases
from .video_player_bci import StimuliPresentation_BCI
from .stimuli_window import StimuliCreation
from .widgets.bci_mep_bins_window import BCIMEPDelayWindow
from ui.widgets.slider_with_labels import VerticalSliderWithLabel, HorizontalSliderWithLabel
from .audio_player import AudioPlayer

PLAY_LABEL = "▶"
STOP_LABEL = "⏸"


class _TensionOnRelay(QObject):
    messageReceived = pyqtSignal(object)


UDP_HOST = "127.0.0.1"
UDP_PORT = 5005


class StimuliControlPanel(QFrame):
    """ --- UI для контроля за стимулами --- """

    stimuliPresentation = pyqtSignal(bool)

    def __init__(
        self,
        settings,
        output_stream,
        feet_stim_stream=None,
        parent=None,
        tension_wait_stream=None,
        tension_on_stream=None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.setMinimumWidth(200)

        self.settings = settings
        self.output_stream = output_stream
        self.feet_stim_stream = feet_stim_stream
        self.tension_wait_stream = tension_wait_stream
        self.tension_on_stream = tension_on_stream

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finilize()

    def _init_state(self):
        self._restart_stimuli = False
        self._player_window = None
        self._tension_on_relay = _TensionOnRelay(self)
        self._tension_on_relay.messageReceived.connect(self._on_tension_on_message)
        if self.tension_on_stream is not None and hasattr(self.tension_on_stream, "set_callback"):
            self.tension_on_stream.set_callback(
                lambda *args: self._tension_on_relay.messageReceived.emit(args)
            )

        audio_file = os.path.join(r"resources\noise", self.settings.noise_filename)
        self._audio_player = AudioPlayer(audio_file, initial_volume=self.settings.noise_volume)

        self._udp_target = (UDP_HOST, UDP_PORT)
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._setup_udp_socket()
        self._udp_sequence_timer = QTimer(self)
        self._udp_sequence_timer.setSingleShot(True)
        self._udp_sequence_timer.timeout.connect(self._send_next_udp_sequence_message)
        self._udp_sequence_messages = []
        self._udp_sequence_index = 0
        self._udp_stimulus_commands = []
        self._udp_stimulus_index = 0
        self._recording_in_progress = False

    def _setup_ui(self):
        self._settings_panel = QFrame(self)
        self.button_create_stimuli = create_button(text="Создать", disabled=False, parent=self, w=100)

        self.combo_box_stimuli = create_combo_box([], parent=self, tooltips=True)
        self.combo_box_bci_stimuli = create_combo_box([], parent=self, tooltips=True)
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
        self.spin_box_phases_delay = create_spin_box(
            -1000, 1000, getattr(self.settings, "phases_delay_ms", 0), step=10, 
              w=70
        )
        self.spin_box_tension_timeout = create_spin_box(
            0,
            10000,
            getattr(self.settings, "antiponk_tension_timeout_ms", 1000),
            step=100,
            w=70,
        )
        self.spin_box_bci_stimuli_dur = create_spin_box(
            100, 60000, self.settings.stimuli_dur, step=100, parent=self, w=70
        )
        self.spin_box_bci_isi_min = create_spin_box(
            0, 60000, self.settings.bci_isi_min_ms, step=100, parent=self, w=70
        )
        self.spin_box_bci_isi_max = create_spin_box(
            0, 60000, self.settings.bci_isi_max_ms, step=100, parent=self, w=70
        )
        self.spin_box_bci_ponk_isi_min = create_spin_box(
            0, 10000, self.settings.bci_ponk_isi_min_ms, step=50, parent=self, w=70
        )
        self.spin_box_bci_ponk_isi_max = create_spin_box(
            0, 10000, self.settings.bci_ponk_isi_max_ms, step=50, parent=self, w=70
        )

        self.check_box_stimuli_record = create_check_box(self.settings.stimuli_with_record, "Запись NVX", parent=self)
        self.check_box_noise = create_check_box(self.settings.use_noise, "Шум", parent=self)
        self.check_box_wait_tension = create_check_box(
            getattr(self.settings, "antiponk_wait_tension", False),
            "ждать напряжение"
        )
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

        self.button_bci_stimuli = create_button(text="Запуск offBCI", disabled=False, parent=self)
        self.button_bci_mep_bins = create_button(text="MEP bins", disabled=False, parent=self)

        self._udp_panel = QFrame(self)
        self.label_udp_target = QLabel(f"UDP {UDP_HOST}:{UDP_PORT}", self)
        self.check_box_udp = create_check_box(False, "send saved udp_commands", parent=self)
        self.line_edit_udp_single = create_lineedit(parent=self)
        self.line_edit_udp_single.setText("1")
        self.line_edit_udp = self.line_edit_udp_single
        self.button_udp_send = create_button(text="send", disabled=False, parent=self, w=60)
        self.line_edit_udp_sequence = create_lineedit(parent=self)
        self.line_edit_udp_sequence.setText("1, 2, 3")
        self.spin_box_udp_interval_ms = create_spin_box(0, 60000, 100, step=10, parent=self, w=70)
        self.button_udp_send_sequence = create_button(text="send seq", disabled=False, parent=self, w=80)

    def _setup_layout(self):
        layout_stimuli_creation = create_vbox([QLabel("СТИМУЛЫ", self), self.button_create_stimuli])
        layout_stimuli = create_hbox([self.combo_box_stimuli, self._button_update_stimuli])
        layout_bci_stimuli = create_hbox([QLabel("offBCI seq", self), self.combo_box_bci_stimuli])
        layout_monitor = create_hbox([QLabel("монитор", self), self.spin_box_monitor])
        layout_nvx = create_hbox([self.check_box_stimuli_record])
        layout_noise = create_hbox(
            [self.check_box_noise, self.button_noise, QLabel("Тип:"), self.combo_box_noise_type, QLabel("var:"), self.combo_box_white_noise]
        )
        layout_rest_video = create_hbox([QLabel("REST", self), self.combo_box_rest_video])
        layout_isi = create_hbox(
            [QLabel("ISI, s", self), self.spin_box_isi_min, QLabel("min", self), self.spin_box_isi_max, QLabel("max", self)]
        )
        layout_phases_delay = create_hbox(
            [QLabel("Delay, ms"), self.spin_box_phases_delay]
        )
        layout_antiponk = create_hbox(
            [
                self.check_box_wait_tension,
                QLabel("timeout, ms"),
                self.spin_box_tension_timeout,
            ]
        )
        layout_bci_stimuli_dur = create_hbox(
            [QLabel("BCI stim, ms", self), self.spin_box_bci_stimuli_dur]
        )
        layout_bci_isi = create_hbox(
            [
                QLabel("BCI ISI, ms", self),
                self.spin_box_bci_isi_min,
                QLabel("min", self),
                self.spin_box_bci_isi_max,
                QLabel("max", self),
            ]
        )
        layout_bci_ponk_isi = create_hbox(
            [
                QLabel("PONK ISI, ms", self),
                self.spin_box_bci_ponk_isi_min,
                QLabel("min", self),
                self.spin_box_bci_ponk_isi_max,
                QLabel("max", self),
            ]
        )

        layout_stimuli_launch = create_hbox([self.button_stimuli])
        layout_stimuli_control = create_hbox([self.button_stimuli_pause, self.button_stimuli_restart])
        layout_volume = create_hbox([self.stimuli_volume_slider, self.noise_volume_slider])

        layout_udp_single = create_hbox(
            [QLabel("one", self), self.line_edit_udp_single, self.button_udp_send]
        )
        layout_udp_sequence = create_hbox(
            [
                QLabel("seq", self),
                self.line_edit_udp_sequence,
                QLabel("ms", self),
                self.spin_box_udp_interval_ms,
                self.button_udp_send_sequence,
            ]
        )
        layout_udp_auto = create_hbox([self.check_box_udp])

        layout_udp = QVBoxLayout(self._udp_panel)
        layout_udp.addWidget(self.label_udp_target)
        layout_udp.addLayout(layout_udp_single)
        layout_udp.addLayout(layout_udp_sequence)
        layout_udp.addLayout(layout_udp_auto)

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
        layout.addLayout(layout_rest_video)

        layout.addLayout(layout_isi)
        # layout.addLayout(layout_phases_delay)
        # layout.addLayout(layout_antiponk)

        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("BCI MODE"))

        layout.addLayout(layout_bci_stimuli)
        layout.addLayout(layout_bci_stimuli_dur)
        layout.addLayout(layout_bci_isi)
        layout.addLayout(layout_bci_ponk_isi)

        layout.addWidget(QLabel(""))
        layout.addLayout(layout_noise)

        layout.addLayout(layout_center)
        layout.addWidget(self._udp_panel)

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
        self.spin_box_phases_delay.valueChanged.connect(self._on_change_phases_delay)
        self.spin_box_tension_timeout.valueChanged.connect(self._on_change_antiponk_tension)
        self.check_box_wait_tension.stateChanged.connect(self._on_change_antiponk_tension)
        self.spin_box_bci_stimuli_dur.valueChanged.connect(self._on_change_bci_timing)
        self.spin_box_bci_isi_min.valueChanged.connect(self._on_change_bci_timing)
        self.spin_box_bci_isi_max.valueChanged.connect(self._on_change_bci_timing)
        self.spin_box_bci_ponk_isi_min.valueChanged.connect(self._on_change_bci_timing)
        self.spin_box_bci_ponk_isi_max.valueChanged.connect(self._on_change_bci_timing)

        self._button_update_stimuli.clicked.connect(self._update_combo_box_stimuli)
        self._button_update_stimuli.clicked.connect(self._update_combo_box_bci_stimuli)
        self.combo_box_noise_type.currentTextChanged[str].connect(self._change_audio_filename)
        self.combo_box_white_noise.currentTextChanged[str].connect(self._change_audio_filename)
        self.combo_box_rest_video.textChanged.connect(self._on_change_rest_video_variants)

        self.button_bci_stimuli.clicked.connect(self._on_bci_stimmuli_button_click)
        self.button_bci_mep_bins.clicked.connect(self._on_bci_mep_bins_button_click)
        self.button_udp_send.clicked.connect(self._on_send_udp_message_button_click)
        self.button_udp_send_sequence.clicked.connect(self._on_send_udp_sequence_button_click)

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
            seq_name = self.combo_box_bci_stimuli.currentText()
            sequence = self._get_sequence_bci(seq_name)
            if not sequence:
                print(f"[StimuliControlPanel]: BCI sequence '{seq_name}' is empty or not found.")
                return

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
            self._set_udp_stimulus_commands(None)
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
            seq_name = self.combo_box_stimuli.currentText()
            sequence = self._get_sequence(seq_name)
            phases_mode = self._is_phases_sequence(seq_name, sequence)
            antiponk_mode = self._is_antiponk_sequence(seq_name, sequence)

            if not self._restart_stimuli:
                self._player_window = self._create_stimuli_player(
                    phases_mode=phases_mode,
                    antiponk_mode=antiponk_mode,
                )
                self._player_window.show()
                self._player_window.raise_()
                self._update_connections()

            if antiponk_mode:
                print("antiponk") #self._apply_antiponk_tension_settings()
            elif phases_mode:
                self._player_window.set_phase_delay(getattr(self.settings, "phases_delay_ms", 0))
            else:
                self._player_window.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
                self._player_window.set_rest_stimulus_variants(self.settings.rest_video_selected)
            self._set_udp_stimulus_commands(sequence)
            self._player_window.set_sequence(sequence, seq_name)
            self._player_window.restart_sequence()

            self.button_stimuli_pause.setEnabled(True)
            self.button_stimuli_pause.setText(PLAY_LABEL)
            self.button_stimuli.setText("Закрыть")

            self._restart_stimuli = False

    def _create_stimuli_player(self, phases_mode=False, antiponk_mode=False):
        # if antiponk_mode:
        #     player = StimuliPresentationAntiponk(
        #         monitor=self.spin_box_monitor.value(),
        #         volume=self.stimuli_volume_slider.slider.value(),
        #         rest_stimulus_variants=self.settings.rest_video_selected,
        #         wait_for_tension=getattr(self.settings, "antiponk_wait_tension", False),
        #         tension_timeout_ms=getattr(self.settings, "antiponk_tension_timeout_ms", 1000),
        #         tension_wait_stream=self.tension_wait_stream,
        #     )
        #     player.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
        #     return player

        if phases_mode:
            return StimuliPresentationPhases(
                monitor=self.spin_box_monitor.value(),
                volume=self.stimuli_volume_slider.slider.value(),
                rest_stimulus_variants=self.settings.rest_video_selected,
                delay_ms=getattr(self.settings, "phases_delay_ms", 0),
            )
        print("NORMAL MODE")
        player = StimuliPresentation_one_by_one(
            monitor=self.spin_box_monitor.value(),
            volume=self.stimuli_volume_slider.slider.value(),
            rest_stimulus_variants=self.settings.rest_video_selected,
        )
        player.set_isi_range(self.settings.isi_min_s, self.settings.isi_max_s)
        return player

    def _is_phases_sequence(self, seq_name, sequence=None):
        if seq_name and "_phases_" in seq_name.lower():
            return True
        if not sequence:
            return False
        return any("_phases_" in str(filename).lower() for filename in sequence.get("set", {}).values())

    def _is_antiponk_sequence(self, seq_name, sequence=None):
        if seq_name and "_antiponk_" in seq_name.lower():
            return True
        if not sequence:
            return False
        return any("_antiponk_" in str(filename).lower() for filename in sequence.get("set", {}).values())

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
        self._udp_stimulus_index = 0

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
        self._send_udp_for_current_stimulus()

    def _on_send_udp_message_button_click(self):
        self._send_udp_message(self.line_edit_udp_single.text().strip())

    def _on_send_udp_sequence_button_click(self):
        messages = self._parse_udp_messages(self.line_edit_udp_sequence.text())
        if not messages:
            print("[UDP]: sequence is empty.")
            return

        self._udp_sequence_timer.stop()
        self._udp_sequence_messages = messages
        self._udp_sequence_index = 0
        self._send_next_udp_sequence_message()

    def _send_next_udp_sequence_message(self):
        if self._udp_sequence_index >= len(self._udp_sequence_messages):
            return

        message = self._udp_sequence_messages[self._udp_sequence_index]
        self._send_udp_message(message)
        self._udp_sequence_index += 1

        if self._udp_sequence_index < len(self._udp_sequence_messages):
            self._udp_sequence_timer.start(int(self.spin_box_udp_interval_ms.value()))

    def _send_udp_for_current_stimulus(self):
        if not self.check_box_udp.isChecked():
            return

        pw = getattr(self, "_player_window", None)
        if not getattr(pw, "_sequence_started", False):
            return

        if not self._udp_stimulus_commands:
            return

        message = self._udp_stimulus_commands[
            self._udp_stimulus_index % len(self._udp_stimulus_commands)
        ]
        self._send_udp_message(message)
        self._udp_stimulus_index += 1

    def _set_udp_stimulus_commands(self, sequence):
        self._udp_stimulus_index = 0
        self._udp_stimulus_commands = []

        if not isinstance(sequence, dict):
            return

        commands = sequence.get("udp_commands")
        if not isinstance(commands, list):
            return

        self._udp_stimulus_commands = [str(command) for command in commands]

    def _send_udp_message(self, message):
        message = str(message).strip()
        if not message:
            return

        try:
            self._udp_socket.sendto(message.encode("utf-8"), self._udp_target)
            print(f"[UDP]: sent '{message}' to {UDP_HOST}:{UDP_PORT}")
            data, address = self._udp_socket.recvfrom(2048)
            response = data.decode("utf-8", errors="replace").strip()
            self._handle_udp_response(response, address)
        except OSError as exc:
            print(f"[UDP]: send/receive failed: {exc}")

    @staticmethod
    def _parse_udp_messages(text):
        return [message.strip() for message in str(text).split(",") if message.strip()]

    def _setup_udp_socket(self):
        self._udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self._udp_socket.bind(self._udp_target)
        except OSError as exc:
            print(f"[UDP]: bind failed on {UDP_HOST}:{UDP_PORT}: {exc}")
            return

        print(f"[UDP]: socket bound to {UDP_HOST}:{UDP_PORT}")

    def _close_udp_socket(self):
        try:
            self._udp_socket.close()
        except OSError:
            pass

    def _handle_udp_response(self, message, address):
        print(f"[UDP response] {address[0]}:{address[1]} -> {message}")

        if not self._recording_in_progress or self.feet_stim_stream is None:
            return

        output_message = {
            "feetStim": message,
            "source": f"{address[0]}:{address[1]}",
        }
        try:
            self.feet_stim_stream(json.dumps(output_message))
        except Exception as exc:
            print(f"[UDP]: feetStim stream write failed: {exc}")

    def set_recording_active(self, recording):
        self._recording_in_progress = bool(recording)

    def closeEvent(self, event):
        self._close_udp_socket()
        super().closeEvent(event)

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

    def _on_change_bci_timing(self, _value):
        stimuli_dur = int(self.spin_box_bci_stimuli_dur.value())
        isi_min_ms = int(self.spin_box_bci_isi_min.value())
        isi_max_ms = int(self.spin_box_bci_isi_max.value())
        ponk_isi_min_ms = int(self.spin_box_bci_ponk_isi_min.value())
        ponk_isi_max_ms = int(self.spin_box_bci_ponk_isi_max.value())

        if isi_min_ms > isi_max_ms:
            isi_min_ms, isi_max_ms = isi_max_ms, isi_min_ms
            self.spin_box_bci_isi_min.blockSignals(True)
            self.spin_box_bci_isi_max.blockSignals(True)
            self.spin_box_bci_isi_min.setValue(isi_min_ms)
            self.spin_box_bci_isi_max.setValue(isi_max_ms)
            self.spin_box_bci_isi_min.blockSignals(False)
            self.spin_box_bci_isi_max.blockSignals(False)

        if ponk_isi_min_ms > ponk_isi_max_ms:
            ponk_isi_min_ms, ponk_isi_max_ms = ponk_isi_max_ms, ponk_isi_min_ms
            self.spin_box_bci_ponk_isi_min.blockSignals(True)
            self.spin_box_bci_ponk_isi_max.blockSignals(True)
            self.spin_box_bci_ponk_isi_min.setValue(ponk_isi_min_ms)
            self.spin_box_bci_ponk_isi_max.setValue(ponk_isi_max_ms)
            self.spin_box_bci_ponk_isi_min.blockSignals(False)
            self.spin_box_bci_ponk_isi_max.blockSignals(False)

        self.settings.stimuli_dur = stimuli_dur
        self.settings.bci_isi_min_ms = isi_min_ms
        self.settings.bci_isi_max_ms = isi_max_ms
        self.settings.bci_ponk_isi_min_ms = ponk_isi_min_ms
        self.settings.bci_ponk_isi_max_ms = ponk_isi_max_ms

        pw = getattr(self, "_player_window", None)
        if isinstance(pw, StimuliPresentation_BCI) and not pw.isHidden():
            pw.set_bci_timing(
                stimuli_dur_ms=stimuli_dur,
                isi_min_ms=isi_min_ms,
                isi_max_ms=isi_max_ms,
                ponk_isi_min_ms=ponk_isi_min_ms,
                ponk_isi_max_ms=ponk_isi_max_ms,
            )

    def _on_change_phases_delay(self, value):
        self.settings.phases_delay_ms = int(value)

        pw = getattr(self, "_player_window", None)
        if isinstance(pw, StimuliPresentationPhases) and not pw.isHidden():
            pw.set_phase_delay(self.settings.phases_delay_ms)

        window = getattr(self, "_bci_mep_bins_window", None)
        if window is not None and window.isVisible():
            window.update_delay_from_settings()

    def _on_change_antiponk_tension(self, _value=None):
        self.settings.antiponk_wait_tension = self.check_box_wait_tension.isChecked()
        self.settings.antiponk_tension_timeout_ms = int(self.spin_box_tension_timeout.value())
        self._apply_antiponk_tension_settings()

    def _apply_antiponk_tension_settings(self):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, StimuliPresentationAntiponk) and not pw.isHidden():
            pw.set_tension_wait_enabled(getattr(self.settings, "antiponk_wait_tension", False))
            pw.set_tension_timeout_ms(getattr(self.settings, "antiponk_tension_timeout_ms", 1000))

    def _on_tension_on_message(self, message):
        pw = getattr(self, "_player_window", None)
        if isinstance(pw, StimuliPresentationAntiponk) and not pw.isHidden():
            pw.on_tension_on_message(message)

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

    def _update_combo_box_bci_stimuli(self):
        current = self.combo_box_bci_stimuli.currentText()
        self.combo_box_bci_stimuli.clear()
        try:
            with open(self.settings.stimuli_bci_filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        if not isinstance(data, dict):
            return

        self.combo_box_bci_stimuli.addItems(data.keys())
        if current:
            index = self.combo_box_bci_stimuli.findText(current)
            if index >= 0:
                self.combo_box_bci_stimuli.setCurrentIndex(index)

    def _update_combo_box_noise(self):
        return

    def _finilize(self):
        self._update_combo_box_stimuli()
        self._update_combo_box_bci_stimuli()

    def sync_ui_from_settings(self):
        self._update_combo_box_bci_stimuli()
        available = set(self.settings.rest_video_variants)
        selected = [item for item in self.settings.rest_video_selected if item in available]
        if not selected:
            selected = [self.settings.rest_video_variants[0]]
        self.settings.rest_video_selected = selected
        self._set_rest_video_checked_items(selected)
        self._set_bci_timing_spinbox_values()
        self.check_box_wait_tension.blockSignals(True)
        self.check_box_wait_tension.setChecked(getattr(self.settings, "antiponk_wait_tension", False))
        self.check_box_wait_tension.blockSignals(False)

    def _set_bci_timing_spinbox_values(self):
        spinbox_values = [
            (self.spin_box_phases_delay, getattr(self.settings, "phases_delay_ms", 0)),
            (self.spin_box_tension_timeout, getattr(self.settings, "antiponk_tension_timeout_ms", 1000)),
            (self.spin_box_bci_stimuli_dur, self.settings.stimuli_dur),
            (self.spin_box_bci_isi_min, self.settings.bci_isi_min_ms),
            (self.spin_box_bci_isi_max, self.settings.bci_isi_max_ms),
            (self.spin_box_bci_ponk_isi_min, self.settings.bci_ponk_isi_min_ms),
            (self.spin_box_bci_ponk_isi_max, self.settings.bci_ponk_isi_max_ms),
        ]
        for spinbox, value in spinbox_values:
            spinbox.blockSignals(True)
            spinbox.setValue(value)
            spinbox.blockSignals(False)
