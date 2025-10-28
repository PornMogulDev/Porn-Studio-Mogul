from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QListWidget, QListWidgetItem, QVBoxLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter

class PreferencesWidget(QWidget):
    """A widget for displaying talent preferences, limits, and policy requirements."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _create_refusal_icon(self) -> QIcon:
        """Creates a small red dot icon to indicate a potential refusal."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("red"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 8, 8)
        painter.end()
        return QIcon(pixmap)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        prefs_limits_group = QGroupBox("Preferences and Limits")
        prefs_grid_layout = QGridLayout(prefs_limits_group)
        prefs_grid_layout.addWidget(QLabel("<b>Role Preferences by Orientation:</b>"), 0, 0, 1, 2)
        self.preferences_tree = QTreeWidget()
        self.preferences_tree.setHeaderLabels(["Preference", "Summary / Score"])
        header = self.preferences_tree.header()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.preferences_tree.setColumnWidth(0, 500) 
        self.preferences_tree.setColumnWidth(1, 100)  
        prefs_grid_layout.addWidget(self.preferences_tree, 1, 0, 1, 2)
        prefs_grid_layout.addWidget(QLabel("<b>Hard Limits</b> (Will Refuse Roles):"), 2, 0, 1, 2)
        self.limits_list = QListWidget()
        prefs_grid_layout.addWidget(self.limits_list, 3, 0, 1, 2)
        prefs_grid_layout.setRowStretch(1, 3) 
        prefs_grid_layout.setRowStretch(3, 1)  
        main_layout.addWidget(prefs_limits_group, 3)
        
        policy_group = QGroupBox("Contract Requirements")
        policy_layout = QVBoxLayout(policy_group)
        policy_layout.addWidget(QLabel("<b>Requires Policies:</b>"))
        self.requires_policies_list = QListWidget()
        policy_layout.addWidget(self.requires_policies_list)
        policy_layout.addWidget(QLabel("<b>Refuses Policies:</b>"))
        self.refuses_policies_list = QListWidget()
        policy_layout.addWidget(self.refuses_policies_list)
        main_layout.addWidget(policy_group, 1)

        self.refusal_icon = self._create_refusal_icon()

    def display_preferences(self, preferences_data: list, limits: list, required_policies: list, refused_policies: list):
        self.preferences_tree.clear()
        if preferences_data:
            for orientation_data in preferences_data:
                summary = orientation_data['summary']
                avg_score = orientation_data['average']
                top_item = QTreeWidgetItem(self.preferences_tree, [orientation_data['orientation'], f"{summary} (~{avg_score:.2f})"])
                
                font = top_item.font(0)
                font.setBold(True)
                top_item.setFont(0, font)
                top_item.setFont(1, font)

                if orientation_data['has_refusals']:
                    top_item.setIcon(0, self.refusal_icon)

                for item in orientation_data['items']:
                    child_item = QTreeWidgetItem(top_item, [f"  • {item['name']}", f"{item['score']:.2f}"])
            self.preferences_tree.collapseAll()
            self.preferences_tree.resizeColumnToContents(0)
        else:
             QTreeWidgetItem(self.preferences_tree, ["No notable preferences.", ""])

        self.limits_list.clear()
        if limits:
            for limit in limits:
                item = QListWidgetItem(limit)
                item.setForeground(QColor("red"))
                self.limits_list.addItem(item)
        else:
            self.limits_list.addItem("None")
 
        self.requires_policies_list.clear()
        if required_policies:
            self.requires_policies_list.addItems(required_policies)
        else: self.requires_policies_list.addItem("None")
         
        self.refuses_policies_list.clear()
        if refused_policies:
            self.refuses_policies_list.addItems(refused_policies)
        else: self.refuses_policies_list.addItem("None")