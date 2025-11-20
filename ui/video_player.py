import sys
import os
import ctypes
# путь к папке, где установлен VLC
# vlc_dir = r"C:\Program Files\VideoLAN\VLC"

# # указываем путь к libvlc.dll
# if sys.platform.startswith("win"):
#     libvlc_path = os.path.join(vlc_dir, "libvlc.dll")
#     ctypes.CDLL(libvlc_path)

import vlc
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QSlider, QLabel, QHBoxLayout, QSpinBox
)
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist
from PyQt5.QtMultimediaWidgets import QVideoWidget

import time

class StimuliPresentation(QWidget):
    def __init__(self, video_file, monitor=1):
        """
        :param video_file: путь к видеофайлу
        :param monitor: номер монитора (1,2,...)
        """
        super().__init__()

        # Настройка окна на нужный монитор
        screens = QApplication.instance().screens()
        monitor_index = monitor - 1
        screen = screens[monitor_index]
        target_monitor = screen.geometry()
        self.setGeometry(target_monitor)
        self.showFullScreen()
        self.setWindowTitle("VLC Video Player")

        self.video_file = video_file

        # --- VLC setup ---
        self.instance = vlc.Instance("--start-time=0")
        self.player = self.instance.media_player_new()

        # Основной виджет для видео
        self.video_widget = QWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.video_widget)

        # Привязываем видео к PyQt5 виджету
        if sys.platform.startswith("win"):
            self.player.set_hwnd(int(self.video_widget.winId()))
        elif sys.platform.startswith("linux"):
            self.player.set_xwindow(int(self.video_widget.winId()))
        elif sys.platform.startswith("darwin"):
            self.player.set_nsobject(int(self.video_widget.winId()))

        # VLC событие окончания видео
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)

        self._play_video()

    def _play_video(self):
        """Проигрываем видео"""
        media = self.instance.media_new(self.video_file)
        self.player.set_media(media)
        self.player.play()

    def _on_end_reached(self, event):
        """Событие окончания видео"""
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        """Escape останавливает видео и закрывает окно"""
        if event.key() == Qt.Key_Escape:
            if self.player is not None:
                self.player.stop()
            self.close()
        else:
            super().keyPressEvent(event)

class StimuliPresentation_old(QWidget):
    def __init__(self, filename, monitor):
        super().__init__()
        monitor_index = monitor - 1

        self.setWindowTitle("PyQt5 Video Player")
        
        screens = QApplication.instance().screens()
        screen = screens[monitor_index]
        target_monitor = screen.geometry()
        self.setGeometry(target_monitor)             # Переносим окно на нужный монитор
        self.showFullScreen()                   

        self._fl = filename
        self._init()

    def _init(self):

        # --- скрытый виджет для предварительной буферизации ---
        self._preloadWidget = QVideoWidget()
        self._preloadPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self._preloadPlayer.setVideoOutput(self._preloadWidget)
        self._preloadPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(self._fl)))
        
        # Проигрываем первые 700 мс (пример)
        self._preloadPlayer.play()
        QTimer.singleShot(700, self._start_main_player)  # через 0.7 сек запускаем основной плеер

    def _start_main_player(self):
        # останавливаем скрытый плеер
        self._preloadPlayer.stop()
        self._preloadPlayer.deleteLater()
        self._preloadWidget.deleteLater()

        self._videoWidget = QVideoWidget()   # виджет видео
        self._videoWidget.setFullScreen(True)  # включаем полноэкранный режим
        self._videoWidget.setAspectRatioMode(Qt.IgnoreAspectRatio)
        # # --- основной layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # убираем внутренние отступы
        layout.setSpacing(0)                   # убираем расстояние между элементами

        layout.addWidget(self._videoWidget)

        self._mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)   # медиаплеер
        self._mediaPlayer.setVideoOutput(self._videoWidget)

        video = QMediaContent(QUrl.fromLocalFile(self._fl))
        self._mediaPlayer.setMedia(video)

        self._mediaPlayer.mediaStatusChanged.connect(self._on_media_status_changed)
    
    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.LoadedMedia:
            self._mediaPlayer.play()  # запускаем только после полной загрузки
        if status == QMediaPlayer.EndOfMedia:
            self.close()  # закрываем окно, когда видео закончилось

    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._mediaPlayer.stop()
            self.close()  # Закрываем окно
        else:
            super().keyPressEvent(event)

class StimuliPresentation_from_pieces(QWidget):
    def __init__(self, params):
        super().__init__()
        monitor_index=0

        self.setWindowTitle("PyQt5 Video Player")
        
        screens = QApplication.instance().screens()
        screen = screens[monitor_index]
        target_monitor = screen.geometry()
        self.setGeometry(target_monitor)             # Переносим окно на нужный монитор
        self.showFullScreen()                   

        self._params = params
    
        self._init()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._finalization()

    def _init(self):
        idx_list =  [1 for _ in range(self._params["before_s"])] +\
                    [2] +\
                    [1 for _ in range(self._params["after_s"])]
        
        self._idx_list = [0] + idx_list * self._params["n_stimuli"] + [1]
        self._idx = 0

        intro_video_fl = self._params["intro_video"] + f"_{self._params['countdown_s']}.mp4"
        self._videos = [intro_video_fl, self._params["cross_video"], self._params["stimuli_video"]]
    
    def _setup_ui(self):
        self._videoWidget = QVideoWidget()   # виджет видео
        # --- основной layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._videoWidget)

        self._mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)   # медиаплеер
        self._mediaPlayer.setVideoOutput(self._videoWidget)
        
        # создаём плейлист с тремя видео
        self._playlist = QMediaPlaylist()
        for video_name in self._videos:
            self._playlist.addMedia(self._load_video(video_name))
        self._playlist.setPlaybackMode(QMediaPlaylist.Sequential)

        self._mediaPlayer.setPlaylist(self._playlist)
    
    def _setup_layout(self):
        
        if False:
            print('hi')
    
    def _setup_connections(self):
        self._playlist.currentIndexChanged.connect(self._on_index_changed)
        # self.mediaPlayer.durationChanged.connect(self.update_duration)
        # self._mediaPlayer.positionChanged.connect(self.update_position)
        # self.mediaPlayer.mediaStatusChanged.connect(self._handle_status) # когда видео заканчивается
        # self._mediaPlayer.stateChanged.connect(self._handle_status) # когда видео заканчивается
        # self._mediaPlayer.mediaStatusChanged.connect(self._on_loaded)    # чтобы запускать следующее видео тогда, когда оно подгружено

    def _load_video(self, filename):
        path = os.path.join(self._params["video_folder"], filename)
        print(path, os.path.exists(path))
        return QMediaContent(QUrl.fromLocalFile(path))

    def _set_next_video(self):
        if self._idx >= len(self._idx_list):
            print("Все видео проиграны")
            return
        idx = self._idx_list[self._idx]
        self._playlist.setCurrentIndex(idx)
        self._idx += 1

    def _on_index_changed(self, index):
        # если закончили блок video2->video3
        if self._idx < len(self._idx_list):
            self._set_next_video()
    
    def _finalization(self):
        self._mediaPlayer.play()

          # -----------------------------
    # Открытие файла
    # -----------------------------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать видео", "", "Видео (*.mp4 *.avi *.mov *.mkv)"
        )
        if path:
            self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(path)))

    # -----------------------------
    # Старт / Пауза
    # -----------------------------
    def toggle_play(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            # перейти к стартовой позиции диапазона
            start_ms = self.start_box.value() * 1000
            self.mediaPlayer.setPosition(start_ms)
            self.mediaPlayer.play()

    # -----------------------------
    # Обновление длительности
    # -----------------------------
    def update_duration(self, duration):
        self.slider.setRange(0, duration)
        # установить лимит stop_box = длительность
        self.stop_box.setValue(duration // 1000)

    # -----------------------------
    # Обновление позиции (контроль диапазона)
    # -----------------------------
    def update_position(self, pos):
        # self.slider.setValue(pos)


        # если вышли за пределы — стоп
        if pos < self._start_ms:
            self.mediaPlayer.setPosition(self._start_ms)

        if pos >= self._stop_ms:
            self.mediaPlayer.pause()

            # вернуться в начало диапазона
            self.mediaPlayer.setPosition(self._start_ms)

            # для автоматического повторения — раскомментируй:
            # self.mediaPlayer.play()
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.close()  # Закрываем окно
        else:
            super().keyPressEvent(event)


class VideoPlayer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PyQt5 Video Player")
        self.resize(800, 600)

        # --- основной layout ---
        layout = QVBoxLayout(self)

        # виджет видео
        self.videoWidget = QVideoWidget()
        layout.addWidget(self.videoWidget)

        # медиаплеер
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.mediaPlayer.setVideoOutput(self.videoWidget)

        # --- кнопки ---
        btn_open = QPushButton("Открыть видео")
        btn_play = QPushButton("▶ / ⏸")
        btn_open.clicked.connect(self.open_file)
        btn_play.clicked.connect(self.toggle_play)

        h1 = QHBoxLayout()
        h1.addWidget(btn_open)
        h1.addWidget(btn_play)
        layout.addLayout(h1)

        # --- слайдер позиционирования ---
        self.slider = QSlider(Qt.Horizontal)
        self.slider.sliderMoved.connect(self.mediaPlayer.setPosition)
        layout.addWidget(self.slider)

        # --- диапазон воспроизведения ---
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Старт (сек):"))
        self.start_box = QSpinBox()
        self.start_box.setMaximum(9999)
        h2.addWidget(self.start_box)

        h2.addWidget(QLabel("Стоп (сек):"))
        self.stop_box = QSpinBox()
        self.stop_box.setMaximum(9999)
        h2.addWidget(self.stop_box)

        layout.addLayout(h2)

        # сигналы позиции и длительности
        self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.positionChanged.connect(self.update_position)

    # -----------------------------
    # Открытие файла
    # -----------------------------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать видео", "", "Видео (*.mp4 *.avi *.mov *.mkv)"
        )
        if path:
            self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(path)))

    # -----------------------------
    # Старт / Пауза
    # -----------------------------
    def toggle_play(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            # перейти к стартовой позиции диапазона
            start_ms = self.start_box.value() * 1000
            self.mediaPlayer.setPosition(start_ms)
            self.mediaPlayer.play()

    # -----------------------------
    # Обновление длительности
    # -----------------------------
    def update_duration(self, duration):
        self.slider.setRange(0, duration)
        # установить лимит stop_box = длительность
        self.stop_box.setValue(duration // 1000)

    # -----------------------------
    # Обновление позиции (контроль диапазона)
    # -----------------------------
    def update_position(self, pos):
        self.slider.setValue(pos)

        start_ms = self.start_box.value() * 1000
        stop_ms = self.stop_box.value() * 1000

        # если вышли за пределы — стоп
        if pos < start_ms:
            self.mediaPlayer.setPosition(start_ms)

        if pos >= stop_ms:
            self.mediaPlayer.pause()

            # вернуться в начало диапазона
            self.mediaPlayer.setPosition(start_ms)

            # для автоматического повторения — раскомментируй:
            # self.mediaPlayer.play()


# -----------------------------
# Запуск приложения
# -----------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player = StimuliPresentation()
    player.show()
    sys.exit(app.exec())