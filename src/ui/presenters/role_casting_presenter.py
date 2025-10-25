from PyQt6.QtCore import QObject, pyqtSlot
from typing import TYPE_CHECKING, List

from core.interfaces import IGameController
from data.game_state import Talent

if TYPE_CHECKING:
    from ui.dialogs.role_casting_dialog import RoleCastingDialog

class RoleCastingPresenter(QObject):
    def __init__(self, controller: IGameController, view: 'RoleCastingDialog', scene_id: int, vp_id: int):
        super().__init__(view) # Ensure presenter is child of view for lifecycle management
        self.controller = controller
        self.view = view
        self.scene_id = scene_id
        self.vp_id = vp_id

        self._all_eligible_talent: List[Talent] = []
        self._connect_signals()
        self._load_initial_data()

    def _connect_signals(self):
        self.view.name_filter_changed.connect(self._on_name_filter_changed)
        self.view.hire_requested.connect(self._on_hire_requested)
    
    def _load_initial_data(self):
        # This single call gets all talent who are eligible and willing
        self._all_eligible_talent = self.controller.hire_talent_service.get_eligible_talent_for_role(
            self.scene_id, self.vp_id
        )
        self.view.update_talent_table(self._all_eligible_talent)

    @pyqtSlot(str)
    def _on_name_filter_changed(self, text: str):
        text_lower = text.lower()
        if not text_lower:
            self.view.update_talent_table(self._all_eligible_talent)
            return
        
        filtered_list = [
            talent for talent in self._all_eligible_talent 
            if text_lower in talent.alias.lower()
        ]
        self.view.update_talent_table(filtered_list)
        
    @pyqtSlot(object)
    def _on_hire_requested(self, talent: Talent):
        cost = self.controller.calculate_talent_demand(talent.id, self.scene_id, self.vp_id)
        self.controller.cast_talent_for_virtual_performer(talent.id, self.scene_id, self.vp_id, cost)
        self.view.close()