from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QStackedWidget, QLabel, QListWidget,
    QPushButton, QMenu, QMessageBox, QListWidgetItem, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSignal

class HiringWidget(QWidget):
    """A widget for assigning a talent to available roles."""
    preview_cost_requested = pyqtSignal(list) # Emits list of selected role data dicts
    hire_confirmed = pyqtSignal(dict)  # {'roles': [...], 'upfront_cost': X}
    sponsor_tour_requested = pyqtSignal(list) # roles_for_tour
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._bulk_discount_tiers = {}
        self._current_talent_base_location = ""
        self._current_studio_location = ""
        # Stores the latest authoritative calculation result from the presenter
        self._current_cost_breakdown = None

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        contract_container = QGroupBox("Assign to Role")
        contract_layout = QVBoxLayout(contract_container)
        self.roles_stack = QStackedWidget()
        
        roles_list_widget = QWidget()
        roles_list_layout = QVBoxLayout(roles_list_widget)
        roles_list_layout.addWidget(QLabel("Available Roles (from scenes in 'casting'):"))
        self.available_roles_list = QListWidget()
        self.available_roles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_roles_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        roles_list_layout.addWidget(self.available_roles_list)
        
        roles_no_scenes_widget = QLabel("There are no uncast roles available for this talent.")
        roles_no_scenes_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roles_no_scenes_widget.setWordWrap(True)
        
        self.roles_stack.addWidget(roles_list_widget)
        self.roles_stack.addWidget(roles_no_scenes_widget)
        contract_layout.addWidget(self.roles_stack)

        button_layout = QHBoxLayout()
        self.hire_button = QPushButton("Assign Talent to Selected Role(s)")
        self.sponsor_tour_button = QPushButton("Sponsor Tour...")
        self.sponsor_tour_button.setToolTip("Select multiple non-local (for the talent) roles within a 4-week period to enable.\n" \
        "The start of the tour must be at least 3 weeks away from the date of hiring.")
        button_layout.addWidget(self.hire_button)
        button_layout.addWidget(self.sponsor_tour_button)
        self.sponsor_tour_button.setEnabled(False) # Disabled by default
        contract_layout.addLayout(button_layout)

        self.total_cost_label = QLabel("Select role(s) to see total cost.")
        self.total_cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_cost_label.setObjectName("SubtleText") # For styling
        contract_layout.addWidget(self.total_cost_label)
        
        main_layout.addWidget(contract_container)

    def _connect_signals(self):
        self.available_roles_list.itemSelectionChanged.connect(self._request_cost_preview)
        self.available_roles_list.itemSelectionChanged.connect(self._update_ui_state)
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        self.available_roles_list.customContextMenuRequested.connect(self._show_role_context_menu)
        self.hire_button.clicked.connect(self._confirm_hire)
        self.sponsor_tour_button.clicked.connect(self._on_sponsor_tour_clicked)

    def update_available_roles(self, available_roles: list, talent_base_location: str, studio_location: str):
        self.available_roles_list.clear()
        self._current_talent_base_location = talent_base_location
        self._current_studio_location = studio_location

        if not available_roles:
            self.roles_stack.setCurrentIndex(1)
            return

        self.roles_stack.setCurrentIndex(0)
        for role_data in available_roles:

            # Display cost breakdown if there's a travel fee.            
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, role_data)  # Store the whole dict
            role_details_html = role_data.get('tooltip_html', 'Role details not available.')
            item.setToolTip(role_details_html)

            if role_data['is_available']:
                # Display cost breakdown for available roles.
                total_cost = role_data.get('cost', 0)
                base_cost = role_data.get('base_cost', total_cost)
                travel_fee = role_data.get('travel_fee', 0)
                rush_fee = role_data.get('rush_fee', 0)
 
                cost_parts = [f"Base: ${base_cost:,}"]
                if travel_fee > 0: cost_parts.append(f"Travel: ${travel_fee:,}")
                if rush_fee > 0: cost_parts.append(f"Rush: ${rush_fee:,}")
                cost_breakdown_text = ", ".join(cost_parts)
                cost_text = f"Cost: ${total_cost:,} ({cost_breakdown_text})"
 
                display_text = f"{role_data['scene_title']} - Role: {role_data['vp_name']} ({cost_text})"
                item.setText(display_text)
            else: # Role is unavailable
                reason = role_data.get('refusal_reason', 'Unknown reason')
                display_text = f"{role_data['scene_title']} - Role: {role_data['vp_name']} (Unavailable: {reason})"
                item.setText(display_text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
 
            self.available_roles_list.addItem(item)
 
        # Trigger a recalculation in case a role was removed that was part of the selection
        self._update_ui_state()

    def set_discount_tiers(self, tiers: dict):
        """Receives the discount configuration from the presenter."""
        self._bulk_discount_tiers = tiers

    def _update_ui_state(self):
        """Calculates cost preview and updates the state of UI elements like buttons."""
        self._request_cost_preview()
        self._update_sponsor_tour_button_state()

    def _update_sponsor_tour_button_state(self):
        """Checks if the current selection is eligible for a tour sponsorship."""
        selected_items = self.available_roles_list.selectedItems()

        # Rule 1: Must have at least 2 roles selected
        if len(selected_items) < 2:
            self.sponsor_tour_button.setEnabled(False)
            return

        # Rule 2: Talent must not be local to the studio
        if self._current_talent_base_location == self._current_studio_location:
             self.sponsor_tour_button.setEnabled(False)
             return

        roles_data = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        # Rule 3: The roles must span a period of 1 to 4 weeks.
        # We can use a simple week-of-all-time calculation for comparison.
        role_dates = [(r['scheduled_year'] * 52 + r['scheduled_week']) for r in roles_data]
        min_date, max_date = min(role_dates), max(role_dates)
        duration_weeks = (max_date - min_date) + 1
        
        if not (1 <= duration_weeks <= 4):
            self.sponsor_tour_button.setEnabled(False)
            return

        # All rules passed
        self.sponsor_tour_button.setEnabled(True)

    def _request_cost_preview(self):
        """Gathers selected roles and emits a signal requesting a cost preview calculation."""
        selected_items = self.available_roles_list.selectedItems()

        if not selected_items:
            self.hire_button.setEnabled(False)
            self.total_cost_label.setText("Select role(s) to see total cost.")
            self._current_cost_breakdown = None
            return
            
        self.total_cost_label.setText("<i>Calculating...</i>")
        roles_data = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        self.preview_cost_requested.emit(roles_data)

    def update_cost_preview(self, cost_breakdown: dict):
        """Public slot for the Presenter to update the UI with calculated costs."""
        if not cost_breakdown:
            self.total_cost_label.setText("<span style='color:red;'>Error calculating cost.</span>")
            self._current_cost_breakdown = None
            self.hire_button.setEnabled(False)
            return

        self._current_cost_breakdown = cost_breakdown
        total_upfront_cost = cost_breakdown.get('total_upfront_cost', 0)
        roles_with_salaries = cost_breakdown.get('roles_with_final_salaries', [])
        total_deferred_cost = sum(role['final_salary'] for role in roles_with_salaries)

        grand_total = total_upfront_cost + total_deferred_cost
        
        self.hire_button.setEnabled(True)
        self.total_cost_label.setText(f"<b>Total:</b> ${int(grand_total):,} (Upfront: ${int(total_upfront_cost):,}, On Shoot: ${int(total_deferred_cost):,})")

    def _on_role_double_clicked(self, item: QListWidgetItem):
        if role_data := item.data(Qt.ItemDataRole.UserRole):
            self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def _on_sponsor_tour_clicked(self):
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items:
            return

        roles_for_tour = [{
            'scene_id': item.data(Qt.ItemDataRole.UserRole)['scene_id'],
            'virtual_performer_id': item.data(Qt.ItemDataRole.UserRole)['virtual_performer_id']
        } for item in selected_items]

        self.sponsor_tour_requested.emit(roles_for_tour)

    def _show_role_context_menu(self, pos):
        item = self.available_roles_list.itemAt(pos)
        if not item:
            return

        if role_data := item.data(Qt.ItemDataRole.UserRole):
            menu = QMenu(self)
            view_scene_action = menu.addAction("View Scene")
            
            global_pos = self.available_roles_list.viewport().mapToGlobal(pos)
            
            action = menu.exec(global_pos)
            if action == view_scene_action:
                self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def _confirm_hire(self):
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Roles Selected", "Please select one or more roles to assign the talent to.")
            return
        
        if not self._current_cost_breakdown:
            QMessageBox.critical(self, "Calculation Error", "Could not confirm hire because the final cost has not been calculated.")
            return
        
        # We must read the correct key, perform validation, and then emit the
        # payload with the key re-mapped for the command service.
        roles_list = self._current_cost_breakdown.get('roles_with_final_salaries', [])
        
        if len(roles_list) != len(set(r['scene_id'] for r in roles_list)):
                QMessageBox.warning(self, "Casting Error", "Cannot cast for multiple roles in the same scene.\nA talent can only be cast once per scene.")
                return
        # Construct the final payload with the key name expected by the command service.
        hiring_payload = {
            'upfront_cost': self._current_cost_breakdown.get('total_upfront_cost', 0),
            'roles': roles_list
        }
        self.hire_confirmed.emit(hiring_payload)