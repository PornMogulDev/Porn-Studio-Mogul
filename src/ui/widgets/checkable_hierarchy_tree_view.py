from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtGui import QStandardItemModel, QStandardItem

class CheckableHierarchyTreeView(QTreeView):
    """
    A self-contained, two-level hierarchical tree view with checkable items.
    It encapsulates all logic for synchronizing parent/child check states.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.setModel(self.model)

        # Configure the view's appearance and behavior
        self.setHeaderHidden(True)
        self.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

        # The widget manages its own state changes internally.
        self.model.itemChanged.connect(self._on_item_changed)

    def populate_data(self, data: dict):
        """
        Clears the current model and populates it with new hierarchical data.
        :param data: A dictionary where keys are parent names and values are lists of child names.
        """
        self.model.clear()
        for parent_name, children in data.items():
            parent_item = QStandardItem(parent_name)
            parent_item.setCheckable(True)
            parent_item.setAutoTristate(True) # Allows for the "partially checked" state
            
            for child_name in children:
                child_item = QStandardItem(child_name)
                child_item.setCheckable(True)
                parent_item.appendRow(child_item)
            
            self.model.appendRow(parent_item)

    def set_checked_items(self, selected_items: list):
        """
        Sets the check state of items in the tree based on a flat list of child names.
        This is a bulk operation, so blocking signals is the most efficient approach.
        """
        self.model.blockSignals(True)
        try:
            is_empty_selection = not selected_items
            for row in range(self.model.rowCount()):
                parent_item = self.model.item(row)
                if not parent_item: continue
                
                # Handle end-nodes (parents without children)
                if parent_item.rowCount() == 0:
                    is_checked = False if is_empty_selection else parent_item.text() in selected_items
                    parent_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                    continue

                # Handle parents with children
                all_children_checked = True
                any_child_checked = False
                for child_row in range(parent_item.rowCount()):
                    child_item = parent_item.child(child_row)
                    if not child_item: continue
                    is_checked = False if is_empty_selection else child_item.text() in selected_items
                    child_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                    if not is_checked: all_children_checked = False
                    if is_checked: any_child_checked = True

                # After setting all children, determine the parent's state
                if all_children_checked:
                    parent_item.setCheckState(Qt.CheckState.Checked)
                elif any_child_checked:
                    parent_item.setCheckState(Qt.CheckState.PartiallyChecked)
                else:
                    parent_item.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self.model.blockSignals(False)
            self._force_update_and_resize()

    def get_checked_items(self) -> list:
        """
        Gathers the text of all checked "end-node" items (children, or parents
        without children) from the tree.
        :return: A flat list of strings of the checked items.
        """
        checked_items = []
        for row in range(self.model.rowCount()):
            parent = self.model.item(row)
            if parent.rowCount() == 0:  # This is an end-node parent
                if parent.checkState() == Qt.CheckState.Checked:
                    checked_items.append(parent.text())
            else:  # This parent has children, so we check them
                for child_row in range(parent.rowCount()):
                    child = parent.child(child_row)
                    if child and child.checkState() == Qt.CheckState.Checked:
                        checked_items.append(child.text())
        return checked_items

    def _on_item_changed(self, item: QStandardItem):
        """
        Internal slot to handle user clicks and synchronize check states.
        Uses blockSignals to prevent recursive calls efficiently.
        """
        self.model.blockSignals(True)
        try:
            # Logic for a parent item being checked/unchecked by the user
            if not item.parent():
                state = item.checkState()
                for i in range(item.rowCount()):
                    child = item.child(i)
                    if child:
                         child.setCheckState(state)
            # Logic for a child item being checked/unchecked by the user
            else:
                parent = item.parent()
                if not parent: return
                
                checked_count = 0
                total_children = parent.rowCount()
                for i in range(total_children):
                    if parent.child(i).checkState() == Qt.CheckState.Checked:
                        checked_count += 1
                
                # Determine and set the parent's new state based on its children
                if checked_count == total_children:
                    parent.setCheckState(Qt.CheckState.Checked)
                elif checked_count > 0:
                    parent.setCheckState(Qt.CheckState.PartiallyChecked)
                else:
                    parent.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self.model.blockSignals(False)
            self._force_update_and_resize()

    def _force_update_and_resize(self):
        """Forces a full repaint and resizes the column to prevent text eliding."""
        # Tells the view to redraw its visible area immediately.
        self.viewport().update()
        # Recalculates the optimal width for the content in column 0.
        self.resizeColumnToContents(0)