from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, 
    QComboBox, QDialogButtonBox, QPushButton, QMessageBox
)
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class SettingsDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setup_ui()
        self.load_current_settings()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Display Group
        display_group = QGroupBox("Display")
        display_layout = QHBoxLayout(display_group)
        
        unit_label = QLabel("Unit System:")
        self.unit_combo = QComboBox()
        self.unit_combo.addItem("Imperial (inches)", "imperial")
        self.unit_combo.addItem("Metric (cm)", "metric")
        
        display_layout.addWidget(unit_label)
        display_layout.addWidget(self.unit_combo)
        
        main_layout.addWidget(display_group)
        
        # Window Layout Group
        layout_group = QGroupBox("Window Layout")
        layout_vbox = QVBoxLayout(layout_group)

        reset_button = QPushButton("Reset Window Geometry")
        reset_button.clicked.connect(self._confirm_and_reset_geometries)

        info_label = QLabel("Restores all windows to their default size and screen position.")
        info_label.setWordWrap(True)
        
        layout_vbox.addWidget(reset_button)
        layout_vbox.addWidget(info_label)

        main_layout.addWidget(layout_group)
        
        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def load_current_settings(self):
        """Sets the UI controls to reflect the current settings."""
        current_unit = self.settings_manager.get_setting("unit_system")
        index = self.unit_combo.findData(current_unit)
        if index != -1:
            self.unit_combo.setCurrentIndex(index)

    def _confirm_and_reset_geometries(self):
        """Shows a confirmation dialog and resets window geometries if confirmed."""
        reply = QMessageBox.question(self, "Confirm Reset",
                                     "Are you sure you want to reset all saved window sizes and positions?\n\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.clear_all_window_geometries()
            QMessageBox.information(self, "Success", "Window geometry has been reset.")


    def accept(self):
        """Saves the settings when the user clicks OK."""
        selected_unit = self.unit_combo.currentData()
        self.settings_manager.set_setting("unit_system", selected_unit)
        super().accept()