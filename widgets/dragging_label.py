import sys
from PyQt5.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QLabel, QFrame
        )
from PyQt5.QtCore import Qt, QPoint

class DraggableLabel(QLabel):
    def mouseDoubleClickEvent(self, event):
        # блокируем двойной клик, чтобы исключить 'пропадание' элемента
        event.ignore()
    fixed_y = 50 # фиксированная горизонтальная линия
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("background-color: lightgray; border: 1px solid black; padding: 5px;")
        self.setFrameShape(QFrame.Panel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(2)
        self.dragging = False
        self.offset = QPoint(0, 0)


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.dragging:
            # вычисляем новое положение по X и ограничиваем его границами рабочей области
            new_pos = self.mapToParent(event.pos() - self.offset)
            new_x = new_pos.x()
            parent = self.parent()
            if parent is not None:
                max_x = max(0, parent.width() - self.width())
                new_x = max(0, min(new_x, max_x))
            self.move(new_x, self.fixed_y)


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

# -----------------------
# Group of labels (draggable together)
# -----------------------
class LabelGroup(QFrame):
    fixed_y = 150


    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Box)
        self.setStyleSheet("background-color: #e0e0ff; border: 2px solid blue;")
        self.dragging = False
        self.offset = QPoint(0, 0)


        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        for lbl in labels:
            lbl.setParent(self)
            layout.addWidget(lbl)

        self.adjustSize()


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()


    def mouseMoveEvent(self, event):
        if self.dragging:
            new_x = self.mapToParent(event.pos() - self.offset).x()
            parent = self.parent()
        if parent is not None:
            max_x = max(0, parent.width() - self.width())
            new_x = max(0, min(new_x, max_x))
        self.move(new_x, self.fixed_y)


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False