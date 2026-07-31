import os
import random
import time

import vlc
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


COUNTDOWN_VIDEO = r"resources/videoSamples/audio_countdown_3.mkv"
CROSS_IMAGE = r"resources/crossFigures/cross_image_black_photomark.png"
FINAL_FIG_FOLDER = r"resources/final_fig"
FINAL_IMAGE_DELAY_MS = 2000


class StimuliPresentationFeetStim(QWidget):
    stimuliStarted = pyqtSignal()
    stimuliFinished = pyqtSignal()
    stimuliPaused = pyqtSignal()
    volumeChanged = pyqtSignal(int)
    playerIsMuted = pyqtSignal()
    currIdxChanged = pyqtSignal(int)
    _videoEnded = pyqtSignal()
    _videoFrameReady = pyqtSignal(int)

    stimulus = pyqtSignal(str)

    def __init__(self, monitor=1, volume=80):
        super().__init__()

        self._volume = volume
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        self._init_state()
        self._videoEnded.connect(self._handle_video_end)
        self._videoFrameReady.connect(self._handle_video_frame_ready)

    def _init_state(self):
        self._stopped = False
        self._finished = False
        self._sequence_started = False
        self._is_paused = False
        self._playback_token = 0
        self._waiting_for_first_frame = False
        self._countdown_running = False
        self._command_started_at = None
        self._command_remaining_ms = 0
        self._isi_min_s = 1.5
        self._isi_max_s = 3.0
        self._commands = []
        self._current_index = 0
        self._current_placeholder_path = CROSS_IMAGE

        final_fig_files = [
            filename for filename in os.listdir(FINAL_FIG_FOLDER)
            if os.path.isfile(os.path.join(FINAL_FIG_FOLDER, filename))
        ]
        self.final_pic_path = os.path.join(FINAL_FIG_FOLDER, random.choice(final_fig_files))

        self._configure_player()

    def _configure_player(self):
        self._instance = vlc.Instance(
            "--file-caching=100",
            "--no-video-title-show",
            "--quiet",
            "--no-sub-autodetect-file",
            "--no-spu",
        )
        self._player = self._instance.media_player_new()

        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        events.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._on_time_changed)

        self._command_timer = QTimer(self)
        self._command_timer.setSingleShot(True)
        self._command_timer.timeout.connect(self._send_next_command)

        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)

        self._placeholder_widget = QLabel(self)
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._set_placeholder_pixmap(CROSS_IMAGE)
        self._placeholder_widget.show()

    def set_sequence(self, stimuli_sequence, seq_name=None):
        if seq_name is None:
            seq_name = "a new"
        print(f"[VLC player feetStim]: set {seq_name} stimuli sequence.")

        self._commands = self._make_command_sequence(stimuli_sequence)
        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self._set_placeholder_pixmap(CROSS_IMAGE)
        self._placeholder_widget.show()
        print("[VLC player feetStim]: press Space to start.")

    def _make_command_sequence(self, stimuli_sequence):
        if not isinstance(stimuli_sequence, dict):
            return []

        commands_by_number = {
            str(number): str(command)
            for number, command in stimuli_sequence.get("udp_commands", {}).items()
        }
        command_sequence = []
        for stimulus_number in stimuli_sequence.get("order", []):
            command = commands_by_number.get(str(stimulus_number))
            if command:
                command_sequence.append(command)
            else:
                print(f"[VLC player feetStim]: command number {stimulus_number} is missing.")
        return command_sequence

    def set_isi_range(self, min_s, max_s):
        min_s = float(min_s)
        max_s = float(max_s)
        if min_s > max_s:
            min_s, max_s = max_s, min_s

        self._isi_min_s = min_s
        self._isi_max_s = max_s

    def _get_random_isi_ms(self):
        return int(random.uniform(self._isi_min_s, self._isi_max_s) * 1000)

    def _play_countdown_video(self):
        if self._stopped:
            return

        self._playback_token += 1
        self._countdown_running = True
        self._waiting_for_first_frame = True
        self._placeholder_widget.show()

        media = self._instance.media_new(COUNTDOWN_VIDEO)
        media.parse_async()
        self._player.stop()
        self._player.set_media(media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

    def _handle_video_frame_ready(self, playback_token):
        if self._stopped or playback_token != self._playback_token:
            return
        if not self._waiting_for_first_frame:
            return

        self._waiting_for_first_frame = False
        self._placeholder_widget.hide()

    def _handle_video_end(self):
        if self._stopped:
            return

        self._waiting_for_first_frame = False
        self._player.stop()

        if self._countdown_running:
            self._countdown_running = False
            self._set_placeholder_pixmap(CROSS_IMAGE)
            self._placeholder_widget.show()
            self._start_command_interval(self._get_random_isi_ms())

    def _send_next_command(self):
        if self._stopped:
            return

        self._command_timer.stop()
        self._command_started_at = None
        self._command_remaining_ms = 0
        self._set_placeholder_pixmap(CROSS_IMAGE)
        self._placeholder_widget.show()

        if self._current_index >= len(self._commands):
            self._show_final_picture()
            return

        command = self._commands[self._current_index]
        self.stimulus.emit(command)
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)

        if self._current_index >= len(self._commands):
            self._show_final_picture()
        else:
            self._start_command_interval(self._get_random_isi_ms())

    def _show_final_picture(self):
        print("[VLC player feetStim]: stimuli sequence has ended.")
        self._finished = True
        self._set_placeholder_pixmap(self.final_pic_path)
        self._placeholder_widget.show()
        QTimer.singleShot(FINAL_IMAGE_DELAY_MS, self.stimuliFinished.emit)

    def _start_command_interval(self, duration_ms):
        self._command_remaining_ms = max(0, int(duration_ms))
        self._command_started_at = time.monotonic()
        self._command_timer.start(self._command_remaining_ms)

    def _pause_command_interval(self):
        if not self._command_timer.isActive():
            return False

        elapsed_ms = int((time.monotonic() - self._command_started_at) * 1000)
        self._command_remaining_ms = max(0, self._command_remaining_ms - elapsed_ms)
        self._command_started_at = None
        self._command_timer.stop()
        return True

    def _resume_command_interval(self):
        if self._command_remaining_ms <= 0:
            self._send_next_command()
            return

        self._command_started_at = time.monotonic()
        self._command_timer.start(self._command_remaining_ms)

    def _set_placeholder_pixmap(self, path):
        self._current_placeholder_path = path
        pixmap = QPixmap(path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._placeholder_widget.setPixmap(pixmap)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._on_space_pressed()
        elif event.key() == Qt.Key_Escape:
            self.finish()
        elif event.key() == Qt.Key_R:
            self.restart_sequence()
        elif event.key() == Qt.Key_Up:
            new_value = min(100, self._volume + 1)
            self.update_volume(new_value)
        elif event.key() == Qt.Key_Down:
            new_value = max(0, self._volume - 1)
            self.update_volume(new_value)
        elif event.key() == Qt.Key_M:
            self._player.audio_toggle_mute()
            self.playerIsMuted.emit()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_placeholder_widget"):
            return
        self._placeholder_widget.setGeometry(self.rect())
        self._set_placeholder_pixmap(self._current_placeholder_path)

    def _on_space_pressed(self):
        if not self._sequence_started:
            if not self._commands:
                print("[VLC player feetStim]: stimuli sequence is empty.")
                return
            print("[VLC player feetStim]: start the stimuli presentation.")
            self._sequence_started = True
            self.stimuliStarted.emit()
            self._is_paused = False
            self._play_countdown_video()
            return

        if not self._is_paused:
            print("[VLC player feetStim]: pause the stimuli presentation.")
            if self._countdown_running:
                self._player.pause()
            else:
                self._pause_command_interval()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        print("[VLC player feetStim]: continue the stimuli presentation.")
        if self._countdown_running:
            self._player.play()
        else:
            self._resume_command_interval()
        self._is_paused = False
        self.stimuliPaused.emit()

    def pause_video(self):
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player feetStim]: restart stimuli presentation.")
        self._player.stop()

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._countdown_running = False
        self._command_timer.stop()
        self._command_started_at = None
        self._command_remaining_ms = 0

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self._set_placeholder_pixmap(CROSS_IMAGE)
        self._placeholder_widget.show()

    def finish(self):
        print("[VLC player feetStim]: finish the stimuli presentation and close the player.")
        self._stopped = True
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._countdown_running = False
        self._command_timer.stop()
        self._command_started_at = None
        self._command_remaining_ms = 0
        self._player.stop()
        self._player.release()
        self._instance.release()
        if not self._finished:
            QTimer.singleShot(FINAL_IMAGE_DELAY_MS, self.stimuliFinished.emit)
        self.close()

    @property
    def is_paused(self):
        return self._is_paused

    def _on_end_reached(self, event):
        if self._is_paused:
            return
        self._videoEnded.emit()

    def _on_time_changed(self, event):
        if self._is_paused or not self._waiting_for_first_frame:
            return

        time_ms = getattr(event.u, "new_time", 0)
        if time_ms <= 0:
            return

        self._videoFrameReady.emit(self._playback_token)

    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        self.volumeChanged.emit(self._volume)
        print("Volume:", self._volume)

    def get_last_volume(self):
        return self._volume
