import json
import time

from PyQt5.QtCore import QTimer

from .video_player import StimuliPresentation_one_by_one


class StimuliPresentationAntiponk(StimuliPresentation_one_by_one):
    def __init__(
        self,
        monitor=1,
        volume=80,
        rest_stimulus_variants=None,
        wait_for_tension=False,
        tension_timeout_ms=1000,
        tension_wait_stream=None,
    ):
        self._wait_for_tension = bool(wait_for_tension)
        self._tension_timeout_ms = int(tension_timeout_ms)
        self._tension_wait_stream = tension_wait_stream
        self._waiting_for_tension = False
        self._tension_wait_started_at = None
        self._tension_wait_remaining_ms = 0

        super().__init__(
            monitor=monitor,
            volume=volume,
            rest_stimulus_variants=rest_stimulus_variants,
        )

        self._tension_wait_timer = QTimer(self)
        self._tension_wait_timer.setSingleShot(True)
        self._tension_wait_timer.timeout.connect(self._release_tension_wait)

    def set_tension_wait_enabled(self, enabled):
        self._wait_for_tension = bool(enabled)
        self._release_tension_wait()
        if not self._wait_for_tension and self._waiting_for_tension:
            self._release_tension_wait()

    def set_tension_timeout_ms(self, timeout_ms):
        self._tension_timeout_ms = max(0, int(timeout_ms))

    def on_tension_on_message(self, *_args):
        if not self._waiting_for_tension or self._is_paused:
            return
        self._release_tension_wait()

    def _play_next_video(self):
        if self._should_wait_for_tension():
            self._start_tension_wait()
            return

        super()._play_next_video()

    def _should_wait_for_tension(self):
        return (
            self._wait_for_tension
            and not self._stopped
            and not self._waiting_for_tension
            and self._sequence_started
            and self._current_index > 0
            and self._next_media is not None
        )

    def _start_tension_wait(self):
        self._cross_timer.stop()
        self._cross_started_at = None
        self._cross_remaining_ms = 0

        self._waiting_for_tension = True
        self._tension_wait_remaining_ms = max(0, int(self._tension_timeout_ms))
        self._tension_wait_started_at = time.monotonic()
        self._send_tension_wait_message()

        if self._tension_wait_remaining_ms <= 0:
            self._release_tension_wait()
        else:
            self._tension_wait_timer.start(self._tension_wait_remaining_ms)

    def _send_tension_wait_message(self):
        if self._tension_wait_stream is None:
            return

        stimulus = None
        if 0 <= self._current_index < len(getattr(self, "video_names", [])):
            stimulus = self.video_names[self._current_index]

        message = {
            "event": "tension_wait",
            "index": int(self._current_index + 1),
            "stimulus": stimulus,
        }
        self._tension_wait_stream(json.dumps(message))

    def _release_tension_wait(self):
        if not self._waiting_for_tension:
            return

        self._tension_wait_timer.stop()
        self._waiting_for_tension = False
        self._tension_wait_started_at = None
        self._tension_wait_remaining_ms = 0
        super()._play_next_video()

    def _pause_tension_wait_interval(self):
        if not self._tension_wait_timer.isActive():
            return False

        elapsed_ms = int((time.monotonic() - self._tension_wait_started_at) * 1000)
        self._tension_wait_remaining_ms = max(0, self._tension_wait_remaining_ms - elapsed_ms)
        self._tension_wait_started_at = None
        self._tension_wait_timer.stop()
        return True

    def _resume_tension_wait_interval(self):
        if not self._waiting_for_tension:
            return

        if self._tension_wait_remaining_ms <= 0:
            self._release_tension_wait()
            return

        self._tension_wait_started_at = time.monotonic()
        self._tension_wait_timer.start(self._tension_wait_remaining_ms)

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
            paused_during_tension_wait = (
                False if paused_during_cross else self._pause_tension_wait_interval()
            )
            if not paused_during_cross and not paused_during_tension_wait:
                self._player.pause()
            self._is_paused = True
            self.stimuliPaused.emit()
            return

        if self._is_paused:
            print("[VLC player]: continue the stimuli presentation.")
            if self._cross_remaining_ms > 0 and not self._waiting_for_first_frame:
                self._resume_cross_interval()
            elif self._waiting_for_tension:
                self._resume_tension_wait_interval()
            else:
                self._player.play()
            self._is_paused = False
            self.stimuliPaused.emit()

    def restart_sequence(self):
        self._tension_wait_timer.stop()
        self._waiting_for_tension = False
        self._tension_wait_started_at = None
        self._tension_wait_remaining_ms = 0
        super().restart_sequence()

    def finish(self):
        self._tension_wait_timer.stop()
        self._waiting_for_tension = False
        self._tension_wait_started_at = None
        self._tension_wait_remaining_ms = 0
        super().finish()
