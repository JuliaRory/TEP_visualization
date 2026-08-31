import os
import random
import re

import vlc
from PyQt5.QtCore import QTimer

from .video_player import StimuliPresentation_one_by_one


PHASES_FOLDER = r"resources\phases"
VIDEO_SAMPLES_FOLDER = r"resources\videoSamples"
PHASE_STIMULUS_NUMBERS = set(range(1, 7))
VIDEO_SAMPLE_STIMULUS_NUMBERS = {7}


class StimuliPresentationPhases(StimuliPresentation_one_by_one):
    """Video player mode for phase-randomized stimuli.

    The regular player resolves all video names once when a sequence is loaded.
    Phases mode resolves stimuli 1..6 immediately before playback so every
    occurrence can get a fresh random phase file.
    """

    PHASE_BINS = {
        -400: (-500, -250, True, True),
        -200: (-250, -150, False, True),
        -100: (-150, -75, False, True),
        -50: (-75, 25, False, True),
        0: (-25, 25, False, False),
    }

    _TMS_RE = re.compile(r"_tms_([+-]?\d+)ms")

    def __init__(self, monitor=1, volume=80, rest_stimulus_variants=None, delay_ms=0):
        self._phase_delay_ms = int(delay_ms)
        self._phase_media_by_filename = {}
        self._phase_ms_by_filename = {}
        self._phase_filename_by_ms = {}
        self._phase_available_ms = []
        self._media_by_path = {}

        super().__init__(
            monitor=monitor,
            volume=volume,
            rest_stimulus_variants=rest_stimulus_variants,
        )

        self.set_isi_range(1, 2)
        self._preload_phase_media()

    def set_phase_delay(self, delay_ms):
        self._phase_delay_ms = int(delay_ms)

    def set_isi_range(self, min_s, max_s):
        super().set_isi_range(1, 2)

    def set_sequence(self, stimuli_sequence, seq_name=None):
        if seq_name is None:
            seq_name = "a new"
        print(f"[VLC player Phases]: set {seq_name} stimuli sequence.")
        self._placeholder_widget.setPixmap(self._intro_pic)
        self._placeholder_widget.show()
        self._show_marker()

        self._cross_dur_ms = stimuli_sequence["cross"]["dur_ms"]
        self.placeholder_path = os.path.join(
            r"resources\crossFigures", stimuli_sequence["cross"]["filename"]
        )

        self._main_cross_pic = self._load_scaled_pixmap(self.placeholder_path)

        self.order = stimuli_sequence["order"]
        self.video_names_by_number = {
            int(number): filename for number, filename in stimuli_sequence["set"].items()
        }
        self.video_names = [
            self.video_names_by_number[int(stimulus_number)]
            for stimulus_number in self.order
        ]

        self._current_index = 0
        self.currIdxChanged.emit(self._current_index)

        self._prepare_next_video()
        print("[VLC player Phases]: press Space to start.")

    def _load_scaled_pixmap(self, path):
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPixmap

        return QPixmap(path).scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _preload_phase_media(self):
        if not os.path.isdir(PHASES_FOLDER):
            print(f"[VLC player Phases]: folder not found: {PHASES_FOLDER}")
            return

        for filename in os.listdir(PHASES_FOLDER):
            path = os.path.join(PHASES_FOLDER, filename)
            if not os.path.isfile(path):
                continue

            phase_ms = self._extract_tms_ms(filename)
            if phase_ms is None:
                continue

            media = self._instance.media_new(path)
            media.parse_async()
            self._phase_media_by_filename[filename] = media
            self._phase_ms_by_filename[filename] = phase_ms
            self._phase_filename_by_ms[phase_ms] = filename

        self._phase_available_ms = sorted(self._phase_filename_by_ms)
        print(
            f"[VLC player Phases]: preloaded {len(self._phase_media_by_filename)} phase videos."
        )

    def _prepare_next_video(self):
        self._next_media = None if self._current_index >= len(self.order) else True

    def _play_next_video(self):
        if self._stopped:
            print("[VLC player Phases]: stimuli presentation has been stopped.")
            return

        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        if self._current_index >= len(self.order):
            print("[VLC player Phases]: stimuli sequence has ended.")
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

        stimulus_number = int(self.order[self._current_index])
        base_filename = self.video_names_by_number[stimulus_number]
        filename, media = self._resolve_media(stimulus_number, base_filename)
        self._emit_stimulus_started(filename)

        if self._current_index == 0:
            self._show_marker()
        else:
            self._hide_marker()

        self._playback_token += 1
        self._waiting_for_first_frame = True

        self._player.stop()
        self._player.set_media(media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

        self._current_index += 1
        self.currIdxChanged.emit(self._current_index)
        self._prepare_next_video()
        self._is_paused = False

    def _resolve_media(self, stimulus_number, base_filename):
        if stimulus_number in VIDEO_SAMPLE_STIMULUS_NUMBERS:
            return base_filename, self._media_from_video_samples(base_filename)

        if stimulus_number in PHASE_STIMULUS_NUMBERS:
            phase_filename = self._choose_phase_filename(base_filename)
            return phase_filename, self._phase_media_by_filename[phase_filename]

        return base_filename, self._media_from_video_samples(base_filename)

    def _media_from_video_samples(self, filename):
        path = os.path.join(VIDEO_SAMPLES_FOLDER, filename)
        if path not in self._media_by_path:
            media = self._instance.media_new(path)
            media.parse_async()
            self._media_by_path[path] = media
        return self._media_by_path[path]

    def _choose_phase_filename(self, base_filename):
        if not self._phase_available_ms:
            raise RuntimeError("No phase videos are available.")

        base_ms = self._extract_tms_ms(base_filename)
        if base_ms is None:
            target_ms = self._phase_delay_ms
        else:
            target_ms = self._get_random_ms_for_shifted_bin(base_ms)

        nearest_ms = min(self._phase_available_ms, key=lambda value: abs(value - target_ms))
        return self._phase_filename_by_ms[nearest_ms]

    def _get_random_ms_for_shifted_bin(self, base_ms):
        phase_bin = self.PHASE_BINS.get(base_ms)
        if phase_bin is None:
            return base_ms + self._phase_delay_ms

        low, high, include_low, include_high = phase_bin
        low = low if include_low else low + 1
        high = high if include_high else high - 1
        low += self._phase_delay_ms
        high += self._phase_delay_ms
        if low > high:
            low, high = high, low

        return random.randint(low, high)

    def _extract_tms_ms(self, filename):
        match = self._TMS_RE.search(str(filename))
        if match is None:
            return None
        return int(match.group(1))
