from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QRect

class GeometryManagerMixin:
    """
    A mixin class to save and restore a QWidget's geometry between sessions.
    
    Usage:
    1. Inherit from this mixin in your QWidget/QDialog subclass.
       e.g., class MyDialog(QDialog, GeometryManagerMixin):
    
    2. Ensure your class has a `self.settings_manager` attribute.
    
    3. Call `self._restore_geometry()` at the end of your `__init__`.
    """
    _initial_geometry: QRect | None = None

    def _restore_geometry(self):
        """
        Loads the window's last known geometry from settings and applies it.
        If the geometry is off-screen, it centers the window on the primary
        monitor instead. This also connects to the settings changed signal.
        """
        if not hasattr(self, 'settings_manager'):
            print(f"Warning: {self.__class__.__name__} uses GeometryManagerMixin but lacks a 'settings_manager' attribute.")
            return

        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

        window_name = self.__class__.__name__
        geometry_data = self.settings_manager.get_window_geometry(window_name)

        if geometry_data:
            geom = QRect(
                geometry_data.get('x', 100),
                geometry_data.get('y', 100),
                geometry_data.get('width', 800),
                geometry_data.get('height', 600)
            )

            # --- Visibility Check ---
            is_visible = False
            if available_screens := QApplication.screens():
                for screen in available_screens:
                    # Check if the restored geometry intersects with any available screen
                    if screen.geometry().intersects(geom):
                        is_visible = True
                        break
            
            if is_visible:
                self.setGeometry(geom)
            else:
                # If not visible (e.g., monitor disconnected), center it.
                self._center_on_primary_screen()
        else:
            # If no geometry is saved, center it as a default behavior.
             self._center_on_primary_screen()

        # Capture the initial geometry after it's been set for the session.
        self._initial_geometry = self.geometry()

    def _save_geometry(self):
        """Saves the window's current geometry to the settings file."""
        if not hasattr(self, 'settings_manager'):
            return # Silently fail if settings_manager isn't present

        # Don't save geometry if the window is minimized or maximized,
        # as this doesn't represent the user's desired "normal" state.
        if self.isMinimized() or self.isMaximized():
            return

        window_name = self.__class__.__name__
        geom = self.geometry()

        geometry_data = {
            'x': geom.x(),
            'y': geom.y(),
            'width': geom.width(),
            'height': geom.height()
        }
        self.settings_manager.set_window_geometry(window_name, geometry_data)

    def closeEvent(self, event):
        """Overridden to save geometry just before the window closes via 'X' button."""
        self._save_geometry()
        # Ensure the parent's closeEvent is also called.
        if hasattr(super(), 'closeEvent'):
            super().closeEvent(event)
    
    def done(self, result: int):
        """
        Overridden to save geometry when the dialog is closed via accept(), reject(),
        or a direct call to done().
        """
        self._save_geometry()
        # This check is necessary because QDialog is not a universal base class
        if isinstance(self, QDialog):
            super().done(result)

    def _center_on_primary_screen(self):
        """Helper method to center the widget on the primary screen."""
        if primary_screen := QApplication.primaryScreen():
            # Use availableGeometry() to avoid overlapping with taskbars, etc.
            screen_geom = primary_screen.availableGeometry()
            # A simple move to the center of the screen, letting the widget keep its sizeHint.
            self.move(screen_geom.center() - self.rect().center())

    def _on_setting_changed(self, key: str):
        """
        Slot that reacts to a setting being changed. If window geometries are
        affected, it re-runs the restore logic to apply defaults if necessary.
        """
        if key == "window_geometries":
            # Re-run the geometry logic. If our saved position was just deleted,
            # this will correctly re-center the window.
            self._restore_geometry()
            
    def revert_to_initial_geometry(self):
        """
        Reverts the window's geometry to the state it was in when it was
        first shown in the current session.
        """
        if self._initial_geometry:
            self.setGeometry(self._initial_geometry)