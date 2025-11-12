from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, 
    QComboBox, QDialogButtonBox, QPushButton, QFontComboBox, QSpinBox
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.settings_dialog_presenter import SettingsDialogPresenter
from ui.view_models import SettingsViewModel

class SettingsDialog(GeometryManagerMixin, QDialog):
    # --- Signals for the Presenter ---
    theme_preview_changed = pyqtSignal(str)
    font_family_preview_changed = pyqtSignal(QFont)
    font_size_preview_changed = pyqtSignal(int)
    reset_geometries_requested = pyqtSignal()
    
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        # The view no longer knows about the controller directly, but the presenter needs it.
        # We still need settings_manager for the GeometryManagerMixin.
        self.settings_manager = controller.settings_manager

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setup_ui()
        
        # --- Presenter Creation (Modal Dialog Pattern) ---
        # The view creates its own presenter and its lifecycle is tied to the dialog's.
        self.presenter = SettingsDialogPresenter(controller, self)

        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Display Group ---
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
        
        # --- Window Layout Group ---
        layout_group = QGroupBox("Window Layout")
        layout_vbox = QVBoxLayout(layout_group)

        reset_button = QPushButton("Reset Window Geometry")
        info_label = QLabel("Restores all windows to their default size and screen position.")
        info_label.setWordWrap(True)
        
        layout_vbox.addWidget(reset_button)
        layout_vbox.addWidget(info_label)
        main_layout.addWidget(layout_group)
        main_layout.addStretch()
        
        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText("Apply")
        # The presenter now connects to the dialog's accepted/rejected signals.
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # --- Signal Connections (View -> Presenter) ---
        # Connect UI interactions to the signals the presenter listens for.
        self.theme_combo.currentTextChanged.connect(self._on_theme_text_changed)
        self.font_combo.currentFontChanged.connect(self.font_family_preview_changed)
        self.font_size_spinbox.valueChanged.connect(self.font_size_preview_changed)
        reset_button.clicked.connect(self.reset_geometries_requested)
    
    def _on_theme_text_changed(self, text: str):
        """Internal slot to convert theme display text to lowercase data value."""
        self.theme_preview_changed.emit(text.lower())

    def populate_controls(self, vm: SettingsViewModel):
        """
        Sets the UI controls to reflect the initial settings provided by the presenter.
        """
        # Block signals to prevent previews from firing during setup.
        self.unit_combo.blockSignals(True)
        self.theme_combo.blockSignals(True)
        self.font_combo.blockSignals(True)
        self.font_size_spinbox.blockSignals(True)

        # Load unit system
        index = self.unit_combo.findData(vm.unit_system)
        if index != -1:
            self.unit_combo.setCurrentIndex(index)
            
        # Load theme setting
        theme_index = self.theme_combo.findText(vm.theme.capitalize())
        if theme_index != -1:
            self.theme_combo.setCurrentIndex(theme_index)

        # Load font settings
        self.font_combo.setCurrentFont(QFont(vm.font_family))
        self.font_size_spinbox.setValue(vm.font_size)

        # Unblock signals now that setup is complete.
        self.unit_combo.blockSignals(False)
        self.theme_combo.blockSignals(False)
        self.font_combo.blockSignals(False)
        self.font_size_spinbox.blockSignals(False)

    # --- Data Access Methods for Presenter ---
    def get_selected_unit_system(self) -> str:
        """Allows the presenter to get the final selected unit system."""
        return self.unit_combo.currentData()

    def get_selected_font(self) -> QFont:
        """Allows the presenter to get the final selected font."""
        return self.font_combo.currentFont()
    
    def get_selected_font_size(self) -> int:
        """Allows the presenter to get the final selected font size."""
        return self.font_size_spinbox.value()

    # The accept and reject methods are now empty shells. The presenter's slots,
    # connected to the accepted/rejected signals, contain all the logic.
    # We still need to override them to call the base implementation.
    def accept(self):
        super().accept()

    def reject(self):
        super().reject()