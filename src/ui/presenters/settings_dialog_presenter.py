from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtGui import QFont

from core.interfaces import IGameController
from ui.view_models import SettingsViewModel

# Forward reference for type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.dialogs.settings_dialog import SettingsDialog

class SettingsDialogPresenter(QObject):
    """
    Presenter for the SettingsDialog. Manages the dialog's state,
    handles live previews, and correctly applies or reverts changes upon closing.
    """
    def __init__(self, controller: IGameController, view: 'SettingsDialog'):
        super().__init__()
        self.controller = controller
        self.settings_manager = controller.settings_manager
        self.view = view

        # --- Capture Initial State ---
        # This snapshot is crucial for the "revert on cancel" functionality.
        self.initial_unit_system = self.settings_manager.get_setting("unit_system")
        self.initial_theme = self.settings_manager.get_setting("theme")
        self.initial_font_family = self.settings_manager.font_family
        self.initial_font_size = self.settings_manager.font_size

        self._connect_signals()
        self._populate_initial_view()

    def _connect_signals(self):
        """Connects signals from the view to the presenter's slots."""
        # Live preview signals
        self.view.theme_preview_changed.connect(self.on_theme_preview)
        self.view.font_family_preview_changed.connect(self.on_font_family_preview)
        self.view.font_size_preview_changed.connect(self.on_font_size_preview)

        # Action signals
        self.view.reset_geometries_requested.connect(self.on_reset_geometries_requested)

        # Final decision signals from the dialog
        self.view.accepted.connect(self.on_accepted)
        self.view.rejected.connect(self.on_rejected)

    def _populate_initial_view(self):
        """Creates a view model from the initial state and populates the view."""
        vm = SettingsViewModel(
            unit_system=self.initial_unit_system,
            theme=self.initial_theme,
            font_family=self.initial_font_family,
            font_size=self.initial_font_size
        )
        self.view.populate_controls(vm)

    @pyqtSlot(str)
    def on_theme_preview(self, theme_name: str):
        """Applies the selected theme as a live preview."""
        self.settings_manager.set_setting("theme", theme_name)

    @pyqtSlot(QFont)
    def on_font_family_preview(self, font: QFont):
        """Applies the selected font family as a live preview."""
        self.settings_manager.set_setting("font_family", font.family())

    @pyqtSlot(int)
    def on_font_size_preview(self, size: int):
        """Applies the selected font size as a live preview."""
        self.settings_manager.set_setting("font_size", size)

    @pyqtSlot()
    def on_reset_geometries_requested(self):
        """Shows a confirmation dialog and resets window geometries if confirmed."""
        reply = QMessageBox.question(self.view, "Confirm Reset",
                                     "Are you sure you want to reset all saved window sizes and positions?\n\nThis action cannot be undone.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel)

        if reply == QMessageBox.StandardButton.Yes:
            self.settings_manager.clear_all_window_geometries()
            QMessageBox.information(self.view, "Success", "Window geometry has been reset.")

    @pyqtSlot()
    def on_accepted(self):
        """
        Finalizes the settings. Theme and font are already set due to live
        preview, so we only need to commit the non-previewed settings.
        """
        final_unit_system = self.view.get_selected_unit_system()
        self.settings_manager.set_setting("unit_system", final_unit_system)
        
        # We also need to explicitly save the final font settings in case the user
        # changed them and then clicked Apply without triggering a final preview signal.
        final_font = self.view.get_selected_font()
        self.settings_manager.set_setting("font_family", final_font.family())
        self.settings_manager.set_setting("font_size", self.view.get_selected_font_size())


    @pyqtSlot()
    def on_rejected(self):
        """
        Reverts any previewed changes by restoring the initial settings snapshot.
        """
        # Revert theme if it was changed
        if self.settings_manager.get_setting("theme") != self.initial_theme:
            self.settings_manager.set_setting("theme", self.initial_theme)

        # Revert font family if it was changed
        if self.settings_manager.font_family != self.initial_font_family:
            self.settings_manager.set_setting("font_family", self.initial_font_family)
            
        # Revert font size if it was changed
        if self.settings_manager.font_size != self.initial_font_size:
            self.settings_manager.set_setting("font_size", self.initial_font_size)