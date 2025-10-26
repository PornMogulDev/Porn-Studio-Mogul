from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QTreeView
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex

from data.game_state import Scene

class HistoryWidget(QWidget):
    """A widget for displaying a talent's scene history."""
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        history_group = QGroupBox("Scene History")
        history_layout = QVBoxLayout(history_group)
        self.scene_history_tree = QTreeView()
        self.scene_history_model = QStandardItemModel()
        self.scene_history_tree.setModel(self.scene_history_model)
        self.scene_history_tree.setHeaderHidden(True)
        self.scene_history_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        history_layout.addWidget(self.scene_history_tree)
        main_layout.addWidget(history_group)

    def _connect_signals(self):
        self.scene_history_tree.doubleClicked.connect(self._on_scene_double_clicked)

    def _on_scene_double_clicked(self, index: QModelIndex):
        item = self.scene_history_model.itemFromIndex(index)
        # We only care about top-level items which represent scenes
        if item and item.parent() is None:
            if scene_id := item.data(Qt.ItemDataRole.UserRole):
                self.open_scene_dialog_requested.emit(scene_id)
            
    def display_scene_history(self, scene_history: list[Scene], current_talent_id: int):
        self.scene_history_model.clear()
        root_node = self.scene_history_model.invisibleRootItem()
    
        if not scene_history:
            root_node.appendRow(QStandardItem("No scenes on record."))
            return

        for scene in scene_history:
            scene_item = QStandardItem(f"{scene.title} ({scene.display_status})")
            font = scene_item.font()
            font.setBold(True)
            scene_item.setFont(font)
            scene_item.setEditable(False)
            scene_item.setData(scene.id, Qt.ItemDataRole.UserRole) # Store scene ID

            contributions = [c for c in scene.performer_contributions if c.talent_id == current_talent_id]
            if contributions:
                sorted_contributions = sorted(contributions, key=lambda c: c.contribution_key)
                for contrib in sorted_contributions:
                    contrib_item = QStandardItem(f"  • {contrib.contribution_key}: {contrib.quality_score:.2f} quality")
                    contrib_item.setEditable(False)
                    scene_item.appendRow(contrib_item)
            else:
                contrib_item = QStandardItem("  • Role data not available.")
                contrib_item.setEditable(False)
                scene_item.appendRow(contrib_item)

            root_node.appendRow(scene_item)
            
        self.scene_history_tree.expandAll()