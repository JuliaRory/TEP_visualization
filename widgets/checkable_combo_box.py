from PyQt5.QtWidgets import QComboBox, QListView
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem

class CheckableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView()
        view.setSelectionMode(QListView.ExtendedSelection)  # <--- вот это важно
        self.setView(view)
        self.setModel(QStandardItemModel(self))

    def addItem(self, text, checked=True):
        item = QStandardItem(text)
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        state = Qt.Checked if checked else Qt.Unchecked
        item.setData(state, Qt.CheckStateRole)
        self.model().appendRow(item)

    def checkedItems(self):
        """Вернуть список отмеченных элементов"""
        checked_list = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                checked_list.append(item.text())
        return checked_list
    
    def keyPressEvent(self, event):
        # если нажали пробел, переключаем выделенные элементы
        if event.key() == Qt.Key_Space:
            indexes = self.view().selectionModel().selectedIndexes()
            if indexes:
                for index in indexes:
                    item = self.model().itemFromIndex(index)
                    item.setCheckState(
                        Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                    )
        else:
            super().keyPressEvent(event)