from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag, QKeyEvent
from PyQt6.QtWidgets import QListWidget

from ui.widgets.scene_planner.action_segment_widget import ActionSegmentItemWidget

class DropEnabledListWidget(QListWidget):
    item_dropped = pyqtSignal(str)
    item_delete_requested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.setDropIndicatorShown(True); self.setDragEnabled(True)
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
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete and self.currentItem(): self.item_delete_requested.emit()
        else: super().keyPressEvent(event)
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        mime_data = QMimeData()
        widget = self.itemWidget(item)
        if isinstance(widget, ActionSegmentItemWidget):
            mime_data.setText(str(item.data(Qt.ItemDataRole.UserRole)))
        else: mime_data.setText(item.text())
        drag = QDrag(self)
        drag.setMimeData(mime_data); drag.exec(Qt.DropAction.CopyAction)