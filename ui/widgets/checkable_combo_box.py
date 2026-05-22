from PyQt5.QtWidgets import QComboBox, QListView
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QStandardItemModel, QStandardItem

class CheckableComboBox(QComboBox):
    textChanged  = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView()
        view.setSelectionMode(QListView.ExtendedSelection)  
        self.setView(view)
        self.setModel(QStandardItemModel(self))

        self._setup_connections()

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

    def setCheckedItems(self, checked_items):
        checked_items = set(checked_items)
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            state = Qt.Checked if item.text() in checked_items else Qt.Unchecked
            item.setCheckState(state)


    def _setup_connections(self):
        self.model().dataChanged.connect(self._on_current_text_changed)
    
    def _on_current_text_changed(self):
        curr_items = self.checkedItems()
        self.textChanged.emit(curr_items)
    
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
