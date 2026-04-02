import pygame
import threading
import time
from PyQt5 import QtCore

class AudioPlayer(QtCore.QObject):
    """
    Класс для циклического воспроизведения аудиофайла с управлением громкостью,
    паузой и запуском. Работает в отдельном потоке.
    """
    
    # Сигналы для обновления UI (опционально)
    playback_started = QtCore.pyqtSignal()
    playback_paused = QtCore.pyqtSignal()
    playback_stopped = QtCore.pyqtSignal()
    volume_changed = QtCore.pyqtSignal(int)
    
    def __init__(self, audio_file_path, initial_volume=50):
        super().__init__()
        self.audio_file_path = audio_file_path
        self.initial_volume = initial_volume
        
        # Состояние воспроизведения
        self.is_playing = False
        self.is_paused = False
        self.stop_requested = False
        
        # Громкость
        self.volume = initial_volume
        self.muted_volume = initial_volume  # Сохраняем громкость перед mute
        
        # Поток воспроизведения
        self.playback_thread = None
        
        # Инициализация pygame mixer
        self._init_pygame()
        
    def _init_pygame(self):
        """Инициализация pygame mixer"""
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            # Устанавливаем начальную громкость
            pygame.mixer.music.set_volume(self.volume / 100.0)
            pygame.mixer.music.load(self.audio_file_path)
            print("Поставлен аудиофайл: ", self.audio_file_path)
            print(f"Pygame mixer инициализирован, громкость: {self.volume}%")
        except Exception as e:
            print(f"Ошибка инициализации pygame mixer: {e}")
            raise
    
    def start_playback(self):
        """Запуск циклического воспроизведения"""
        if self.is_playing:
            print("Воспроизведение уже запущено")
            return
            
        self.is_playing = True
        self.is_paused = False
        self.stop_requested = False
        
        # Создаем и запускаем поток воспроизведения
        self.playback_thread = threading.Thread(
            target=self._playback_loop,
            daemon=True,
            name="AudioPlaybackThread"
        )
        self.playback_thread.start()
        
        print("Воспроизведение звука запущено")
        self.playback_started.emit()
    
    def set_audiofile(self, filename):
        
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
        try:
            pygame.mixer.music.load(filename)   # Загружаем аудиофайл
            print("Поставлен аудиофайл: ", filename)
        except:
            print("Не получилось загрузить аудифайл: ", filename)
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.play()

    def _playback_loop(self):
        """Основной цикл воспроизведения в отдельном потоке"""
        try:
            
            # Основной цикл воспроизведения
            while not self.stop_requested:
                if self.is_paused:
                    # Если на паузе, ждем
                    time.sleep(0.1)
                    continue
                
                # Воспроизводим файл
                pygame.mixer.music.play()
                
                # Ждем окончания воспроизведения текущего трека
                while (pygame.mixer.music.get_busy() and 
                       not self.stop_requested and 
                       not self.is_paused):
                    time.sleep(0.05)  # Небольшая пауза для снижения нагрузки на CPU
                
                # Если не остановлено и не на паузе - повторяем
                if not self.stop_requested and not self.is_paused:
                    print("Повтор звуковой дорожки...")
                    continue
                    
        except Exception as e:
            print(f"Ошибка в цикле воспроизведения: {e}")
        finally:
            self.is_playing = False
            self.is_paused = False
            print("Цикл воспроизведения завершен")
    
    def pause(self):
        """Постановка на паузу"""
        if not self.is_playing:
            print("Воспроизведение не запущено, пауза невозможна")
            return
            
        if not self.is_paused:
            self.is_paused = True
            pygame.mixer.music.pause()
            print("Воспроизведение на паузе")
            self.playback_paused.emit()
    
    def resume(self):
        """Продолжение воспроизведения после паузы"""
        if not self.is_playing:
            print("Воспроизведение не запущено, продолжить невозможно")
            return
            
        if self.is_paused:
            self.is_paused = False
            pygame.mixer.music.unpause()
            print("Воспроизведение продолжено")
            self.playback_started.emit()
    
    def stop(self):
        """Полная остановка воспроизведения"""
        self.stop_requested = True
        self.is_playing = False
        self.is_paused = False
        
        # Останавливаем воспроизведение pygame
        pygame.mixer.music.stop()
        
        # Ждем завершения потока
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
            print("Поток воспроизведения завершен")
        
        print("Воспроизведение остановлено")
        self.playback_stopped.emit()
    
    @property
    def is_active(self):
        """Проверка, активно ли воспроизведение"""
        return self.is_playing and not self.is_paused

    # === VOLUME ===
    def set_volume(self, volume):
        """Установка громкости (0-100)"""
        if 0 <= volume <= 100:
            self.volume = volume
            
            # Если не в режиме mute, применяем громкость
            if not hasattr(self, '_is_muted') or not self._is_muted:
                pygame.mixer.music.set_volume(volume / 100.0)
            
            print(f"Громкость установлена: {volume}%")
            self.volume_changed.emit(volume)
        else:
            print(f"Некорректное значение громкости: {volume}. Допустимый диапазон: 0-100")
    
    def get_volume(self):
        """Получение текущей громкости"""
        return self.volume
    
    def mute(self):
        """Отключение звука"""
        if not hasattr(self, '_is_muted'):
            self._is_muted = False
            
        if not self._is_muted:
            self.muted_volume = self.volume  # Сохраняем текущую громкость
            pygame.mixer.music.set_volume(0)
            self._is_muted = True
            print("Звук отключен")
    
    def unmute(self):
        """Включение звука"""
        if hasattr(self, '_is_muted') and self._is_muted:
            pygame.mixer.music.set_volume(self.muted_volume / 100.0)
            self._is_muted = False
            print(f"Звук включен, громкость: {self.muted_volume}%")
    
    def toggle_mute(self):
        """Переключение режима mute/unmute"""
        if not hasattr(self, '_is_muted') or not self._is_muted:
            self.mute()
        else:
            self.unmute()
    
    
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.stop()
        pygame.mixer.quit()
        print("Ресурсы аудиоплеера очищены")
