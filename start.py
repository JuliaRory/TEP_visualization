from PyQt5.QtWidgets import QApplication
import os
import sys
import time

from utils.theme_loader import load_qss

from utils.dispatcher import CallDispatcher
from drivers.resonance_foreign_driver import Driver
from ui.main_window import MainWindow


os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r'.\venv\Lib\site-packages\PyQt5\Qt5\plugins'
os.environ['PATH'] += r';~qgis directoryqt\apps\qgis\bin;~qgis directory\apps\Qt5\bin'

# == Создание главный объект приложения Qt == 
app = QApplication(sys.argv)    
style = load_qss(r"styles/theme.qss", r"styles/palette.json")   # подгрузка стиляs

app.setStyleSheet(style)

# == Магическое подключениен драйвера для получения потока с данными из резонанса == 
                                                                                                         
driver = Driver("TEP_visual")          
dispatcher = CallDispatcher()                          # пустая функция-обработчик
driver.inputDataStream("epochs", dispatcher)           # создание входного потока данных типа Stream
driver.loadConfig(r'resonance_settings.json')          # вгрузить настройки с потоком в резонансе
# driver.loadConfig(r'resonance_settings_main.json')          # вгрузить настройки с потоком в резонансе

# == Запуск приложения ==
filename_params = r'data/TEP_visual_settings.json'     # файл с настройками приложения
main = MainWindow(dispatcher, filename_params)         # открыть Qt-окно приложения

sys.exit(app.exec_())
