from PyQt6.QtWidgets import QTableWidget, QStyleOptionViewItem
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QPoint
from PyQt6.QtGui import QMouseEvent

class SmartTableWidget(QTableWidget):
    """
    A QTableWidget that supports 'Smart Hover' and 'Alt+Click' interactions.
    It assumes the item's UserRole data contains the entity ID or Object.
    """
    # Emits the data found in UserRole and the global mouse position
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    # Emits the data found in UserRole
    smart_alt_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True) 
        self._last_hovered_index = QModelIndex()

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)
        
        index = self.indexAt(event.pos())
        
        if index.isValid() and index.row() == self._last_hovered_index.row() and index.column() == self._last_hovered_index.column():
            return

        # STRICT BEHAVIOR: Only show summary for Column 0 (Alias)
        if index.isValid() and index.column() == 0:
            self._last_hovered_index = index
            # QTableWidget uses item(row, col).data(...) internally via the model interface
            entity_data = index.data(Qt.ItemDataRole.UserRole)
            
            if entity_data:
                global_pos = self.mapToGlobal(event.pos())
                self.smart_hover_entered.emit(entity_data, global_pos)
            else:
                self.smart_hover_left.emit()
        else:
            self._last_hovered_index = QModelIndex()
            self.smart_hover_left.emit()

    def leaveEvent(self, event):
        self._last_hovered_index = QModelIndex()
        self.smart_hover_left.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            index = self.indexAt(event.pos())
            if index.isValid():
                if index.column() == 0:
                    entity_data = index.data(Qt.ItemDataRole.UserRole)
                    if entity_data:
                        self.smart_alt_clicked.emit(entity_data)
                        return 
                
                # Forward to delegate if needed (copied from SmartTableView for consistency)
                else:
                    delegate = self.itemDelegateForColumn(index.column())
                    if delegate:
                        option = QStyleOptionViewItem()
                        option.initFrom(self)
                        option.rect = self.visualRect(index)
                        option.index = index
                        if delegate.editorEvent(event, self.model(), option, index):
                            return

        super().mousePressEvent(event)