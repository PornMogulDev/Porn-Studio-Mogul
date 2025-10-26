from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QListWidget, QListWidgetItem, QVBoxLayout
)
from PyQt6.QtGui import QColor

class PreferencesWidget(QWidget):
    """A widget for displaying talent preferences, limits, and policy requirements."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        prefs_limits_group = QGroupBox("Preferences & Limits")
        prefs_grid_layout = QGridLayout(prefs_limits_group)
        prefs_grid_layout.addWidget(QLabel("<b>Likes</b> (Reduces Hire Cost):"), 0, 0)
        prefs_grid_layout.addWidget(QLabel("<b>Dislikes</b> (Increases Hire Cost):"), 0, 1)
        self.likes_list = QListWidget(); self.dislikes_list = QListWidget()
        prefs_grid_layout.addWidget(self.likes_list, 1, 0); prefs_grid_layout.addWidget(self.dislikes_list, 1, 1)
        prefs_grid_layout.addWidget(QLabel("<b>Hard Limits</b> (Will Refuse Roles):"), 2, 0, 1, 2)
        self.limits_list = QListWidget()
        prefs_grid_layout.addWidget(self.limits_list, 3, 0, 1, 2)
        main_layout.addWidget(prefs_limits_group)
        
        policy_group = QGroupBox("Contract Requirements")
        policy_layout = QVBoxLayout(policy_group)
        policy_layout.addWidget(QLabel("<b>Requires Policies:</b>"))
        self.requires_policies_list = QListWidget()
        policy_layout.addWidget(self.requires_policies_list)
        policy_layout.addWidget(QLabel("<b>Refuses Policies:</b>"))
        self.refuses_policies_list = QListWidget()
        policy_layout.addWidget(self.refuses_policies_list)
        main_layout.addWidget(policy_group)

    def display_preferences(self, likes: list, dislikes: list, limits: list, required_policies: list, refused_policies: list):
        self.likes_list.clear()
        if likes: self.likes_list.addItems(likes)
        else: self.likes_list.addItem("None")
                
        self.dislikes_list.clear()
        if dislikes: self.dislikes_list.addItems(dislikes)
        else: self.dislikes_list.addItem("None")

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