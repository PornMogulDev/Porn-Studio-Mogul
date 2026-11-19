from PyQt6.QtCore import QObject
from data.game_state import Talent
from ui.builders.talent_view_data_builder import TalentViewDataBuilder

class DetailsPresenter(QObject):
    """
    Sub-presenter responsible for populating the DetailsWidget.
    """
    def __init__(self, controller, widget, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget

    def set_talent(self, talent: Talent):
        """Loads and displays basic info and skills for the given talent."""
        if not talent:
            return
            
        basic_info = TalentViewDataBuilder.build_basic_info(talent, self.controller)
        skills_info = TalentViewDataBuilder.build_skills_info(talent)

        self.widget.display_basic_info(basic_info)
        self.widget.display_skills(skills_info)
        self.widget.populate_physical_label(talent)