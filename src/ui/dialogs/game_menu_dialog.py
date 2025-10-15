from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QDialogButtonBox, QHBoxLayout, QLabel, QCheckBox
)

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.dialogs.save_load_ui import SaveLoadDialog
from ui.dialogs.settings_dialog import SettingsDialog

class GameMenuDialog(GeometryManagerMixin, QDialog):
    """A dialog that serves as the in-game menu."""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setWindowTitle("Game Menu")
        self.setup_ui()
        self._restore_geometry()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        resume_btn = QPushButton("Resume Game")
        save_btn = QPushButton("Save Game")
        load_btn = QPushButton("Load Game")
        settings_btn = QPushButton("Settings")
        return_to_menu_btn = QPushButton("Return to Main Menu")
        quit_btn = QPushButton("Quit to Desktop")

        layout.addWidget(resume_btn)
        layout.addWidget(save_btn)
        layout.addWidget(load_btn)
        layout.addWidget(settings_btn)
        layout.addWidget(return_to_menu_btn)
        layout.addWidget(quit_btn)

        # Connections
        resume_btn.clicked.connect(self.accept)
        return_to_menu_btn.clicked.connect(self.return_to_menu)
        save_btn.clicked.connect(self.save_game)
        load_btn.clicked.connect(self.load_game)
        settings_btn.clicked.connect(self.show_settings_dialog)
        quit_btn.clicked.connect(self.quit_game)

    def return_to_menu(self):
        dialog = ExitDialog(self.controller, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.return_to_main_menu(exit_save)
        self.accept() # Close menu after action

    def save_game(self):
        dialog = SaveLoadDialog(self.controller, mode='save', parent=self)
        dialog.save_selected.connect(self.controller.save_game)
        dialog.exec()

    def load_game(self):
        dialog = SaveLoadDialog(self.controller, mode='load', parent=self)
        dialog.save_selected.connect(self.controller.load_game)
        dialog.exec()

    def show_settings_dialog(self):
        """Creates and shows the settings dialog."""
        dialog = SettingsDialog(self.controller, self)
        dialog.exec()
    def quit_game(self):
        dialog = ExitDialog(self.controller, text="Create 'Exit Save' before quitting?", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            exit_save = dialog.get_data()
            self.controller.quit_game(exit_save)

class ExitDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, text="Create 'Exit Save'?", parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setup_ui(text)
        self._restore_geometry()
    
    def setup_ui(self, text):
        self.setWindowTitle("Confirm Action")
        layout = QVBoxLayout(self)
        
        cb_container = QWidget(); cb_layout = QHBoxLayout(cb_container)
        cb_text = QLabel(text); self.save_on_exit_cb = QCheckBox()
        
        default_checked = self.controller.settings_manager.get_setting("save_on_exit", True)
        self.save_on_exit_cb.setChecked(default_checked)
        
        cb_layout.addWidget(cb_text); cb_layout.addWidget(self.save_on_exit_cb)
        layout.addWidget(cb_container)
        
        button_box = QDialogButtonBox()
        button_box.addButton("Confirm", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def accept(self):
        new_state = self.save_on_exit_cb.isChecked()
        self.controller.settings_manager.set_setting("save_on_exit", new_state)
        super().accept()
        
    def get_data(self):
        return self.save_on_exit_cb.isChecked()
