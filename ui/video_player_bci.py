import os
import random
import time

import vlc
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


REST_STIMULUS = "rest1500_tms_0ms_bar.mkv"
REST_STIMULUS_VARIANTS = (
    "rest1500_tms_0ms_bar.mkv",
    "rest1500_tms_-200ms_bar.mkv",
    "rest1500_tms_+200ms_bar.mkv",
)
START_COUNTDOWN_VIDEO = r"resources/videoSamples/audio_countdown_3.mkv"
INTRO_AFTER_COUNTDOWN_MS = 2000
FIRST_PONK_AFTER_COUNTDOWN_MS = 500
BCI_STIMULUS_HAND = "hand"
BCI_STIMULUS_LEG = "leg"
BCI_STIMULUS_TYPES = {BCI_STIMULUS_HAND, BCI_STIMULUS_LEG}


class StimuliPresentation_BCI(QWidget):
    stimuliStarted = pyqtSignal()
    stimuliFinished = pyqtSignal()
    stimuliPaused = pyqtSignal()
    volumeChanged = pyqtSignal(int)
    playerIsMuted = pyqtSignal()
    currIdxChanged = pyqtSignal(int)
    _videoEnded = pyqtSignal()
    _videoFrameReady = pyqtSignal(int)

    stimulusStarted = pyqtSignal(str)
    stimulusFinished = pyqtSignal(str)
    stimulus = pyqtSignal(str)

    def __init__(self, monitor=1, volume=80, rest_stimulus_variants=None, settings=None):
        super().__init__()

        self._settings = settings   # stimuli settings

        self._volume = volume
        self.set_rest_stimulus_variants(rest_stimulus_variants)

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
        self._current_stimulus = None
        self._countdown_running = False
        self._ponk_started = False
        self._cross_started_at = None
        self._cross_remaining_ms = 0
        self._intro_after_countdown_started_at = None
        self._intro_after_countdown_remaining_ms = 0
        self._isi_min_s = 1.5
        self._isi_max_s = 3.0
        self._stimuli_dur_ms = self._settings.stimuli_dur

        self._isi_bci_ponk_ms = 1000
        self._isi_bci_min_ms = self._settings.bci_isi_min_ms
        self._isi_bci_max_ms = self._settings.bci_isi_max_ms
        self._ponk_isi_min_ms = self._settings.bci_ponk_isi_min_ms
        self._ponk_isi_max_ms = self._settings.bci_ponk_isi_max_ms

        self._photomark_status = "white"

        self._bci_stimulus_type = self._normalize_bci_stimulus_type(
            getattr(self._settings, "bci_stimulus_type", BCI_STIMULUS_HAND)
        )
        self._decipher = {"1": self._bci_stimulus_type, "2": "rest"}

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
        self._cross_timer.timeout.connect(self._play_next_stimuli)

        self._intro_after_countdown_timer = QTimer(self)
        self._intro_after_countdown_timer.setSingleShot(True)
        self._intro_after_countdown_timer.timeout.connect(self._start_bci_sequence_after_intro)

        self._stimuli_timer = QTimer(self)
        self._stimuli_timer.setSingleShot(True)
        self._stimuli_timer.timeout.connect(self._stop_stimuli)

        # self._ponk_timer = QTimer(self)
        # self._ponk_timer.setSingleShot(False)
        # self._ponk_timer.timeout.connect(self._launch_ponk)

        self._ponk_timer = QTimer(self)
        self._ponk_timer.setSingleShot(True)
        self._ponk_timer.timeout.connect(self._ponk_timer_stop)

        self._photomark_timer = QTimer(self)
        self._photomark_timer.setSingleShot(True)
        self._photomark_timer.timeout.connect(self._show_marker)        

        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        self._player.set_hwnd(winid)

        self._placeholder_widget = QLabel(self)     # здесь мы будем менять стимулы
        self._marker_widget = QLabel(self)

        self._hand_pic_path = self._bci_stimulus_pic_path()
        self._rest_pic_path = self._settings.rest_pic

        self._final_pic = QPixmap(self.final_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._intro_pic = QPixmap(self._settings.background_pic).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._hand_pic = QPixmap(self._hand_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._rest_pic = QPixmap(self._rest_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        print(
            "[VLC player BCI]: loaded stimuli images:",
            {self._bci_stimulus_type: self._hand_pic_path, "rest": self._rest_pic_path},
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

        self.order = stimuli_sequence

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)

        # self._prepare_next_video()
        print("[VLC player]: press Space to start.")


    def set_rest_stimulus_variants(self, filenames):
        variants = [self._normalize_video_filename(name) for name in (filenames or [])]
        variants = [name for name in variants if name in REST_STIMULUS_VARIANTS]
        self._rest_stimulus_variants = variants or [REST_STIMULUS]

    def set_bci_stimulus_type(self, stimulus_type):
        stimulus_type = self._normalize_bci_stimulus_type(stimulus_type)
        self._bci_stimulus_type = stimulus_type
        self._settings.bci_stimulus_type = stimulus_type
        self._decipher["1"] = stimulus_type
        self._hand_pic_path = self._bci_stimulus_pic_path()
        self._hand_pic = QPixmap(self._hand_pic_path).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        if self._current_stimulus in BCI_STIMULUS_TYPES:
            self._current_stimulus = stimulus_type
            self._placeholder_widget.setPixmap(self._hand_pic)

    def _bci_stimulus_pic_path(self):
        if self._bci_stimulus_type == BCI_STIMULUS_LEG:
            return getattr(self._settings, "leg_pic", r"resources/bci/leg_base.png")
        return getattr(self._settings, "hand_pic", r"resources/bci/FDI_r_style1_base.png")

    @staticmethod
    def _normalize_bci_stimulus_type(stimulus_type):
        stimulus_type = str(stimulus_type or "").strip().lower()
        return stimulus_type if stimulus_type in BCI_STIMULUS_TYPES else BCI_STIMULUS_HAND

    @staticmethod
    def _normalize_video_filename(name):
        name = str(name)
        return name if os.path.splitext(name)[1] else f"{name}.mkv"

    def _prepare_next_video(self):
        if self._current_index >= len(self.order):
            self._next_media = None
            return

        media = self._instance.media_new(self.video_files[self._current_index])
        media.parse_async()
        self._next_media = media

    def _play_next_stimuli(self):
        if self._stopped:
            print("[VLC player]: stimuli presentation has been stopped.")
            return

        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        # if self._next_media is None:
        #     print("[VLC player]: stimuli sequence has ended.")
        #     QTimer.singleShot(2000, self.stimuliFinished.emit)
        #     self._finished = True
        #     self._waiting_for_first_frame = False
        #     self._placeholder_widget.setPixmap(self._final_pic)
        #     self._placeholder_widget.show()
        #     self._show_marker()
        #     return
        if self._current_index >= len(self.order):
            print("[VLC player]: stimuli sequence has ended.")
            QTimer.singleShot(2000, self.stimuliFinished.emit)
            self._finished = True
            self._ponk_timer.stop()
            # self._waiting_for_first_frame = False
            self._placeholder_widget.setPixmap(self._final_pic)
            self._placeholder_widget.show()
            self._show_marker()

            return
        next_stimuli = self._hand_pic if self.order[self._current_index] == 1 else self._rest_pic
        self._placeholder_widget.setPixmap(next_stimuli)
        self._placeholder_widget.show()

        self._emit_stimulus_started(self._decipher[str(self.order[self._current_index])])
        
        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)
        self._is_paused = False

        self._start_stimuli_interval(self._stimuli_dur_ms)        # ждём сколько-то мс пока идут стимулы


    def _stop_stimuli(self):
        self._stimuli_timer.stop()
        self._stimuli_started_at = None
        self._stimuli_remaining_ms = 0
        self._emit_stimulus_finished()

        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()

        self._start_cross_interval(self._get_random_isi_ms())

    def _emit_stimulus_started(self, stimulus):
        self._emit_stimulus_finished()
        self._current_stimulus = str(stimulus)
        self.stimulusStarted.emit(self._current_stimulus)
        self.stimulus.emit(self._current_stimulus)

    def _emit_stimulus_finished(self):
        if self._current_stimulus is None:
            return

        stimulus = self._current_stimulus
        self._current_stimulus = None
        self.stimulusFinished.emit(stimulus)


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
            self._placeholder_widget.setPixmap(self._intro_pic)
            self._placeholder_widget.show()
            self._show_marker()
            self._start_ponk_timer(FIRST_PONK_AFTER_COUNTDOWN_MS)
            self._start_intro_after_countdown_interval(INTRO_AFTER_COUNTDOWN_MS)
            return

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

    def set_bci_timing(
        self,
        stimuli_dur_ms=None,
        isi_min_ms=None,
        isi_max_ms=None,
        ponk_isi_min_ms=None,
        ponk_isi_max_ms=None,
    ):
        if stimuli_dur_ms is not None:
            self._stimuli_dur_ms = max(0, int(stimuli_dur_ms))

        if isi_min_ms is not None and isi_max_ms is not None:
            isi_min_ms = int(isi_min_ms)
            isi_max_ms = int(isi_max_ms)
            if isi_min_ms > isi_max_ms:
                isi_min_ms, isi_max_ms = isi_max_ms, isi_min_ms
            self._isi_bci_min_ms = isi_min_ms
            self._isi_bci_max_ms = isi_max_ms

        if ponk_isi_min_ms is not None and ponk_isi_max_ms is not None:
            ponk_isi_min_ms = int(ponk_isi_min_ms)
            ponk_isi_max_ms = int(ponk_isi_max_ms)
            if ponk_isi_min_ms > ponk_isi_max_ms:
                ponk_isi_min_ms, ponk_isi_max_ms = ponk_isi_max_ms, ponk_isi_min_ms
            self._ponk_isi_min_ms = ponk_isi_min_ms
            self._ponk_isi_max_ms = ponk_isi_max_ms

    def _get_random_isi_ms(self):
        isi_min_ms = self._isi_bci_min_ms
        isi_max_ms = self._isi_bci_max_ms
        return int(random.uniform(isi_min_ms, isi_max_ms))

    def _show_marker(self):
        self._marker_widget.show()
        self._marker_widget.raise_()
        # print("show")

    def _hide_marker(self):
        self._marker_widget.hide()
        # print("hide")

    def _start_cross_interval(self, duration_ms):
        self._cross_remaining_ms = max(0, int(duration_ms))
        self._cross_started_at = time.monotonic()
        self._cross_timer.start(self._cross_remaining_ms)

    def _start_intro_after_countdown_interval(self, duration_ms):
        self._intro_after_countdown_remaining_ms = max(0, int(duration_ms))
        self._intro_after_countdown_started_at = time.monotonic()
        self._intro_after_countdown_timer.start(self._intro_after_countdown_remaining_ms)

    def _start_stimuli_interval(self, duration_ms):
        self._stimuli_remaining_ms = max(0, int(duration_ms))
        self._stimuli_started_at = time.monotonic()
        self._stimuli_timer.start(self._stimuli_remaining_ms)
    
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
            self._play_next_stimuli()
            return

        self._cross_started_at = time.monotonic()
        self._cross_timer.start(self._cross_remaining_ms)

    def _pause_intro_after_countdown_interval(self):
        if not self._intro_after_countdown_timer.isActive():
            return False

        elapsed_ms = int((time.monotonic() - self._intro_after_countdown_started_at) * 1000)
        self._intro_after_countdown_remaining_ms = max(
            0, self._intro_after_countdown_remaining_ms - elapsed_ms
        )
        self._intro_after_countdown_started_at = None
        self._intro_after_countdown_timer.stop()
        return True

    def _resume_intro_after_countdown_interval(self):
        if self._intro_after_countdown_remaining_ms <= 0:
            self._start_bci_sequence_after_intro()
            return

        self._intro_after_countdown_started_at = time.monotonic()
        self._intro_after_countdown_timer.start(self._intro_after_countdown_remaining_ms)

    def _pause_stimuli_interval(self):
        if not self._stimuli_timer.isActive():
            return False

        elapsed_ms = int((time.monotonic() - self._stimuli_started_at) * 1000)
        self._stimuli_remaining_ms = max(0, self._stimuli_remaining_ms - elapsed_ms)
        self._stimuli_started_at = None
        self._stimuli_timer.stop()
        return True

    def _resume_stimuli_interval(self):
        if self._stimuli_remaining_ms <= 0:
            self._stop_stimuli()
            return

        self._stimuli_started_at = time.monotonic()
        self._stimuli_timer.start(self._stimuli_remaining_ms)

    def _launch_ponk(self):
        self._hide_marker()
        self._photomark_timer.start(50)
    
    def _get_new_bci_isi(self):
        # ВРЕМЯ МЕЖДУ ПОНЬКАМИ
        isi_min_ms = self._ponk_isi_min_ms
        isi_max_ms = self._ponk_isi_max_ms
        return 1000 + int(random.uniform(isi_min_ms, isi_max_ms))

    def _ponk_timer_stop(self):
        self._launch_ponk()
        new_isi = self._get_new_bci_isi()
        print("PONK ISI", new_isi)
        self._ponk_timer.start(new_isi)

    def _start_ponk_timer(self, delay_ms=None):
        if self._ponk_timer.isActive():
            self._ponk_started = True
            return

        self._ponk_started = True
        if delay_ms is None:
            delay_ms = self._get_new_bci_isi()
        self._ponk_timer.start(max(0, int(delay_ms)))

    def _play_countdown_video(self):
        if self._stopped:
            return

        self._playback_token += 1
        self._countdown_running = True
        self._waiting_for_first_frame = True
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()
        self._show_marker()

        media = self._instance.media_new(START_COUNTDOWN_VIDEO)
        media.parse_async()
        self._player.stop()
        self._player.set_media(media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

    def _start_bci_sequence_after_intro(self):
        if self._stopped:
            return

        self._intro_after_countdown_timer.stop()
        self._intro_after_countdown_started_at = None
        self._intro_after_countdown_remaining_ms = 0
        self._start_ponk_timer()
        self._play_next_stimuli()
    
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
            self._play_countdown_video()
            return

        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            paused_during_countdown = self._countdown_running
            if paused_during_countdown:
                self._player.pause()
            paused_during_intro = False if paused_during_countdown else self._pause_intro_after_countdown_interval()
            paused_during_cross = (
                False if paused_during_countdown or paused_during_intro else self._pause_cross_interval()
            )
            if not paused_during_countdown and not paused_during_intro and not paused_during_cross:
                self._pause_stimuli_interval()
            self._is_paused = True
            self.stimuliPaused.emit()
            if self._ponk_started:
                self._ponk_timer.stop()
            return

        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            if self._countdown_running:
                self._player.play()
            elif self._intro_after_countdown_remaining_ms > 0:
                self._resume_intro_after_countdown_interval()
            elif self._cross_remaining_ms > 0 and not self._waiting_for_first_frame:
                self._resume_cross_interval()
            else:
                self._resume_stimuli_interval()
            self._is_paused = False
            self.stimuliPaused.emit()
            if self._ponk_started:
                self._ponk_timer.start(self._get_new_bci_isi())

    def pause_video(self):
        self._on_space_pressed()

    def restart_sequence(self):
        print("[VLC player]: restart stimuli presentation.")
        self._player.stop()

        self._ponk_timer.stop()
        self._is_paused = False
        self._sequence_started = False
        self._stopped = False
        self._finished = False
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._emit_stimulus_finished()
        self._countdown_running = False
        self._ponk_started = False
        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        self._intro_after_countdown_timer.stop()
        self._intro_after_countdown_started_at = None
        self._intro_after_countdown_remaining_ms = 0

        self._stimuli_timer.stop()
        self._stimuli_started_at = None
        self._stimuli_remaining_ms = 0

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)

        # self._prepare_next_video()
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()
        self._show_marker()

    def finish(self):
        print("[VLC player]: finish the stimuli presentation and close the player.")
        self._stopped = True
        self._playback_token += 1
        self._waiting_for_first_frame = False
        self._emit_stimulus_finished()
        self._countdown_running = False
        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0
        self._show_marker()

        self._intro_after_countdown_timer.stop()
        self._stimuli_timer.stop()
        self._ponk_timer.stop()
        self._player.stop()
        self._player.release()
        self._instance.release()
        if not self._finished:
            QTimer.singleShot(2000, self.stimuliFinished.emit)
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
