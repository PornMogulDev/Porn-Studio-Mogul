from PyQt6.QtCore import QObject
from data.game_state import Talent

class ChemistryPresenter(QObject):
    """
    Sub-presenter responsible for the ChemistryWidget.
    Handles data population and smart-hover/navigation interactions.
    """
    def __init__(self, controller, widget, uimanager, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget
        self.uimanager = uimanager
        self._connect_signals()

    def _connect_signals(self):
        # Navigation
        self.widget.talent_profile_requested.connect(self.uimanager.show_talent_profile_by_id)
        
        # Smart Hover / Interactions
        self.widget.smart_hover_entered.connect(self.uimanager.show_talent_summary)
        self.widget.smart_hover_left.connect(self.uimanager.hide_talent_summary)
        self.widget.smart_alt_clicked.connect(self.uimanager.show_talent_profile_by_id)

    def set_talent(self, talent: Talent):
        """Calculates chemistry scores with other talent and updates the widget."""
        if not talent:
            return

        raw_chemistry_dict = self.controller.get_talent_chemistry(talent.id)

        chemistry_view_model = []
        for other_talent_id, chem_details in raw_chemistry_dict.items(): 
            if other_talent := self.controller.get_talent_by_id(other_talent_id):
                chemistry_view_model.append({
                    'other_talent_id': other_talent_id,
                    'other_talent_alias': other_talent.alias,
                    'score': chem_details['score'] 
                })

        self.widget.display_chemistry(chemistry_view_model)