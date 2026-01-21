from PyQt5.QtWidgets import  QWidget, QVBoxLayout, QSlider, QLabel
from PyQt5.QtCore import Qt, pyqtSignal

class VerticalSliderWithLabel(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        # Вертикальный слайдер
        self.slider = QSlider(Qt.Vertical)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(50)
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TicksRight)

        # Подпись текущего значения
        self.label = QLabel(str(self.slider.value()))
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.slider)
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Сигнал при изменении значения
        self.slider.valueChanged.connect(self.on_value_changed)

    def on_value_changed(self, value):
        # Обновляем подпись только когда пользователь отпустил ползунок
        if not self.slider.isSliderDown():  
            self.label.setText(str(value))
            self.valueChanged.emit(value)
