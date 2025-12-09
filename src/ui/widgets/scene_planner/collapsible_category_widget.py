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

    def set_tags(self, tags: List[Dict[str, Any]]):
        """
        Populates the tree grouping tags by their 'concept'.
        """
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
                child_item = QTreeWidgetItem(root_item)
                # Use full_name for display (contains stars, gender info from presenter)
                display_text = tag.get('full_name', tag.get('name', 'Unknown'))
                child_item.setText(0, display_text)
                # Store full tag data for retrieval
                child_item.setData(0, Qt.ItemDataRole.UserRole, tag)
                
                if tooltip := tag.get("tooltip"):
                    child_item.setToolTip(0, tooltip)
            
            # Expand all by default to show tags
            root_item.setExpanded(True)

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
            
        # Emulate the behavior of DraggableListWidget which sends text.
        # We send the first selected name.
        text_to_drag = selected_names[0]
            
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