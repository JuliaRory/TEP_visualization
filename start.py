from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import os
import sys
import time

from utils.theme_loader import load_qss
from utils.resonance_control import ResonanceAppProxy

from utils.dispatcher import CallDispatcher
from drivers.resonance_foreign_driver import Driver
from ui.main_window import MainWindow


os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'.\venv\Lib\site-packages\PyQt5\Qt5\plugins'
os.environ['PATH'] += r';~qgis directoryqt\apps\qgis\bin;~qgis directory\apps\Qt5\bin'

# == Создание главный объект приложения Qt == 
app = QApplication(sys.argv)    

style = load_qss(r"styles/theme.qss", r"styles/palette.json")   # подгрузка стиля

app.setStyleSheet(style)

# == Магическое подключениен драйвера для получения потока с данными из резонанса == 
                                                                                                         
driver = Driver("TEP_visual")

dispatcher = CallDispatcher()                                            # пустая функция-обработчик
driver.inputDataStream("epochs", dispatcher)                             # создание входного потока данных типа Stream
# driver.inputMessageStream("epochs", dispatcher)                             # создание входного потока данных типа Stream
tension_on_dispatcher = CallDispatcher()
driver.inputMessageStream("tension_on", tension_on_dispatcher)
epoch_labels_dispatcher = CallDispatcher()
driver.inputMessageStream("epoch_labels", epoch_labels_dispatcher)

output_stream = driver.outputMessageStream("controlSignal")           # создание выходного потока данных типа Message
output_stream_stimuli = driver.outputMessageStream("stimuli")           # создание выходного потока данных типа Message
output_stream_feet_stim = driver.outputMessageStream("feetStim")
output_stream_tension_wait = driver.outputMessageStream("tension_wait")
resonance = ResonanceAppProxy(output_stream)                             # Создаем прокси резонанса

driver_poll_timer = QTimer()
driver_poll_timer.timeout.connect(driver.pollEvents)
driver_poll_timer.start(10)

# driver.loadConfig(r'resonance_settings.json')          # вгрузить настройки с потоком в резонансе
# driver.loadConfig(r'resonance_settings_main.json')       # вгрузить настройки с потоком в резонансе
# driver.loadConfig(r'stream_Generator@message__to__TEP_visual@epochs.json')   # вгрузить настройки с потоком в резонансе

# == Запуск приложения ==
filename_params = r'data/TEP_visual_settings.json'     # файл с настройками приложения
main = MainWindow(
    dispatcher,
    resonance,
    output_stream_stimuli,
    filename_params,
    feet_stim_stream=output_stream_feet_stim,
    epoch_labels_stream=epoch_labels_dispatcher,
    tension_wait_stream=output_stream_tension_wait,
    tension_on_stream=tension_on_dispatcher,
)         # открыть Qt-окно приложения

sys.exit(app.exec_())


