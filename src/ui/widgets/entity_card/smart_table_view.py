from PyQt6.QtWidgets import QTableView, QStyleOptionViewItem, QStyle
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QPoint
from PyQt6.QtGui import QMouseEvent

class SmartTableView(QTableView):
    """
    A QTableView that supports 'Smart Hover' and 'Alt+Click' interactions.
    It assumes the underlying model's UserRole data contains the entity object.
    """
    # Emits the object found in UserRole and the global mouse position
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    # Emits the object found in UserRole
    smart_alt_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True) # Essential for hover events
        self._last_hovered_index = QModelIndex()
        self._smart_columns = {0} # Default to column 0

    def set_smart_columns(self, columns: list[int]):
        """Configures which columns trigger the smart hover card."""
        self._smart_columns = set(columns)

    def add_smart_column(self, column: int):
        self._smart_columns.add(column)

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)
        
        index = self.indexAt(event.pos())
        
        # Optimization: Don't re-emit if we are still on the same row/column
        if index.isValid() and index.row() == self._last_hovered_index.row() and index.column() == self._last_hovered_index.column():
            return

        # Behavior: Only show summary for configured smart columns
        if index.isValid() and index.column() in self._smart_columns:
            self._last_hovered_index = index
            # Get the entity from the model (UserRole)
            entity = index.data(Qt.ItemDataRole.UserRole)
            if entity:
                global_pos = self.mapToGlobal(event.pos())
                self.smart_hover_entered.emit(entity, global_pos)
            else:
                self.smart_hover_left.emit()
        else:
            # If we move off column 0, clear the card
            self._last_hovered_index = QModelIndex()
            self.smart_hover_left.emit()

    def leaveEvent(self, event):
        self._last_hovered_index = QModelIndex()
        self.smart_hover_left.emit()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        # Handle Alt + Left Click
        if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            index = self.indexAt(event.pos())
            if index.isValid():
                # Case 1: Smart Column (Row Action - Standard Smart Table Logic)
                if index.column() in self._smart_columns:
                    entity = index.data(Qt.ItemDataRole.UserRole)
                    if entity:
                        self.smart_alt_clicked.emit(entity)
                        return # Consume the event so we don't select the row
                
                # Case 2: Other Columns (Delegate Action - e.g. Cast Column)
                # We must manually forward the event to the delegate because setEditTriggers(NoEditTriggers)
                # prevents the View from calling editorEvent() on mouse press.
                else:
                    delegate = self.itemDelegateForColumn(index.column())
                    if delegate:
                        # Manually construct the option since viewOptions() is protected/unavailable
                        option = QStyleOptionViewItem()
                        option.initFrom(self)
                        option.rect = self.visualRect(index)
                        option.index = index
                        
                        # Manually invoke editorEvent. If it returns True, it handled the click.
                        if delegate.editorEvent(event, self.model(), option, index):
                            return

        super().mousePressEvent(event)