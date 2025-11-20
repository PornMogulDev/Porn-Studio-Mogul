from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QStackedWidget, QLabel, QListWidget,
    QPushButton, QMenu, QMessageBox, QListWidgetItem, QHBoxLayout, QFormLayout,
    QSlider, QSpinBox, QComboBox, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class HiringWidget(QWidget):
    """A widget for assigning a talent to available roles."""
    preview_cost_requested = pyqtSignal(list) # Emits list of selected role data dicts
    hire_confirmed = pyqtSignal(dict)  # {'roles': [...], 'upfront_cost': X}
    sponsor_tour_requested = pyqtSignal(list) # roles_for_tour
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id
    # Contract Signals
    contract_preview_requested = pyqtSignal(dict) # Emits terms dict
    contract_sign_requested = pyqtSignal(dict) # Emits terms dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bulk_discount_tiers = {}
        self._current_talent_base_location = ""
        self._current_studio_location = ""
        self._danger_color = QColor("red") # Default fallback
        self._current_cost_breakdown = None
        self._is_contracted = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Main Stack: Standard Hiring vs. Negotiation ---
        self.main_stack = QStackedWidget()
        
        # --- Page 1: Standard Hiring View ---
        self.hiring_page = QWidget()
        hiring_layout = QVBoxLayout(self.hiring_page)

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

        # Negotiation Entry Button
        self.negotiate_button = QPushButton("Offer Exclusive Contract")
        contract_layout.addWidget(self.negotiate_button)

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
        self.total_cost_label.setObjectName("totalCostLabel") # Changed for specific theming
        contract_layout.addWidget(self.total_cost_label)
        
        hiring_layout.addWidget(contract_container)
        self.main_stack.addWidget(self.hiring_page)

        # --- Page 2: Contract Negotiation View ---
        self.negotiation_page = QWidget()
        neg_layout = QVBoxLayout(self.negotiation_page)
        
        neg_group = QGroupBox("Exclusive Contract Terms")
        form_layout = QFormLayout(neg_group)
        
        # Duration
        self.duration_slider = QSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(12, 156)
        self.duration_slider.setValue(52)
        self.duration_label = QLabel("52 weeks")
        self.duration_slider.valueChanged.connect(lambda v: self.duration_label.setText(f"{v} weeks"))
        form_layout.addRow("Duration:", self._wrap_slider(self.duration_slider, self.duration_label))
        
        # Max Scenes
        self.max_scenes_spin = QSpinBox()
        self.max_scenes_spin.setRange(1, 7)
        self.max_scenes_spin.setValue(1)
        form_layout.addRow("Max Scenes/Week:", self.max_scenes_spin)
        
        # Dynamic Limit
        self.max_dynamic_combo = QComboBox()
        self.max_dynamic_combo.addItems(["0 (Vanilla)", "1 (Standard)", "2 (Hardcore)", "3 (Extreme)"])
        self.max_dynamic_combo.setCurrentIndex(3)
        form_layout.addRow("Max Intensity:", self.max_dynamic_combo)
        
        # Disposition (optional)
        self.disposition_combo = QComboBox()
        self.disposition_combo.addItems(["Any", "Dom", "Sub", "Switch"])
        form_layout.addRow("Required Disposition:", self.disposition_combo)

        # Checkboxes for Scope (Scrollable)
        scope_area = QScrollArea()
        scope_widget = QWidget()
        self.scope_layout = QVBoxLayout(scope_widget)
        
        self.concept_checks = {}
        self.orientation_checks = {}
        
        scope_widget.setLayout(self.scope_layout)
        scope_area.setWidget(scope_widget)
        scope_area.setWidgetResizable(True)
        scope_area.setFixedHeight(200)
        neg_layout.addWidget(scope_area)
        
        neg_layout.addWidget(neg_group)
        
        # Result / Actions
        self.salary_preview_label = QLabel("Weekly Salary: Calculating...")
        self.salary_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        neg_layout.addWidget(self.salary_preview_label)
        
        btn_row = QHBoxLayout()
        self.cancel_neg_button = QPushButton("Cancel")
        self.sign_contract_button = QPushButton("Sign Contract")
        btn_row.addWidget(self.cancel_neg_button)
        btn_row.addWidget(self.sign_contract_button)
        neg_layout.addLayout(btn_row)
        
        self.main_stack.addWidget(self.negotiation_page)
        
        main_layout.addWidget(self.main_stack)

    def _wrap_slider(self, slider, label):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(slider)
        l.addWidget(label)
        return w

    def _connect_signals(self):
        self.available_roles_list.itemSelectionChanged.connect(self._request_cost_preview)
        self.available_roles_list.itemSelectionChanged.connect(self._update_ui_state)
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        self.available_roles_list.customContextMenuRequested.connect(self._show_role_context_menu)
        self.hire_button.clicked.connect(self._confirm_hire)
        self.sponsor_tour_button.clicked.connect(self._on_sponsor_tour_clicked)

        # Contract flow
        self.negotiate_button.clicked.connect(self._on_negotiate_clicked)
        self.cancel_neg_button.clicked.connect(lambda: self.main_stack.setCurrentIndex(0))
        self.sign_contract_button.clicked.connect(self._on_sign_contract_clicked)
        
        # Auto-update preview on any change
        self.duration_slider.valueChanged.connect(self._request_contract_preview)
        self.max_scenes_spin.valueChanged.connect(self._request_contract_preview)
        self.max_dynamic_combo.currentIndexChanged.connect(self._request_contract_preview)
        self.disposition_combo.currentIndexChanged.connect(self._request_contract_preview)

    def set_theme_colors(self, danger_color: str):
        """Receives theme colors to style list items dynamically."""
        self._danger_color = QColor(danger_color)

    def _on_negotiate_clicked(self):
        """Switch to negotiation view and trigger an immediate calculation."""
        self.main_stack.setCurrentIndex(1)
        self._request_contract_preview()

    def populate_contract_options(self, concepts: list, orientations: list):
        """Populates the checkboxes dynamically."""
        # Clear old
        while self.scope_layout.count():
            item = self.scope_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.concept_checks = {}
        self.orientation_checks = {}
        
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Concepts Column
        concepts_col = QVBoxLayout()
        concepts_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        concepts_col.addWidget(QLabel("<b>Allowed Concepts:</b>"))
        for c in concepts:
            chk = QCheckBox(c)
            chk.setChecked(True)
            chk.stateChanged.connect(self._request_contract_preview)
            concepts_col.addWidget(chk)
            self.concept_checks[c] = chk

        container_layout.addLayout(concepts_col)
            
        # Orientations Column
        orient_col = QVBoxLayout()
        orient_col.setAlignment(Qt.AlignmentFlag.AlignTop)
        orient_col.addWidget(QLabel("<b>Allowed Orientations:</b>"))
        for o in orientations:
            chk = QCheckBox(o)
            chk.setChecked(True)
            chk.stateChanged.connect(self._request_contract_preview)
            orient_col.addWidget(chk)
            self.orientation_checks[o] = chk
        container_layout.addLayout(orient_col)
            
        self.scope_layout.addWidget(container)

    def update_available_roles(self, available_roles: list, talent_base_location: str, studio_location: str, is_contracted: bool):
        self.available_roles_list.clear()
        self._current_talent_base_location = talent_base_location
        self._current_studio_location = studio_location
        self._is_contracted = is_contracted

        # Handle Contract State
        if is_contracted:
            self.negotiate_button.setEnabled(False)
            self.negotiate_button.setText("Exclusive Contract Active")
            self.main_stack.setCurrentIndex(0) # Force back to list view
        else:
            self.negotiate_button.setEnabled(True)
            self.negotiate_button.setText("Offer Exclusive Contract")

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
                if self._is_contracted and total_cost == 0:
                    cost_text = "<b>Cost: $0 (Contract)</b>"
                else:
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
            self._update_cost_label("Select role(s) to see total cost.", status="neutral")
            self._current_cost_breakdown = None
            return
            
        self.total_cost_label.setText("<i>Calculating...</i>")
        roles_data = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        self.preview_cost_requested.emit(roles_data)

    def update_cost_preview(self, cost_breakdown: dict):
        """Public slot for the Presenter to update the UI with calculated costs."""
        if not cost_breakdown:
            self._update_cost_label("Error calculating cost.", status="error")
            self._current_cost_breakdown = None
            self.hire_button.setEnabled(False)
            return

        self._current_cost_breakdown = cost_breakdown

        # Handle invalid roles (Validation Feedback)
        invalid_roles = cost_breakdown.get('invalid_roles', [])
        
        # Reset visual state of all items first
        for index in range(self.available_roles_list.count()):
            item = self.available_roles_list.item(index)
            item.setForeground(Qt.GlobalColor.black) # Or default theme color
            
        if invalid_roles:
            self.hire_button.setEnabled(False)
            reasons = set(r['error_reason'] for r in invalid_roles)
            reason_text = "; ".join(reasons)
            self._update_cost_label(f"Cannot Hire: {reason_text}", status="error")
            
            # Mark specific items in red
            invalid_keys = set((r['scene_id'], r['virtual_performer_id']) for r in invalid_roles)
            for index in range(self.available_roles_list.count()):
                item = self.available_roles_list.item(index)
                data = item.data(Qt.ItemDataRole.UserRole)
                if (data['scene_id'], data['virtual_performer_id']) in invalid_keys:
                    item.setForeground(self._danger_color)
            return

        total_upfront_cost = cost_breakdown.get('total_upfront_cost', 0)
        roles_with_salaries = cost_breakdown.get('roles_with_final_salaries', [])
        total_deferred_cost = sum(role['final_salary'] for role in roles_with_salaries)

        grand_total = total_upfront_cost + total_deferred_cost
        
        self.hire_button.setEnabled(True)
        self._update_cost_label(
            f"Total: ${int(grand_total):,} (Upfront: ${int(total_upfront_cost):,}, On Shoot: ${int(total_deferred_cost):,})",
            status="neutral"
        )

    def _update_cost_label(self, text: str, status: str):
        """Updates text and forces a style refresh based on status property."""
        self.total_cost_label.setText(text)
        self.total_cost_label.setProperty("status", status)
        self.total_cost_label.style().unpolish(self.total_cost_label)
        self.total_cost_label.style().polish(self.total_cost_label)

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

    def _get_contract_terms(self) -> dict:
        allowed_concepts = [c for c, chk in self.concept_checks.items() if chk.isChecked()]
        allowed_orientations = [o for o, chk in self.orientation_checks.items() if chk.isChecked()]
        
        return {
            'duration_weeks': self.duration_slider.value(),
            'max_scenes_per_week': self.max_scenes_spin.value(),
            'max_dynamic': self.max_dynamic_combo.currentIndex(),
            'disposition': self.disposition_combo.currentText() if self.disposition_combo.currentIndex() > 0 else None,
            'allowed_concepts': allowed_concepts,
            'allowed_orientations': allowed_orientations
        }

    def _request_contract_preview(self):
        if self.main_stack.currentIndex() != 1: return
        terms = self._get_contract_terms()
        self.contract_preview_requested.emit(terms)

    def update_contract_preview(self, salary: int):
        self.salary_preview_label.setText(f"Weekly Salary: <b>${salary:,}</b>")

    def _on_sign_contract_clicked(self):
        terms = self._get_contract_terms()
        if not terms['allowed_concepts'] and not terms['allowed_orientations']:
             QMessageBox.warning(self, "Invalid Contract", "You must select at least one concept or orientation.")
             return
             
        self.contract_sign_requested.emit(terms)