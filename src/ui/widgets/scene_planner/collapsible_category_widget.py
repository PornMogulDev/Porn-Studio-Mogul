from typing import List, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView

class CollapsibleCategoryWidget(QTreeWidget):
    """
    A TreeWidget that groups items by a 'concept' key.
    Replaces DraggableListWidget for structured tag display (e.g. Physical Tags).
    """
    item_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setIndentation(20)
        self.setRootIsDecorated(True)

        # Cache leaf items to allow filtering without rebuilding
        # Key: tag full_name, Value: QTreeWidgetItem
        self._leaf_items: Dict[str, QTreeWidgetItem] = {}

    def set_tags(self, tags: List[Dict[str, Any]]):
        """
        Updates the tree. If the tree is empty, it builds it.
        If the tree exists, it filters items based on the input list,
        preserving expansion state and scroll position.
        """
        # Optimization: If we already have items and this is a filter (subset),
        # just hide/show instead of rebuilding.
        if self.topLevelItemCount() > 0:
            visible_names = {t.get('full_name', t.get('name')) for t in tags}
            if all(name in self._leaf_items for name in visible_names):
                self._filter_items(visible_names)
                return

        # Full Build / Rebuild
        self.clear()
        self._leaf_items.clear()
        
        # Group tags by concept + orientation
        groups = {}
        # Special group for tags without a concept
        groups["Uncategorized"] = []
        
        for tag in tags:
            concept = tag.get('concept', "Uncategorized")
            orientation = tag.get('orientation')
            
            # Dynamic Header: "Concept (Orientation)" or just "Concept"
            if concept != "Uncategorized" and orientation:
                group_name = f"{concept} ({orientation})"
            else:
                group_name = concept

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(tag)
            
        # Sort headers: Alphabetical, but Uncategorized always last
        sorted_group_names = sorted([k for k in groups.keys() if k != "Uncategorized"])
        if groups["Uncategorized"]:
            sorted_group_names.append("Uncategorized")
            
        for group_name in sorted_group_names:
            tag_list = groups[group_name]
            if not tag_list:
                continue
                
            # Create Category Root (Header)
            root_item = QTreeWidgetItem(self)
            root_item.setText(0, group_name)
            
            # Style root item
            font = root_item.font(0)
            font.setBold(True)
            root_item.setFont(0, font)
            # Headers are enabled (for expansion) but not selectable for dragging
            root_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            
            # Sort tags within the group alphabetically
            sorted_tags = sorted(tag_list, key=lambda t: t.get('full_name', t.get('name', '')))
            
            for tag in sorted_tags:
                child_item = QTreeWidgetItem(root_item)
                display_text = tag.get('full_name', tag.get('name', 'Unknown'))
                child_item.setText(0, display_text)
                
                # Store full tag data for retrieval in presenter
                child_item.setData(0, Qt.ItemDataRole.UserRole, tag)

                # Cache for filtering and lookups
                self._leaf_items[display_text] = child_item
                
                if tooltip := tag.get("tooltip"):
                    child_item.setToolTip(0, tooltip)
            
            # Expand headers by default
            root_item.setExpanded(True)

    def _filter_items(self, visible_names: set):
        """Hides items not in visible_names, handles parent visibility."""
        self.setUpdatesEnabled(False)
        
        for i in range(self.topLevelItemCount()):
            root = self.topLevelItem(i)
            visible_children = 0
            for j in range(root.childCount()):
                child = root.child(j)
                should_hide = child.text(0) not in visible_names
                child.setHidden(should_hide)
                if not should_hide:
                    visible_children += 1
            
            # Hide category if all children are hidden
            root.setHidden(visible_children == 0)
            
        self.setUpdatesEnabled(True)

    def get_selected_tag_names(self) -> List[str]:
        """Returns the text of selected leaf nodes."""
        selected_names = []
        for item in self.selectedItems():
            # Only include leaf nodes (nodes with parent)
            if item.parent() is not None:
                selected_names.append(item.text(0))
        return selected_names

    # --- Drag and Drop Implementation ---

    def startDrag(self, supportedActions):
        selected_names = self.get_selected_tag_names()
        if not selected_names:
            return
            
        # Send all selected names joined by newlines to support multi-select drag
        text_to_drag = "\n".join(selected_names)
            
        if text_to_drag:
            mime_data = QMimeData()
            mime_data.setText(text_to_drag)
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.source() is self:
            event.ignore()
            return
            
        if event.mimeData().hasText():
            text = event.mimeData().text()
            self.item_dropped.emit(text)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)