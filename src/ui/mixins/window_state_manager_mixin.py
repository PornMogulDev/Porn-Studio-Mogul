# ui/mixins/window_state_manager_mixin.py

import logging
from PyQt6.QtCore import QByteArray

logger = logging.getLogger(__name__)

class WindowStateManagerMixin:
    """
    A mixin class for QMainWindow to save and restore the state of its
    dock widgets and toolbars between sessions.
    
    Usage:
    1. Inherit from this mixin in your QMainWindow subclass.
       e.g., class MyWindow(QMainWindow, WindowStateManagerMixin):
    
    2. Ensure your class has `self.settings_manager` and a `_get_window_name()` method.
    
    3. Call `self._restore_state()` at the end of your `__init__`.
    
    4. Override `closeEvent` in your QMainWindow to call `self._save_state()`.
    """

    def _get_window_name(self) -> str:
        """
        Placeholder method. The inheriting class must provide this.
        It should return the key used to store the window's state.
        """
        # This check is important because if the main class doesn't override this,
        # we get a clear error instead of a silent failure.
        if self.__class__.__name__ == "WindowStateManagerMixin":
            return "WindowStateManagerMixin"
        raise NotImplementedError(
            f"The class '{self.__class__.__name__}' must override the _get_window_name method."
        )

    def _save_state(self):
        """
        Saves the window's current layout state (docks, toolbars) to settings.
        The state is stored as a Base64 encoded string to be JSON-safe.
        """
        if not hasattr(self, 'settings_manager'):
            logger.warning(f"WARNING: {self.__class__.__name__} uses WindowStateManagerMixin but lacks a 'settings_manager' attribute.")
            return

        window_name = self._get_window_name()
        
        # saveState() returns a QByteArray, which can contain nulls.
        # We encode it to Base64 to safely store it in a JSON text file.
        layout_state_bytes = self.saveState().toBase64()
        layout_state_str = layout_state_bytes.data().decode('ascii')
        
        self.settings_manager.set_window_setting(window_name, 'layout_state', layout_state_str)

    def _restore_state(self):
        """
        Loads the window's last known layout state from settings and applies it.
        """
        if not hasattr(self, 'settings_manager'):
            logger.warning(f"WARNING: {self.__class__.__name__} uses WindowStateManagerMixin but lacks a 'settings_manager' attribute.")
            return

        window_name = self._get_window_name()
        layout_state_str = self.settings_manager.get_window_setting(window_name, 'layout_state')
        
        if layout_state_str:
            try:
                # Decode the Base64 string back into a QByteArray for restoreState().
                layout_state_bytes = QByteArray.fromBase64(layout_state_str.encode('ascii'))
                if not self.restoreState(layout_state_bytes):
                    logger.warning(f"Failed to restore layout state for '{window_name}'. State data might be corrupt.")
            except Exception as e:
                logger.error(f"Error decoding or restoring layout state for '{window_name}': {e}")