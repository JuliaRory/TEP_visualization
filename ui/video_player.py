import sys, os, time, tempfile, subprocess
import time

import vlc

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QKeyEvent


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

    def __init__(self, intro_file, stimuli_files, order, monitor=1):
        super().__init__()
        self._intro_file = os.path.abspath(intro_file)
        self._stimuli_files = [os.path.abspath(f) for f in stimuli_files]
        self._order = order
        self._current_video_index = 0

        # Проверка наличия аудио в стимульных файлах
        for idx in order:
            if not self._has_audio(self._stimuli_files[idx]):
                raise RuntimeError(f"Stimulus video has no audio: {self._stimuli_files[idx]}")

        # Создаём комбинированный файл стимулов
        self._temp_file = self._concat_stimuli(self._stimuli_files, self._order)

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
        self._playlist = [self._intro_file, self._temp_file]

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

        # Сортируем по order
        files = [files[i] for i in order]

        # Создаём list.txt для ffmpeg concat
        list_file = os.path.join(temp_dir, "stimuli_list.txt")
        with open(list_file, "w") as f:
            for file in files:
                f.write(f"file '{file}'\n")

        # Склеиваем быстро, видео копируем, аудио перекодируем в AAC
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            temp_file
        ], check=True)

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

class StimuliPresentation_one_by_one(QWidget):
    """
    Класс для последовательного воспроизведения серии стимулов в указанном порядке.
    
    Args:
        video_files  (list[str]):    Пути к видеофайлам.
        order        (list[int]):    Порядок воспроизведения (индексы video_files).
        monitor      (int):          Номер монитора для полноэкранного вывода.
    
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

    _videoEnded = pyqtSignal()      # сигнал окончания очередного видео
    # stimuliFinished = pyqtSignal()  # сигнал окончания последовательности стимулов

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
        self._current_index = 0                  # индекс текущего видео в order

        # == VLC setup ==
        self._instance = vlc.Instance(
            '--file-caching=50',           # буферизация
            '--avcodec-hw=any',       # аппаратное декодирование
            '--no-video-title-show',
            '--quiet'                       # минимизация логов
            )
        self._medias = [self._instance.media_new(f) for f in self.video_files]
        
        self._player = self._instance.media_player_new()
        
        # == Контейнер для вывода ==
        self._video_widget = QWidget(self)
        self._video_widget.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        layout.addWidget(self._video_widget)

        # Привязываем видео к PyQt5 виджету
        if sys.platform.startswith("win"):
            self._player.set_hwnd(int(self._video_widget.winId()))        # сообщаем плееру ID системного окна
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
        """
        Проигрывает следующее видео из списка order.
        Закрывает плеер, когда все видео из списка воспроизведены.
        """
        
        if self._current_index >= len(self.order):
            self.close()
            return

        video_idx = self.order[self._current_index]
        video_path = self.video_files[video_idx-1]

        print(f"Video #{self._current_index}: {video_path}")
        self._start_time = time.perf_counter()

        # создаём новый экземпляр media для каждого видео
        # media = self._instance.media_new(video_path)
        self._player.set_media(self._medias[video_idx-1])
        # self._player.set_media(media)
        self._video_widget.update()
        self._player.play()

        self._current_index += 1
       
    def _on_end_reached(self, event):
        """
        Вызывается, когда получает сигнал о завершении очередного видео. 
        Срабатывает :attr:`_videoEnded` для вызова функции запуска следующего видео  в GUI-потоке.
        """
        end_time = time.perf_counter()
        print(f"--duration: {(end_time - self._start_time):.3f} s")
        self._videoEnded.emit()

    def keyPressEvent(self, event: QKeyEvent):
        """
        Останавливает воспроизведение видео и закрывает окно по нажатию на esc.
        Срабатывает :attr:`stimuliFinished` для сообщения вовне о заверешении показа стимулов.
        Args:
            event (QKeyEvent): Key press event.
        """
        if event.key() == Qt.Key_Escape:
            if self._player is not None:
                self._player.stop()
            # self.stimuliFinished.emit()
            self.close()
        else:
            super().keyPressEvent(event)

