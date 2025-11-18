import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QSlider, QLabel, QHBoxLayout, QSpinBox
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

import time

class StimuliPresentation(QWidget):
    def __init__(self, params):
        super().__init__()
        monitor_index=0

        self.setWindowTitle("PyQt5 Video Player")
        
        screens = QApplication.instance().screens()
        screen = screens[monitor_index]
        target_monitor = screen.geometry()
        self.setGeometry(target_monitor)             # Переносим окно на нужный монитор
        self.showFullScreen()

        # --- основной layout ---
        layout = QVBoxLayout(self)

        # виджет видео
        self.videoWidget = QVideoWidget()
        layout.addWidget(self.videoWidget)

        # медиаплеер
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.mediaPlayer.setVideoOutput(self.videoWidget)


        # # сигналы позиции и длительности
        # self.mediaPlayer.durationChanged.connect(self.update_duration)
        self.mediaPlayer.positionChanged.connect(self.update_position)
        # self.mediaPlayer.mediaStatusChanged.connect(self._handle_status) # когда видео заканчивается
        self.mediaPlayer.stateChanged.connect(self._handle_status) # когда видео заканчивается
        self.mediaPlayer.mediaStatusChanged.connect(self._on_loaded)

        self._start_ms = 0
        self._stop_ms = 0
        # self.show()
        self._params = params
        self._counter = 0
        self._status = None
        self.has_started = False  # новый флаг для первого видео
        self._init()

    def _init(self):
        self._play_intro()

        path = os.path.join(r"resources/videoSamples", self._params["stimuli_video"])
        self._stimuli_video = QMediaContent(QUrl.fromLocalFile(path))
            
    def _play_intro(self):
        path = os.path.join(r"resources/videoSamples", self._params["intro_video"])
        self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self._stop_ms = self._params["countdown_second"] * 1000
        self._status = "intro"
        
        self.mediaPlayer.play()
        
    def _handle_status(self, status):
        if status == 1:
            self.has_started = True

        print(status)
        # QMediaPlayer.EndOfMedia = 7
        # QMediaPlayer.LoadedMedia = 2
        # QMediaPlayer.StoppedState = 6
        if status == 2 and self.has_started:
            if self._status == "intro":
                print('intro')
                self._status = "stimuli"
                self._start_ms = self._params["start_fragment_s"] * 1000
                self._stop_ms = self._params["end_fragment_s"] * 1000

            if self._status == "stimuli" and self._counter <= self._params["n_stimuli"]:
                print('stimuli')
                self.mediaPlayer.setMedia(self._stimuli_video)
                self.mediaPlayer.setPosition(self._start_ms)
                # self.mediaPlayer.play()
                self._counter += 1
            
            else:
                self.close()

    def _on_loaded(self, status):
        if status == 2: #QMediaPlayer.LoadedMedia:
            self.mediaPlayer.play()

      

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