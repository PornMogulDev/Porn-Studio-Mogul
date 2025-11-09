from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QListWidget

class DraggableListWidget(QListWidget):
    item_dropped = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item:
            mime_data = QMimeData(); mime_data.setText(item.text()); drag = QDrag(self)
            drag.setMimeData(mime_data); drag.exec(Qt.DropAction.CopyAction)
    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        if event.source() is self: event.ignore(); return
        if event.mimeData().hasText(): self.item_dropped.emit(event.mimeData().text()); event.acceptProposedAction()
        else: super().dropEvent(event)