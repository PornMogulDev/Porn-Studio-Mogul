from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QGroupBox, QPushButton
)
from PyQt6.QtCore import pyqtSignal
from typing import List, Dict, Optional

class SceneRoleSelectorWidget(QWidget):
    """Widget for selecting a scene and role to hire for."""
    scene_changed = pyqtSignal(int)  # scene_id
    role_changed = pyqtSignal(int, int)  # scene_id, vp_id
    refresh_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_scene_id = None
        self.current_vp_id = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Scene Selection
        scene_group = QGroupBox("Select Scene")
        scene_layout = QVBoxLayout(scene_group)
        
        self.scene_combo = QComboBox()
        self.scene_combo.setPlaceholderText("Select a scene in casting...")
        scene_layout.addWidget(self.scene_combo)
        
        layout.addWidget(scene_group)
        
        # Role Selection
        role_group = QGroupBox("Select Role")
        role_layout = QVBoxLayout(role_group)
        
        self.role_combo = QComboBox()
        self.role_combo.setPlaceholderText("Select a role...")
        self.role_combo.setEnabled(False)
        role_layout.addWidget(self.role_combo)
        
        layout.addWidget(role_group)
        
        # Refresh button
        refresh_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Scenes")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        refresh_layout.addStretch()
        refresh_layout.addWidget(self.refresh_button)
        layout.addLayout(refresh_layout)
        
        layout.addStretch()
        
        # Connect signals
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
    
    def populate_scenes(self, scenes: List[Dict]):
        """
        Populate scene dropdown.
        scenes: List of dicts with 'id' and 'title'
        """
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        
        if not scenes:
            self.scene_combo.setPlaceholderText("No scenes available for casting")
            self.scene_combo.blockSignals(False)
            return
        
        for scene in scenes:
            self.scene_combo.addItem(scene['title'], scene['id'])
        
        self.scene_combo.blockSignals(False)
        
        # Auto-select first scene
        if self.scene_combo.count() > 0:
            self.scene_combo.setCurrentIndex(0)
    
    def populate_roles(self, roles: List[Dict]):
        """
        Populate role dropdown.
        roles: List of dicts with 'id' and 'name'
        """
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        
        if not roles:
            self.role_combo.setPlaceholderText("No uncast roles")
            self.role_combo.blockSignals(False)
            return
        
        for role in roles:
            self.role_combo.addItem(role['name'], role['id'])
        
        self.role_combo.setEnabled(True)
        self.role_combo.blockSignals(False)
        
        # Auto-select first role
        if self.role_combo.count() > 0:
            self.role_combo.setCurrentIndex(0)
    
    def _on_scene_changed(self, index):
        """Handle scene selection change."""
        if index >= 0:
            self.current_scene_id = self.scene_combo.currentData()
            if self.current_scene_id:
                self.scene_changed.emit(self.current_scene_id)
    
    def _on_role_changed(self, index):
        """Handle role selection change."""
        if index >= 0 and self.current_scene_id:
            self.current_vp_id = self.role_combo.currentData()
            if self.current_vp_id:
                self.role_changed.emit(self.current_scene_id, self.current_vp_id)
    
    def get_current_selection(self) -> Optional[tuple]:
        """Returns (scene_id, vp_id) or None."""
        if self.current_scene_id and self.current_vp_id:
            return (self.current_scene_id, self.current_vp_id)
        return None
    
    def clear_role_selection(self):
        """Clear the role dropdown."""
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        self.current_vp_id = None