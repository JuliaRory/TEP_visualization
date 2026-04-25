import os
import random
import time

import vlc
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class StimuliPresentation_one_by_one(QWidget):
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
        self._cross_started_at = None
        self._cross_remaining_ms = 0
        self._isi_min_s = 1.5
        self._isi_max_s = 3.0

        self.intro_pic_path = os.path.join(
            r"resources\crossFigures", "cross_image_black_photomark.png"
        )
        final_fig_files = os.listdir(r"resources\final_fig")
        self.final_pic_path = os.path.join(
            r"resources\final_fig", random.choice(final_fig_files)
        )

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

        self._cross_timer = QTimer(self)
        self._cross_timer.setSingleShot(True)
        self._cross_timer.timeout.connect(self._play_next_video)

        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)

        self._placeholder_widget = QLabel(self)
        self._marker_widget = QLabel(self)

        self._final_pic = QPixmap(self.final_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._intro_pic = QPixmap(self.intro_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._placeholder_widget.show()

        self._marker_widget.setGeometry(self.width() - 75, 0, 75, 75)
        self._marker_widget.setStyleSheet("background-color: white;")
        self._marker_widget.show()
        self._marker_widget.raise_()

    def set_sequence(self, stimuli_sequence, seq_name=None):
        if seq_name is None:
            seq_name = "a new"
        print(f"[VLC player]: set {seq_name} stimuli sequence.")
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()
        self._show_marker()

        self._cross_dur_ms = stimuli_sequence["cross"]["dur_ms"]
        self.placeholder_path = os.path.join(
            r"resources\crossFigures", stimuli_sequence["cross"]["filename"]
        )

        self._main_cross_pic = QPixmap(self.placeholder_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.order = stimuli_sequence["order"]
        self.video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        full_video_names = [os.path.join(path, file) for file in self.video_names]
        self.video_files = [full_video_names[i - 1] for i in self.order]

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)
        self.stimulus.emit(self.video_names[self.order[self._current_index] - 1])

        self._prepare_next_video()
        print("[VLC player]: press Space to start.")

    def _prepare_next_video(self):
        if self._current_index >= len(self.video_files):
            self._next_media = None
            return

        media = self._instance.media_new(self.video_files[self._current_index])
        media.parse_async()
        self._next_media = media

    def _play_next_video(self):
        if self._stopped:
            print("[VLC player]: stimuli presentation has been stopped.")
            return

        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        if self._next_media is None:
            print("[VLC player]: stimuli sequence has ended.")
            QTimer.singleShot(5000, self.stimuliFinished.emit)
            self._finished = True
            self._waiting_for_first_frame = False
            self._placeholder_widget.setPixmap(self._final_pic)
            self._placeholder_widget.show()
            self._show_marker()
            return

        if self._current_index == 1:
            self._placeholder_widget.setPixmap(self._main_cross_pic)

        self._placeholder_widget.show()
        self.stimulus.emit(self.video_names[self.order[self._current_index] - 1])

        if self._current_index == 0:
            self._show_marker()
        else:
            self._hide_marker()

        self._playback_token += 1
        self._waiting_for_first_frame = True

        # Reset the player while the placeholder fully covers the surface so
        # stale frames from the previous clip never leak into the next one.
        self._player.stop()
        self._player.set_media(self._next_media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)
        self._prepare_next_video()
        self._is_paused = False

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
        self._placeholder_widget.show()
        self._show_marker()
        self._start_cross_interval(self._get_random_isi_ms())

    def set_isi_range(self, min_s, max_s):
        min_s = float(min_s)
        max_s = float(max_s)
        if min_s > max_s:
            min_s, max_s = max_s, min_s

        self._isi_min_s = min_s
        self._isi_max_s = max_s

    def _get_random_isi_ms(self):
        return int(random.uniform(self._isi_min_s, self._isi_max_s) * 1000)

    def _show_marker(self):
        self._marker_widget.show()
        self._marker_widget.raise_()

    def _hide_marker(self):
        self._marker_widget.hide()

    def _start_cross_interval(self, duration_ms):
        self._cross_remaining_ms = max(0, int(duration_ms))
        self._cross_started_at = time.monotonic()
        self._cross_timer.start(self._cross_remaining_ms)

    def _pause_cross_interval(self):
        if not self._cross_timer.isActive():
            return False

        elapsed_ms = int((time.monotonic() - self._cross_started_at) * 1000)
        self._cross_remaining_ms = max(0, self._cross_remaining_ms - elapsed_ms)
        self._cross_started_at = None
        self._cross_timer.stop()
        return True

    def _resume_cross_interval(self):
        if self._cross_remaining_ms <= 0:
            self._play_next_video()
            return

        self._cross_started_at = time.monotonic()
        self._cross_timer.start(self._cross_remaining_ms)

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
        if not hasattr(self, "_placeholder_widget") or not hasattr(self, "_marker_widget"):
            return
        self._placeholder_widget.setGeometry(self.rect())
        self._marker_widget.setGeometry(self.width() - 75, 0, 75, 75)
        self._marker_widget.raise_()

    def _on_space_pressed(self):
        if not self._sequence_started:
            print("[VLC player]: start the stimuli presentation.")
            self._sequence_started = True
            self.stimuliStarted.emit()
            self._is_paused = False
            self._play_next_video()
            return

        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            paused_during_cross = self._pause_cross_interval()
            if not paused_during_cross:
                self._player.pause()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            if self._cross_remaining_ms > 0 and not self._waiting_for_first_frame:
                self._resume_cross_interval()
            else:
                self._player.play()
            self._is_paused = False
            self.stimuliPaused.emit()

    def pause_video(self):
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player]: restart stimuli presentation.")
        self._player.stop()

        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)

        self._prepare_next_video()
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()
        self._show_marker()

    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
        self._stopped = True
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0
        self._show_marker()
        self._player.stop()
        self._player.release()
        self._instance.release()
        if not self._finished:
            QTimer.singleShot(5000, self.stimuliFinished.emit)
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
