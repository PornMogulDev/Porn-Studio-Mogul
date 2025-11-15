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
        layout = QHBoxLayout(self)
        
        # Scene
        self.scene_combo = QComboBox()
        # The initial placeholder will be overridden in populate_scenes;
        # this default is used only before the first data load.
        self.scene_combo.setPlaceholderText("Select a scene in casting...")
        layout.addWidget(self.scene_combo)
        # Role
        self.role_combo = QComboBox()
        self.role_combo.setPlaceholderText("Select a role...")
        self.role_combo.setEnabled(False)
        layout.addWidget(self.role_combo)
        # Button
        self.refresh_button = QPushButton("Apply Filters for Role")
        # Start disabled; it will be enabled only when both a scene and
        # a role have been explicitly selected.
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self.refresh_button)
        
        # Connect signals
        self.scene_combo.currentIndexChanged.connect(self._on_scene_changed)
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
    
    def populate_scenes(self, scenes: List[Dict]):
        """Populate the scene dropdown without auto-selecting.

        The combobox will remain unselected and show its placeholder text
        until the user explicitly chooses a scene.

        The placeholder is dynamic:
        - If there are no castable scenes, show a descriptive message.
        - If there are scenes, prompt the user to choose one.

        Parameters
        ----------
        scenes: List[Dict]
            List of dicts with ``id`` and ``title`` keys.
        """
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        self.current_scene_id = None

        # Whenever the available scenes change, the role selection must
        # be reset as well so the presenter does not operate on stale IDs.
        self.clear_role_selection()

        if not scenes:
            # No castable scenes: disable the combobox and show a
            # descriptive placeholder.
            self.scene_combo.setEnabled(False)
            self.scene_combo.setPlaceholderText("No scenes available for casting")
            self.scene_combo.setCurrentIndex(-1)
            self.scene_combo.blockSignals(False)
            # With no scenes, the Apply button must remain disabled.
            self._update_apply_button_state()
            return

        # When there are scenes, enable the combobox and prompt the user
        # to choose one.
        self.scene_combo.setEnabled(True)
        self.scene_combo.setPlaceholderText("Choose a scene in casting")

        for scene in scenes:
            self.scene_combo.addItem(scene['title'], scene['id'])

        # Ensure no scene is auto-selected after repopulating; the
        # user must explicitly choose one before any signals fire.
        self.scene_combo.setCurrentIndex(-1)
        self.scene_combo.blockSignals(False)
        self._update_apply_button_state()
    
    def populate_roles(self, roles: List[Dict]):
        """Populate the role dropdown without auto-selecting.

        The combobox will remain unselected and show its placeholder text
        until the user explicitly chooses a role.

        Parameters
        ----------
        roles: List[Dict]
            List of dicts with ``id`` and ``name`` keys.
        """
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        self.current_vp_id = None

        if not roles:
            # In the current game flow, a scene that is still in casting
            # is expected to have uncast roles. If this branch is ever
            # hit, we still present a sensible message and keep the
            # combobox disabled.
            self.role_combo.setPlaceholderText("No uncast roles")
            self.role_combo.blockSignals(False)
            self._update_apply_button_state()
            return

        for role in roles:
            self.role_combo.addItem(role['name'], role['id'])

        # Enable the combobox but leave it unselected so that the
        # presenter only reacts when the user explicitly picks a role.
        self.role_combo.setEnabled(True)
        self.role_combo.setCurrentIndex(-1)
        self.role_combo.blockSignals(False)
        self._update_apply_button_state()
    
    def _on_scene_changed(self, index):
        """Handle scene selection change.

        When the user clears the selection (index == -1), we reset the
        current scene and role state and keep the Apply button disabled.
        """
        if index < 0:
            self.current_scene_id = None
            self.clear_role_selection()
            self._update_apply_button_state()
            return

        self.current_scene_id = self.scene_combo.currentData()
        if self.current_scene_id:
            self.scene_changed.emit(self.current_scene_id)
        self._update_apply_button_state()
    
    def _on_role_changed(self, index):
        """Handle role selection change.

        When the user clears the selection (index == -1), we reset the
        current role and keep the Apply button disabled.
        """
        if index < 0:
            self.current_vp_id = None
            self._update_apply_button_state()
            return

        if self.current_scene_id:
            self.current_vp_id = self.role_combo.currentData()
            if self.current_vp_id:
                self.role_changed.emit(self.current_scene_id, self.current_vp_id)
        self._update_apply_button_state()
    
    def get_current_selection(self) -> Optional[tuple]:
        """Returns (scene_id, vp_id) or None."""
        if self.current_scene_id and self.current_vp_id:
            return (self.current_scene_id, self.current_vp_id)
        return None
    
    def clear_role_selection(self):
        """Clear the role dropdown and reset role-related state."""
        self.role_combo.clear()
        self.role_combo.setEnabled(False)
        self.current_vp_id = None
        self._update_apply_button_state()

    def _update_apply_button_state(self):
        """Enable the Apply button only when both scene and role are set.

        This keeps expensive filtering behind an explicit, valid
        selection and gives clear visual feedback to the player.
        """
        enabled = self.current_scene_id is not None and self.current_vp_id is not None
        self.refresh_button.setEnabled(enabled)