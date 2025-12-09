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
        # If we already have items and this seems like a filter operation (subset of data),
        # try to just hide/show items instead of rebuilding.
        if self.topLevelItemCount() > 0:
            visible_names = {t.get('full_name', t.get('name')) for t in tags}
            
            # Heuristic: If we have cached items matching the input, update visibility
            # If we received new tags that we don't know about, fall through to rebuild.
            if all(name in self._leaf_items for name in visible_names):
                self._filter_items(visible_names)
                return

        # Full Build / Rebuild
        self.clear()
        
        # Group tags by concept
        groups = {}
        # Special group for tags without a concept
        groups["Uncategorized"] = []
        
        for tag in tags:
            concept = tag.get('concept', "Uncategorized")
            if concept not in groups:
                groups[concept] = []
            groups[concept].append(tag)
            
        # Sort concepts: Standard alphabetical, but Uncategorized last
        sorted_concepts = sorted([k for k in groups.keys() if k != "Uncategorized"])
        if groups["Uncategorized"]:
            sorted_concepts.append("Uncategorized")
            
        for concept in sorted_concepts:
            tag_list = groups[concept]
            if not tag_list:
                continue
                
            # Create Category Root
            root_item = QTreeWidgetItem(self)
            root_item.setText(0, concept)
            # Style root item
            font = root_item.font(0)
            font.setBold(True)
            root_item.setFont(0, font)
            # Root items are enabled (for expansion) but not selectable for dragging
            root_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            
            for tag in tag_list:
                # Ensure we use the full name as the unique key
                child_item = QTreeWidgetItem(root_item)
                # Use full_name for display (contains stars, gender info from presenter)
                display_text = tag.get('full_name', tag.get('name', 'Unknown'))
                child_item.setText(0, display_text)
                # Store full tag data for retrieval
                child_item.setData(0, Qt.ItemDataRole.UserRole, tag)

                # Cache for filtering
                self._leaf_items[display_text] = child_item
                
                if tooltip := tag.get("tooltip"):
                    child_item.setToolTip(0, tooltip)
            
            # Expand all by default to show tags
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