# src/utils/preset_handler.py
from typing import Callable, Dict
from PyQt6.QtWidgets import QMessageBox, QWidget

class PresetHandler:
    """
    Manages the logic for saving/loading/deleting presets via SettingsManager.
    Connects a PresetWidget to a data provider/consumer.
    """
    def __init__(self, 
                 widget, 
                 settings_manager, 
                 settings_key: str, 
                 parent_view: QWidget,
                 save_callback: Callable[[], Dict],
                 load_callback: Callable[[Dict], None]):
        """
        :param widget: The PresetWidget instance.
        :param settings_manager: The application SettingsManager.
        :param settings_key: The key used in settings (e.g., 'scene_planner_presets').
        :param parent_view: The parent widget for showing alerts.
        :param save_callback: Function returning the Dict data to save.
        :param load_callback: Function accepting a Dict to apply to the app state.
        """
        self.widget = widget
        self.settings_manager = settings_manager
        self.settings_key = settings_key
        self.view = parent_view
        self.get_data_to_save = save_callback
        self.apply_loaded_data = load_callback

        # Connect Signals
        self.widget.load_requested.connect(self.load_preset)
        self.widget.save_requested.connect(self.save_preset)
        self.widget.delete_requested.connect(self.delete_preset)
        
        self.refresh_ui()

    def refresh_ui(self, select_name=None):
        presets = self.settings_manager.get_setting(self.settings_key, {})
        self.widget.populate_presets(list(presets.keys()), select_name)

    def save_preset(self, name: str):
        if not name:
            QMessageBox.warning(self.view, "Save Preset", "Please enter a name for the preset.")
            return
        
        data = self.get_data_to_save()
        if data is None: return # Callback can cancel save by returning None

        presets = self.settings_manager.get_setting(self.settings_key, {}).copy()
        
        # Optional: Confirm overwrite
        if name in presets:
            if QMessageBox.question(self.view, "Confirm Overwrite", 
                                  f"Preset '{name}' already exists. Overwrite?",
                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return

        presets[name] = data
        self.settings_manager.set_setting(self.settings_key, presets)
        self.refresh_ui(select_name=name)
        QMessageBox.information(self.view, "Preset Saved", f"Preset '{name}' has been saved.")

    def load_preset(self, name: str):
        presets = self.settings_manager.get_setting(self.settings_key, {})
        data = presets.get(name)
        if not data:
            QMessageBox.warning(self.view, "Load Error", f"Could not find preset named '{name}'.")
            return
        
        try:
            self.apply_loaded_data(data)
        except Exception as e:
            QMessageBox.critical(self.view, "Load Error", f"Failed to load preset: {str(e)}")

    def delete_preset(self, name: str):
        if not name: return
        presets = self.settings_manager.get_setting(self.settings_key, {}).copy()
        
        if name not in presets: return

        if QMessageBox.question(self.view, "Delete Preset", 
                              f"Are you sure you want to delete '{name}'?",
                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del presets[name]
            self.settings_manager.set_setting(self.settings_key, presets)
            self.refresh_ui()