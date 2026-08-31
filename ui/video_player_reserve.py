import sys, os, tempfile, subprocess
import time

import vlc

import random

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, QThread
from PyQt5.QtGui import QKeyEvent, QPixmap, QImage

from utils.add_to_json import save_sequence

class StimuliPresentation_onefile(QWidget):
    """
    Проигрывает интро и затем стимулы в заданном порядке на указанном мониторе.
    Входные стимулы должны иметь аудиодорожку.

    Args:
        intro_file (str): путь к интро-видео
        stimuli_files (list[str]): список стимульных видео
        order (list[int]): порядок воспроизведения стимулов
        monitor (int): номер монитора

    Signals:
        stimuliFinished (pyqtSignal): срабатывает после окончания всего воспроизведения
    """
    stimuliFinished = pyqtSignal()
    stimulusStarted = pyqtSignal(str)
    stimulusFinished = pyqtSignal(str)
    stimulus = pyqtSignal(str)

    def __init__(self, stimuli_sequence, save=True, sequence_name=None, monitor=1):
        super().__init__()
        # self._intro_file = os.path.abspath(intro_file)
        self._save = save
        self._order = stimuli_sequence["order"]

        video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        video_names = [os.path.join(path, file) for file in video_names]

        self._stimuli_files = [video_names[i-1] for i in self._order]
    

        # self._stimuli_files = [os.path.abspath(f) for f in stimuli_files]
        # self._order = order
        self._current_video_index = 0
        self._current_stimulus = None
        try: 
            self._temp_file = stimuli_sequence["filename"]
        except:

            

            # Проверка наличия аудио в стимульных файлах
            for idx in self._order:
                if not self._has_audio(self._stimuli_files[idx]):
                    raise RuntimeError(f"Stimulus video has no audio: {self._stimuli_files[idx]}")

            # Создаём комбинированный файл стимулов
            self._temp_file = self._concat_stimuli(self._stimuli_files, self._order)

            if save:
                stimuli_filename = r"resources/saved_stimuli.json"
                stimuli_sequence["filename"] = self._temp_file
                save_sequence(stimuli_filename, sequence_name, stimuli_sequence)

        # Настройка окна на нужный монитор
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        # VLC setup
        self._instance = vlc.Instance('--no-video-title-show', '--quiet', '--avcodec-hw=any', '--file-caching=100')
        self._player = self._instance.media_player_new()

        # Виджет для видео
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self._video_widget)

        if sys.platform.startswith("win"):
            self._player.set_hwnd(int(self._video_widget.winId()))
        elif sys.platform.startswith("linux"):
            self._player.set_xwindow(int(self._video_widget.winId()))
        elif sys.platform.startswith("darwin"):
            self._player.set_nsobject(int(self._video_widget.winId()))

        # Таймер для проверки конца видео
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._check_end)

        # Список видео для проигрывания: сначала интро, потом стимулы
        self._playlist = [self._temp_file]

        self._play_current_video()

    def _has_audio(self, file_path):
        """Проверяет, есть ли аудиодорожка"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            file_path
        ], capture_output=True, text=True)
        return bool(result.stdout.strip())

    def _concat_stimuli(self, files, order):
        """Быстро объединяет стимулы в один файл"""
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "combined_stimuli.mp4")
        
        # Создаём list.txt для ffmpeg concat
        list_file = os.path.join(temp_dir, "stimuli_list.txt")
        with open(list_file, "w") as f:

            for file in files:
                f.write(f"file '{os.path.abspath(file)}'\n")

        # Склеиваем быстро, видео копируем, аудио перекодируем в AAC
        subprocess.run([
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            temp_file
        ], check=True)
        # subprocess.run([
        #     "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        #     "-i", list_file,
        #     "-c:v", "copy",
        #     "-c:a", "aac",
        #     "-b:a", "128k",
        #     temp_file
        # ], check=True)

        return temp_file

    def _play_current_video(self):
        stimulus = self._playlist[self._current_video_index]
        self._player.set_media(self._instance.media_new(stimulus))
        self._emit_stimulus_started(stimulus)
        self._player.play()
        self._timer.start()

    def _check_end(self):
        state = self._player.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
            self._timer.stop()
            self._emit_stimulus_finished()
            self._current_video_index += 1
            if self._current_video_index < len(self._playlist):
                self._play_current_video()
            else:
                self.stimuliFinished.emit()
                self._cleanup()

    def _cleanup(self):
        """Остановить плеер и удалить временный файл"""
        self._emit_stimulus_finished()
        if self._player is not None:
            self._player.stop()
            self._player.set_media(None)
            self._player.release()
            self._instance.release()

        if os.path.exists(self._temp_file):
            try:
                if not self._save:
                    os.remove(self._temp_file)
            except PermissionError:
                print(f"Не удалось удалить временный файл: {self._temp_file}")

        self.close()

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

    def keyPressEvent(self, event):
        """Esc для остановки воспроизведения"""
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape:
            self.stimuliFinished.emit()
            self._cleanup()
        else:
            super().keyPressEvent(event)

