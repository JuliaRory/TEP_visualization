import sys, os, time, tempfile, subprocess
import time

import vlc
import cv2

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

class StimuliPresentation(QWidget):
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

class StimuliPresentation_one_by_onefdf(QWidget):
    _videoEnded = pyqtSignal()  # сигнал окончания очередного видео

    def __init__(self, stimuli_sequence, monitor=1):
        super().__init__()

        # == Монитор и окно ==
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        # == Данные ==
        self.order = stimuli_sequence["order"]
        video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        video_names = [os.path.join(path, file) for file in video_names]
        self.video_files = [video_names[i-1] for i in self.order]

        print(self.video_files, self.order)
        self._current_index = 0
        self._start_time = 0

        # == VLC setup ==
        self._instance = vlc.Instance([
            '--file-caching=500',
            '--network-caching=500',
            '--no-video-title-show',
            '--quiet',
            '--avcodec-hw=dxva2',  # аппаратное декодирование на Windows
        ])

        if self._instance is None:
            raise RuntimeError("Не удалось создать VLC Instance! Проверьте аргументы.")

        self._player = self._instance.media_player_new()

        # == Контейнер для вывода ==
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._video_widget)

        if sys.platform.startswith("win"):
            self._player.set_hwnd(int(self._video_widget.winId()))
        elif sys.platform.startswith("linux"):
            self._player.set_xwindow(int(self._video_widget.winId()))
        elif sys.platform.startswith("darwin"):
            self._player.set_nsobject(int(self._video_widget.winId()))

        # == События VLC ==
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        # Подключаем сигнал окончания видео к запуску следующего видео
        self._videoEnded.connect(self._play_next_video)

        # Запуск первого видео
        self._play_next_video()

    def _play_next_video(self):
        if self._current_index >= len(self.video_files):
            QTimer.singleShot(100, self.close)
            return

        video_path = self.video_files[self._current_index]
        print("Playing:", video_path)
        self._start_time = time.perf_counter()

        media = self._instance.media_new(video_path)
        self._player.set_media(media)

        # Прогрев потока для устранения черного экрана
        self._player.play()
        self._player.pause()
        QTimer.singleShot(30, self._player.play)

        self._current_index += 1

    def _on_end_reached(self, event):
        end_time = time.perf_counter()
        print(f"--duration: {(end_time - self._start_time):.3f} s")

        # Эмитим сигнал в главном потоке безопасно
        # QMetaObject.invokeMethod(self, "_emit_video_ended", Qt.QueuedConnection)
        QTimer.singleShot(0, lambda: self._videoEnded.emit())

    def _emit_video_ended(self):
        self._videoEnded.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            if self._player is not None:
                self._player.stop()
            self.close()
        else:
            super().keyPressEvent(event)

class StimuliPresentation_one_by_one(QWidget):
    stimuliFinished = pyqtSignal()

    def __init__(self, stimuli_sequence, monitor=1):
        super().__init__()  

        self._stopped = False
        self._cross_dur_ms = stimuli_sequence["cross"]["dur_ms"]      # проигрвать крест 
        self.placeholder_path = os.path.join(r"resources\crossFigures", stimuli_sequence["cross"]["filename"])

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
        self._placeholder_widget.setGeometry(self.rect())
        self._placeholder_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_widget.setStyleSheet("background-color: black;")
        self._placeholder_widget.show()

        # Запуск воспроизведения
        self._play_next_video()
        # self._show_placeholder_then_play()

    def _show_placeholder_then_play(self):
        """Показываем placeholder, затем запускаем видео через короткую задержку"""
        self._placeholder_widget.show()

        QTimer.singleShot(self._cross_dur_ms, self._play_next_video)  

    def _play_next_video(self):
        if self._stopped:
            return
        if self._current_index >= len(self.video_files):
            
            QTimer.singleShot(50, self._end)
            return

        video_path = self.video_files[self._current_index]
        media = self._instance.media_new(video_path)
        media.parse_async()  # preload

        self._player.set_media(media)
        self._player.play()

        # Скрываем placeholder через 50ms после старта VLC
        delay = 100 if self._current_index > 0 else 0
        QTimer.singleShot(delay, self._placeholder_widget.hide)

        self._current_index += 1
        # Проверяем окончание видео каждые 50ms
        QTimer.singleShot(50, self._check_video_end)

    def _check_video_end(self):
        if self._stopped:
            return  # больше ничего не делаем
        if self._player.get_state() == vlc.State.Ended:
            # Сразу показываем placeholder перед следующим видео
            self._placeholder_widget.show()
            QTimer.singleShot(self._cross_dur_ms, self._play_next_video)
        else:
            QTimer.singleShot(50, self._check_video_end)

    def _end(self):
        self.stimuliFinished.emit()
        self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._stopped = True           # ставим флаг остановки
            self._player.stop()
            self._player.release()
            self._instance.release()
            self._end()
        else:
            super().keyPressEvent(event)



class StimuliPresentation_one_by_onаааe(QWidget):
    """
    Класс для последовательного воспроизведения серии стимулов в указанном порядке.
    
    Args:
        stimuli_sequence  (dict{}):    Имена видеофайлов и последовательность. 
        monitor      (int):            Номер монитора для полноэкранного вывода.
    
    Signals:
        _videoEnded (pyqtSignal):  
                Срабатывает, когда VLC заканчивает проигрывать очередное видео. 
                **Внутренний сигнал**: используется для связки видео в VLC-плеере. Не для внешнего использования.
        stimuliFinished (pyqtSignal):
                Срабатывает, когда все видео в последовательности стимулов проиграны. Для использования извне.
    
    Example:
        >>> widget = StimuliPresentation(
        ...     video_files=["a.mp4", "b.mp4", "c.mp4"],
        ...     order=[2, 0, 1],
        ...     monitor=1
        ... )
        >>> widget.stimuliFinished.connect(on_stimuli_finished)
        >>> widget.show()
    """
    _videoEnded = pyqtSignal()

    def __init__(self, stimuli_sequence, monitor=1):
        super().__init__()

        # === Настройка экрана ===
        screens = QApplication.instance().screens()
        target_monitor = screens[monitor - 1].geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()

        # === Список видео ===
        self.order = stimuli_sequence["order"]
        video_names = list(stimuli_sequence["set"].values())
        path = r"resources\videoSamples"
        video_names = [os.path.join(path, file) for file in video_names]
        self.video_files = [video_names[i-1] for i in self.order]
        self._current_index = 0

        # === VLC ===
        self._instance = vlc.Instance('--file-caching=1000','--no-video-title-show','--quiet')
        self._player = self._instance.media_player_new()
        self._next_media = None

        # === Видео виджет ===
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

        # === QLabel для первого кадра ===
        self._frame_label = QLabel(self._video_widget)
        self._frame_label.setAlignment(Qt.AlignCenter)
        self._frame_label.setStyleSheet("background-color: black;")
        self._frame_label.setGeometry(self._video_widget.rect())
        self._frame_label.show()

        # === События VLC ===
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        self._videoEnded.connect(self._play_next_video)

        # === Подготовка и запуск ===
        self._prepare_next_video()
        self._play_next_video()

    # === Подготовка следующего видео ===
    def _prepare_next_video(self):
        if self._current_index >= len(self.video_files):
            self._next_media = None
            return

        video_path = self.video_files[self._current_index]
        self._next_media = self._instance.media_new(video_path)
        self._next_media.parse_async()

        # === Получаем первый кадр через OpenCV ===
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_image)
            self._frame_label.setPixmap(pixmap.scaled(self._video_widget.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._frame_label.show()
        cap.release()

    # === Воспроизведение следующего видео ===
    def _play_next_video(self):
        if self._next_media is None:
            QTimer.singleShot(50, self.close)
            return

        self._player.stop()
        self._player.set_media(self._next_media)
        self._player.play()
        self._start_time = time.perf_counter()

        # Скрываем QLabel после начала воспроизведения
        QTimer.singleShot(50, lambda: self._frame_label.hide())

        # Подготовка следующего видео
        self._current_index += 1
        self._prepare_next_video()

    # === Конец видео ===
    def _on_end_reached(self, event):
        QTimer.singleShot(0, lambda: self._videoEnded.emit())
        print(f"Video finished in {time.perf_counter() - self._start_time:.3f} s")

    # === Esc для выхода ===
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._stopped = True
            self._player.stop()
            self._player.release()
            self._instance.release()
            self.close()
        else:
            super().keyPressEvent(event)