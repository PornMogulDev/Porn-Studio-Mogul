import logging
from typing import Optional
from PyQt6.QtWidgets import QApplication, QWidget
from ui.widgets.entity_card.entity_summary_card import EntitySummaryCard

logger = logging.getLogger(__name__)

class TooltipManager:
    """
    Manages the lifecycle and positioning of the EntitySummaryCard (Smart Hover).
    Decouples visual tooltip logic from the main UIManager.
    """
    def __init__(self, controller, parent_widget: QWidget = None):
        self.controller = controller
        self.settings_manager = controller.settings_manager
        self.parent_widget = parent_widget
        self._summary_card: Optional[EntitySummaryCard] = None

    def _get_card(self) -> EntitySummaryCard:
        if not self._summary_card:
            self._summary_card = EntitySummaryCard(self.settings_manager, self.parent_widget)
        return self._summary_card

    def show_talent_summary(self, talent_id: int, global_pos):
        talent = self.controller.get_talent_by_id(talent_id)
        if not talent:
            return

        card = self._get_card()
        card.load_talent(talent, self.controller)

        # Smart Positioning Logic to keep tooltip on screen
        screen = QApplication.screenAt(global_pos)
        if screen:
            screen_geo = screen.availableGeometry()
            card_geo = card.sizeHint() 
            
            x = global_pos.x() + 15
            y = global_pos.y() + 15

            # Check Right Edge
            if x + card_geo.width() > screen_geo.right():
                x = global_pos.x() - card_geo.width() - 5
            
            # Check Bottom Edge
            if y + card_geo.height() > screen_geo.bottom():
                y = global_pos.y() - card_geo.height() - 5
            
            card.move(x, y)
        else:
             card.move(global_pos.x() + 15, global_pos.y() + 15)

        card.show()
        card.raise_()

    def hide_summary(self):
        if self._summary_card:
            self._summary_card.hide()
            
    def cleanup(self):
        if self._summary_card:
            self._summary_card.close()
            self._summary_card = None