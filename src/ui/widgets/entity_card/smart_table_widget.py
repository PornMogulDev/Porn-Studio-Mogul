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
        self._smart_columns = {0}

    def set_smart_columns(self, columns: list[int]):
        """Configures which columns trigger the smart hover card."""
        self._smart_columns = set(columns)

    def add_smart_column(self, column: int):
        self._smart_columns.add(column)

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)
        
        index = self.indexAt(event.pos())
        
        if index.isValid() and index.row() == self._last_hovered_index.row() and index.column() == self._last_hovered_index.column():
            return

        # Behavior: Only show summary for configured smart columns
        if index.isValid() and index.column() in self._smart_columns:
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
                if index.column() in self._smart_columns:
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