from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, 
    QComboBox, QDialogButtonBox, QPushButton, QMessageBox, QFontComboBox, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class SettingsDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager

        # --- NEW: Store the initial theme to allow for cancellation ---
        self.initial_theme = self.settings_manager.get_setting("theme")
        self.initial_font_family = self.settings_manager.font_family
        self.initial_font_size = self.settings_manager.font_size

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setup_ui()
        self.load_current_settings()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Display Group
        display_group = QGroupBox("Display")
        display_v_layout = QVBoxLayout(display_group)

        # Unit System layout
        unit_layout = QHBoxLayout()
        unit_label = QLabel("Unit System:")
        self.unit_combo = QComboBox()
        self.unit_combo.addItem("Imperial (inches)", "imperial")
        self.unit_combo.addItem("Metric (cm)", "metric")
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(self.unit_combo)
        display_v_layout.addLayout(unit_layout)

        # Theme layout
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("System", "system")
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        display_v_layout.addLayout(theme_layout)

        # Font Family
        font_layout = QHBoxLayout()
        font_label = QLabel("Font:")
        self.font_combo = QFontComboBox()
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_combo)
        display_v_layout.addLayout(font_layout)

        # Font Size
        font_size_layout = QHBoxLayout()
        font_size_label = QLabel("Font Size:")
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 24)
        self.font_size_spinbox.setSuffix(" pt")
        font_size_layout.addWidget(font_size_label)
        font_size_layout.addWidget(self.font_size_spinbox)
        display_v_layout.addLayout(font_size_layout)
        
        main_layout.addWidget(display_group)
        
        # ... (Window Layout Group is unchanged) ...
        layout_group = QGroupBox("Window Layout")
        layout_vbox = QVBoxLayout(layout_group)

        reset_button = QPushButton("Reset Window Geometry")
        reset_button.clicked.connect(self._confirm_and_reset_geometries)

        info_label = QLabel("Restores all windows to their default size and screen position.")
        info_label.setWordWrap(True)
        
        layout_vbox.addWidget(reset_button)
        layout_vbox.addWidget(info_label)

        main_layout.addWidget(layout_group)

        main_layout.addStretch()
        
        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Apply")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # Connect the theme combo box to the preview slot ---
        self.theme_combo.currentTextChanged.connect(self._preview_theme)
        self.font_combo.currentFontChanged.connect(self._preview_font_family)
        self.font_size_spinbox.valueChanged.connect(self._preview_font_size)

    # Slot to handle live previewing of the theme 
    @pyqtSlot(str)
    def _preview_theme(self, theme_name: str):
        """Applies the selected theme as a preview."""
        # This works because set_setting emits a signal that the ApplicationWindow
        # is already listening to.
        self.settings_manager.set_setting("theme", theme_name.lower())

    @pyqtSlot("QFont")
    def _preview_font_family(self, font: "QFont"):
        """Applies the selected font family as a preview."""
        self.settings_manager.set_setting("font_family", font.family())

    @pyqtSlot(int)
    def _preview_font_size(self, size: int):
        """Applies the selected font size as a preview."""
        self.settings_manager.set_setting("font_size", size)

    def load_current_settings(self):
        """Sets the UI controls to reflect the current settings."""
        # Load unit system
        current_unit = self.settings_manager.get_setting("unit_system")
        index = self.unit_combo.findData(current_unit)
        if index != -1:
            self.unit_combo.setCurrentIndex(index)
            
        # Load theme setting
        current_theme = self.settings_manager.get_setting("theme")
        theme_index = self.theme_combo.findData(current_theme)
        if theme_index != -1:
            self.theme_combo.setCurrentIndex(theme_index)

        # Load font settings
        self.font_combo.setCurrentFont(QFont(self.initial_font_family))
        self.font_size_spinbox.setValue(self.initial_font_size)

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
        # Save unit system
        selected_unit = self.unit_combo.currentData()
        self.settings_manager.set_setting("unit_system", selected_unit)

        # Save font and scale settings
        self.settings_manager.set_setting("font_family", self.font_combo.currentFont().family())
        self.settings_manager.set_setting("font_size", self.font_size_spinbox.value())

        super().accept()

    def reject(self):
        """Reverts the theme to its original state and closes the dialog."""
        # Revert theme
        current_theme = self.settings_manager.get_setting("theme")
        if current_theme != self.initial_theme:
            self.settings_manager.set_setting("theme", self.initial_theme)

        # Revert font
        if self.settings_manager.font_family != self.initial_font_family:
            self.settings_manager.set_setting("font_family", self.initial_font_family)
        if self.settings_manager.font_size != self.initial_font_size:
            self.settings_manager.set_setting("font_size", self.initial_font_size)
        
        super().reject()