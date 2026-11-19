from PyQt6.QtCore import QObject
from data.game_state import Talent
from ui.builders.preferences_view_model_builder import build_preferences_view_model

class PreferencesPresenter(QObject):
    """
    Sub-presenter responsible for the PreferencesWidget.
    Handles calculating tag affinities, policies, and dynamic limits.
    """
    def __init__(self, controller, widget, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget

    def set_talent(self, talent: Talent):
        """Builds the preferences view model and updates the widget."""
        if not talent:
            return

        tag_definitions = self.controller.data_manager.tag_definitions
        policy_definitions = self.controller.data_manager.studio_policies_data

        preferences_data, limits, required_policies, refused_policies, ds_data = build_preferences_view_model(
            talent=talent,
            tag_definitions=tag_definitions,
            policy_definitions=policy_definitions
        )

        self.widget.display_preferences(
            preferences_data=preferences_data,
            limits=limits,
            required_policies=required_policies,
            refused_policies=refused_policies,
            ds_data=ds_data
        )

    def handle_theme_change(self, danger_color: str):
        """Updates widget colors when the theme changes."""
        self.widget.set_theme_colors(danger_color=danger_color)