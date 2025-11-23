from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QDialogButtonBox, 
    QHBoxLayout, QLabel, QCheckBox, QWidget
)
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class GameMenuDialog(GeometryManagerMixin, QDialog):
    """
    A dumb view that exposes user intent via signals.
    """
    # Signals decouple the View from the Manager/Controller
    save_clicked = pyqtSignal()
    load_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    return_to_menu_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
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

        # Direct connections
        resume_btn.clicked.connect(self.accept) # Resume just closes the dialog
        save_btn.clicked.connect(self.save_clicked.emit)
        load_btn.clicked.connect(self.load_clicked.emit)
        settings_btn.clicked.connect(self.settings_clicked.emit)
        return_to_menu_btn.clicked.connect(self.return_to_menu_clicked.emit)
        quit_btn.clicked.connect(self.quit_clicked.emit)

class ExitDialog(GeometryManagerMixin, QDialog):
    """
    A standard modal dialog. 
    Accepts 'default_checked' bool instead of reading settings itself.
    """
    def __init__(self, text="Create 'Exit Save'?", default_checked=True, parent=None):
        super().__init__(parent)
        self.setup_ui(text, default_checked)
        self._restore_geometry()
    
    def setup_ui(self, text, default_checked):
        self.setWindowTitle("Confirm Action")
        layout = QVBoxLayout(self)
        
        cb_container = QWidget(); cb_layout = QHBoxLayout(cb_container)
        cb_text = QLabel(text)
        self.save_on_exit_cb = QCheckBox()
        self.save_on_exit_cb.setChecked(default_checked)
        
        cb_layout.addWidget(cb_text)
        cb_layout.addWidget(self.save_on_exit_cb)
        layout.addWidget(cb_container)
        
        button_box = QDialogButtonBox()
        button_box.addButton("Confirm", QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def get_data(self):
        return self.save_on_exit_cb.isChecked()