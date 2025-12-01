from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtGui import QMouseEvent

class SmartHoverMixin:
    """
    Mixin for QTableView/QTableWidget to handle smart hover and alt-click interactions.
    
    Requirements for the consuming class:
    1. Must inherit from QTableView or QTableWidget.
    2. Must define the following pyqtSignals:
       - smart_hover_entered(object, QPoint)
       - smart_hover_left()
       - smart_alt_clicked(object)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
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
            # QTableView uses index.data(), QTableWidget items set data via UserRole which index.data() accesses.
            entity = index.data(Qt.ItemDataRole.UserRole)
            
            if entity:
                global_pos = self.mapToGlobal(event.pos())
                self.smart_hover_entered.emit(entity, global_pos)
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
        # Handle Alt + Left Click
        if event.button() == Qt.MouseButton.LeftButton and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            index = self.indexAt(event.pos())
            if index.isValid():
                # Case 1: Smart Column (Row Action - Standard Smart Table Logic)
                if index.column() in self._smart_columns:
                    entity = index.data(Qt.ItemDataRole.UserRole)
                    if entity:
                        self.smart_alt_clicked.emit(entity)
                        return # Consume the event so we don't select the row/cell
                
                # Case 2: Other Columns (Delegate Action - e.g. Cast Column links)
                # We must manually forward the event to the delegate because setEditTriggers(NoEditTriggers)
                # often prevents the View from calling editorEvent() on mouse press.
                else:
                    delegate = self.itemDelegateForColumn(index.column())
                    if delegate:
                        # Manually construct the option since viewOptions() is protected/unavailable to mixins easily
                        option = QStyleOptionViewItem()
                        option.initFrom(self)
                        option.rect = self.visualRect(index)
                        option.index = index
                        
                        # Manually invoke editorEvent. If it returns True, it handled the click.
                        if delegate.editorEvent(event, self.model(), option, index):
                            return

        super().mousePressEvent(event)