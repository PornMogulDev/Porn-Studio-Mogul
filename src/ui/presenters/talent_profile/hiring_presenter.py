import logging
from dataclasses import asdict
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from data.game_state import Talent
from ui.dialogs.sponsor_tour_dialog import SponsorTourDialog
from ui.builders.role_details_builder import prepare_role_details_data, format_role_details_html

logger = logging.getLogger(__name__)

class HiringPresenter(QObject):
    """
    Sub-presenter responsible for the HiringWidget.
    Handles role assignment, contract negotiation, and tour sponsorship flows.
    """
    def __init__(self, controller, widget, uimanager, view_parent, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.widget = widget
        self.uimanager = uimanager
        self.view_parent = view_parent
        self.current_talent_id: Optional[int] = None
        self._current_tour_roles: List[Dict] = []
        self._active_tour_dialog: Optional[SponsorTourDialog] = None

        self._configure_widget()
        self._connect_signals()

    def _configure_widget(self):
        raw_discount_tiers = self.controller.data_manager.game_config.get("hiring_bulk_discount_tiers", {})
        cleaned_discount_tiers = {int(k): v for k, v in raw_discount_tiers.items()}
        self.widget.set_discount_tiers(cleaned_discount_tiers)

    def _connect_signals(self):
        self.widget.preview_cost_requested.connect(self._calculate_bulk_hiring_preview)
        self.widget.hire_confirmed.connect(self._on_hire_confirmed)
        self.widget.sponsor_tour_requested.connect(self._on_sponsor_tour_requested)
        self.widget.open_scene_dialog_requested.connect(self.uimanager.show_scene_planner)
        self.widget.contract_preview_requested.connect(self._on_contract_preview_requested)
        self.widget.contract_sign_requested.connect(self._on_contract_sign_requested)

    def set_talent(self, talent: Talent):
        """Refreshes the available roles list for the given talent."""
        if not talent:
            self.current_talent_id = None
            return
            
        self.current_talent_id = talent.id
        self.refresh_available_roles(talent)

    def refresh_available_roles(self, talent: Talent):
        """Fetches and updates the list of available roles for the current talent."""
        available_roles = self.controller.find_available_roles_for_talent(talent.id)
        
        for role_data in available_roles:
            details_dict = prepare_role_details_data(
                role_data['scene_id'], 
                role_data['virtual_performer_id'], 
                self.controller
            )
            tooltip_html = format_role_details_html(details_dict)
            role_data['tooltip_html'] = tooltip_html
            
        studio_location = self.controller.game_state.studio.location
        is_contracted = getattr(talent, 'contract', None) is not None
        
        try:
            self.widget.update_available_roles(
                available_roles, 
                talent.base_location, 
                studio_location, 
                is_contracted
            )
        except RuntimeError:
            pass
            
        # Update theme colors based on current settings
        current_theme = self.controller.get_current_theme()
        self.handle_theme_change(current_theme.danger)

    def handle_theme_change(self, danger_color: str):
        self.widget.set_theme_colors(danger_color=danger_color)

    @pyqtSlot(list)
    def _calculate_bulk_hiring_preview(self, selected_roles_data: list):
        if not self.current_talent_id or not selected_roles_data:
            self.widget.update_cost_preview(None)
            return

        # 1. Validation Phase
        validation_results = self.controller.validate_potential_bookings(
            self.current_talent_id, selected_roles_data
        )

        valid_roles = []
        invalid_roles = []

        for role_data in selected_roles_data:
            key = (role_data['scene_id'], role_data['virtual_performer_id'])
            result = validation_results.get(key)
            
            if not result:
                continue

            if result.success:
                valid_roles.append(role_data)
            else:
                error_role = role_data.copy()
                error_role['error_reason'] = result.reason
                invalid_roles.append(error_role)

        # 2. Calculation Phase
        cost_breakdown = self.controller.calculate_bulk_hiring_costs(
            self.current_talent_id, valid_roles
        )
        
        if cost_breakdown:
            cost_breakdown['invalid_roles'] = invalid_roles
        self.widget.update_cost_preview(cost_breakdown)

    @pyqtSlot(dict)
    def _on_hire_confirmed(self, hiring_data: dict):
        if not self.current_talent_id: return
        self.controller.cast_talent_for_multiple_roles(self.current_talent_id, hiring_data)

    @pyqtSlot(list)
    def _on_sponsor_tour_requested(self, roles_for_tour: list):
        """Handles the request to sponsor a tour."""
        if not self.current_talent_id:
            return

        # 1. Fetch preview data
        result_dto = self.controller.get_tour_sponsorship_preview(
            self.current_talent_id, roles_for_tour
        )
        preview_data_dict = asdict(result_dto)

        # 2. Check feasibility
        if not preview_data_dict.get('is_feasible'):
            reason = preview_data_dict.get('refusal_reason', "Unknown reason.")
            QMessageBox.warning(
                self.view_parent, 
                "Tour Infeasible", 
                f"Cannot sponsor this tour: {reason}"
            )
            return

        # 3. Store roles for the callback
        self._current_tour_roles = roles_for_tour

        # 4. Open Dialog
        talent = self.controller.get_talent_by_id(self.current_talent_id)
        if not talent: return
        
        self._active_tour_dialog = SponsorTourDialog(
            talent.alias, preview_data_dict, parent=self.view_parent
        )
        self._active_tour_dialog.tour_confirmed.connect(self._execute_tour)
        
        # Dialog lifecycle is now managed by _execute_tour's success/fail logic
        # or the user clicking Cancel (rejected).
        self._active_tour_dialog.exec()
        
        # Cleanup after dialog closes
        self._active_tour_dialog = None
        self._current_tour_roles = []

    def _execute_tour(self):
        """Called by the dialog's signal when user confirms."""
        if not self._active_tour_dialog or not self.current_talent_id:
            return
            
        final_tour_details = self._active_tour_dialog.get_selected_tour_details()
        total_cost = self._active_tour_dialog.get_final_cost()
        
        if not final_tour_details:
            self._active_tour_dialog.show_error_message("Invalid tour details.")
            return

        try:
            # Attempt to execute the transaction
            self.controller.sponsor_tour(
                self.current_talent_id,
                self._current_tour_roles,
                final_tour_details,
                total_cost
            )
            
            # If successful (no exception raised), we close the dialog
            self._active_tour_dialog.accept()
            
        except Exception as e:
            logger.error(f"Failed to sponsor tour: {e}", exc_info=True)
            # If failed, keep dialog open and show error
            self._active_tour_dialog.show_error_message(f"An error occurred while processing the tour: {str(e)}")

    @pyqtSlot(dict)
    def _on_contract_preview_requested(self, terms: dict):
        if not self.current_talent_id: return
        salary = self.controller.calculate_contract_salary(self.current_talent_id, terms)
        self.widget.update_contract_preview(salary)

    @pyqtSlot(dict)
    def _on_contract_sign_requested(self, terms: dict):
        if not self.current_talent_id: return
        self.controller.sign_contract(self.current_talent_id, terms)