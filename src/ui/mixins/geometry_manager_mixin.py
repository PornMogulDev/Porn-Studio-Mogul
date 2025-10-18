import logging
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import QRect

logger = logging.getLogger(__name__)

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

    def _get_window_name(self) -> str:
        """
        Returns the key used to store the window's geometry.
        Defaults to the class name. Override for multiple instances of the same class.
        """
        return self.__class__.__name__

    def _restore_geometry(self):
        """
        Loads the window's last known geometry from settings and applies it.
        If the geometry is off-screen or not found, it centers the window 
        on its parent or the primary monitor. This also connects to the 
        settings changed signal.
        """
        if not hasattr(self, 'settings_manager'):
            logger.warning(f"WARNING: {self.__class__.__name__} uses GeometryManagerMixin but lacks a 'settings_manager' attribute.")
            return

        self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)

        window_name = self._get_window_name()
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
                # If not visible (e.g., monitor disconnected), apply default position.
                self._apply_default_geometry()
        else:
            # If no geometry is saved, apply default position.
             self._apply_default_geometry()

        # Capture the initial geometry after it's been set for the session.
        self._initial_geometry = self.geometry()

        if not geometry_data:
            self._needs_centering = True

    def _save_geometry(self):
        """Saves the window's current geometry to the settings file."""
        if not hasattr(self, 'settings_manager'):
            return # Silently fail if settings_manager isn't present

        # Don't save geometry if the window is minimized or maximized,
        # as this doesn't represent the user's desired "normal" state.
        if self.isMinimized() or self.isMaximized():
            return

        window_name = self._get_window_name()
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

    def _apply_default_geometry(self):
        # Resize to a sensible default. Prioritize minimumSize as it's often
        # explicitly set for main windows. Fall back to sizeHint for dialogs.
        min_size = self.minimumSize()
        if min_size.width() > 0 and min_size.height() > 0:
            self.resize(min_size)
        else:
            size_hint = self.sizeHint()
            if size_hint.isValid():
                self.resize(size_hint)

        parent = self.parentWidget()
        if parent:
            parent_center = parent.mapToGlobal(parent.rect().center())
            self_rect = self.frameGeometry()
            self.move(parent_center.x() - self_rect.width() // 2,
                    parent_center.y() - self_rect.height() // 2)
        else:
            # Fallback: Center on primary screen
            if primary_screen := QApplication.primaryScreen():
                screen_geom = primary_screen.availableGeometry()
                self_rect = self.frameGeometry()
                self.move(screen_geom.center().x() - self_rect.width() // 2,
                          screen_geom.center().y() - self_rect.height() // 2)

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