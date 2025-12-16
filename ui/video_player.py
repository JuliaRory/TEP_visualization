import sys, os, time, tempfile, subprocess
import time

import vlc

import random

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, QThread
from PyQt5.QtGui import QKeyEvent, QPixmap, QImage

from utils.add_to_json import save_sequence

# воспроизведение стимулов идёт через VLC плеер (https://www.videolan.org/vlc/) <-- он должен быть установлен на компьютер (!!!) 
# на питоне для этого устанавливается библиотека python-vlc (https://pypi.org/project/python-vlc/)
# его необходимо привязать к системному окну открываемого QWidget
# ┌─────────────────────────────────────────────┐
# │ StimuliPresentation : QWidget (fullscreen)  │
# │┌───────────────────────────────────────────┐│
# ││       VLC выводит сюда картинку           ││
# │└───────────────────────────────────────────┘│
# └─────────────────────────────────────────────┘
# сигнал об окончании видео и переключении на новое реализован через pyqtSignal(), чтобы вписывать событие в общий поток GUI:
#  ┌──────────────┐              ┌──────────────┐
#  │ VLC thread   │ --emit-->    │ Qt event loop│
#  │ end reached  │              │ (GUI thread) │
#  └──────────────┘              └──────────────┘
#                                   |
#                                   ↓
#                         _play_next_video()
# 
# закрытие окна (и остановка видео) происходит при нажатии на кнопку Escape или по окончании последовательности стимулов
# окончание последовательности стимулов вызывает сигнал stimuliFinished

class StimuliPresentation_one_by_one(QWidget):
    stimuliFinished = pyqtSignal()
    volumeChanged = pyqtSignal(int)
    playerIsMuted = pyqtSignal()
    _videoEnded = pyqtSignal()

    def __init__(self, stimuli_sequence, monitor=1, volume=80):
        super().__init__()  

        self._volume = volume

        self._stopped = False
        self._finished = False
        self._sequence_started = False
        self._is_paused = False
        self._cross_dur_ms = stimuli_sequence["cross"]["dur_ms"]      # проигрвать крест 
        self.placeholder_path = os.path.join(r"resources\crossFigures", stimuli_sequence["cross"]["filename"])

        # self.final_pic_path = os.path.join(r"resources\crossFigures", "final_picture.png")
        final_fig_files = os.listdir(r"resources\final_fig")
        self.final_pic_path = os.path.join(r"resources\final_fig", random.choice(final_fig_files))
        print(self.final_pic_path)

        # self.final_pic_path = os.path.join(r"resources\final_fig", "final_1.png")

        # Настройка экрана
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        # Видео
        self.order = stimuli_sequence["order"]
        video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        video_names = [os.path.join(path, file) for file in video_names]
        self.video_files = [video_names[i-1] for i in self.order]
        self._current_index = 0

        # VLC
        self._instance = vlc.Instance(
            '--file-caching=100',
            '--no-video-title-show',
            '--quiet',
            '--no-sub-autodetect-file', 
            '--no-spu'
            )
        self._player = self._instance.media_player_new()

        # Привязка событий
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        # Видео виджет
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self._video_widget)

        winid = int(self._video_widget.winId())
        if sys.platform.startswith("win"):
            self._player.set_hwnd(winid)
        elif sys.platform.startswith("linux"):
            self._player.set_xwindow(winid)
        elif sys.platform.startswith("darwin"):
            self._player.set_nsobject(winid)

        # === Placeholder widget поверх всего ===
        self._placeholder_widget = QLabel(self)
        self._placeholder_widget.setPixmap(
            QPixmap(self.placeholder_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        self._final_pic = QPixmap(self.final_pic_path).scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._placeholder_widget.show()

        # Запуск воспроизведения
        self._prepare_next_video()
        print('[VLC player]: press Space to start.')
        
    def _show_placeholder_then_play(self):
        """Показываем placeholder, затем запускаем видео через короткую задержку"""
        self._placeholder_widget.show()

        QTimer.singleShot(self._cross_dur_ms, self._play_next_video)  

    def _prepare_next_video(self):
        
        if self._current_index >= len(self.video_files):
            self._next_media = None
            return

        video_path = self.video_files[self._current_index]
        media = self._instance.media_new(video_path)
        media.parse_async()  # preload

        # self._player.set_media(media)

        # Сохраняем для следующего проигрывания
        self._next_media = media

        
    def _play_next_video(self):
        if self._stopped:
            print('[VLC player]: stimuli presentation was stopped.')
            return
        
        if self._next_media is None:
            print("[VLC player]: stimuli sequence was ended.")
            self.stimuliFinished.emit()
            self._finished = True

            self._placeholder_widget.setPixmap(self._final_pic)
            self._placeholder_widget.show()
            return
        
        self._placeholder_widget.show()
        
        # self._player.stop()
        self._player.set_media(self._next_media)
        self._player.audio_set_volume(self._volume)
        self._player.play()

        self._current_index += 1
        self._prepare_next_video()
        self._is_paused = False

        # Скрываем placeholder через 50ms после старта VLC
        delay = 50 # if self._current_index > 0 else 0
        QTimer.singleShot(delay, self._placeholder_widget.hide)

        # Проверяем окончание видео каждые 50ms
        QTimer.singleShot(50, self._check_video_end)
    
        # Таймер для плавной замены: placeholder за 100 мс до конца
        # QTimer.singleShot(50, self._schedule_placeholder_before_end)

    # Показ placeholder за 100 мс до конца видео
    def _schedule_placeholder_before_end(self, pre_ms=100):
        length = self._player.get_length()
        if length <= 0:
            # если длина ещё не готова, повторяем через 50 мс
            QTimer.singleShot(50, self._schedule_placeholder_before_end)
            return
        remaining = max(0, length - self._player.get_time() - pre_ms)
        QTimer.singleShot(remaining, self._placeholder_widget.show)

    def _wait_for_first_frame(self):
        state = self._player.get_state()
        if state in (vlc.State.Playing, vlc.State.Buffering):
            # первый кадр уже рендерится
            self._placeholder_widget.hide()
        else:
            # повторяем проверку каждые 30 мс
            QTimer.singleShot(30, self._wait_for_first_frame)

    def _check_video_end(self):
        if self._stopped:
            return  # больше ничего не делаем
        if self._player.get_state() == vlc.State.Ended:
            # Сразу показываем placeholder перед следующим видео
            self._placeholder_widget.show()
            QTimer.singleShot(self._cross_dur_ms, self._play_next_video)
        else:
            QTimer.singleShot(50, self._check_video_end)
    
    def _on_end_reached(self, event):
        if self._is_paused:
            return  # если вдруг pause совпал с концом
        
        QTimer.singleShot(0, self._videoEnded.emit)

    def _on_space_pressed(self):
        # 1️⃣ Последовательность ещё не запускалась
        if not self._sequence_started:
            print("[VLC player]: start the stimuli presentation.")
            self._sequence_started = True
            self._is_paused = False
            self._play_next_video()
            return

        # 2️⃣ Видео играет → пауза
        if not self._is_paused:
            print("[VLC player]: pause the stimuli presentation.")
            self._player.pause()
            self._is_paused = True
            return

        # 3️⃣ Видео на паузе → продолжить
        print("[VLC player]: continue the stimuli presentation.")
        self._player.play()
        self._is_paused = False

    def update_volume(self, value):
        self._volume = value
        self._player.audio_set_volume(self._volume)
        # print("Volume:", self._volume)
    
    def get_last_volume(self):
        return self._volume

    def keyPressEvent(self, event):
        # start|stop regulation
        if event.key() == Qt.Key_Space:
            self._on_space_pressed()

        # closing regulation
        elif event.key() == Qt.Key_Escape:
            print("[VLC player]: finish the stimuli presentation and close the player.")
            self._stopped = True           # ставим флаг остановки
            self._player.stop()
            self._player.release()
            self._instance.release()
            if not self._finished:
                self.stimuliFinished.emit()
            self.close()

        # volume regulation
        elif event.key() == Qt.Key_Up:
            self._volume = min(100, self._volume + 1)
            self._player.audio_set_volume(self._volume)
            self.volumeChanged.emit(self._volume)
            # print("Volume:", self._volume)

        elif event.key() == Qt.Key_Down:
            self._volume = max(0, self._volume - 1)
            self._player.audio_set_volume(self._volume)
            self.volumeChanged.emit(self._volume)
            # print("Volume:", self._volume)

        elif event.key() == Qt.Key_M:
            self._player.audio_toggle_mute()
            self.playerIsMuted.emit()

        else:
            super().keyPressEvent(event)
            
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
        self._player.set_media(self._instance.media_new(self._playlist[self._current_video_index]))
        self._player.play()
        self._timer.start()

    def _check_end(self):
        state = self._player.get_state()
        if state in (vlc.State.Ended, vlc.State.Stopped, vlc.State.Error):
            self._timer.stop()
            self._current_video_index += 1
            if self._current_video_index < len(self._playlist):
                self._play_current_video()
            else:
                self.stimuliFinished.emit()
                self._cleanup()

    def _cleanup(self):
        """Остановить плеер и удалить временный файл"""
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

    def keyPressEvent(self, event):
        """Esc для остановки воспроизведения"""
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape:
            self.stimuliFinished.emit()
            self._cleanup()
        else:
            super().keyPressEvent(event)

