from collections import defaultdict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QStackedWidget, QLabel, QListWidget,
    QPushButton, QMenu, QMessageBox, QListWidgetItem
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal

class HiringWidget(QWidget):
    """A widget for assigning a talent to available roles."""
    hire_confirmed = pyqtSignal(list)  # roles_to_cast
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._bulk_discount_tiers = {}

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
        
        self.hire_button = QPushButton("Assign Talent to Selected Role(s)")
        contract_layout.addWidget(self.hire_button)

        self.total_cost_label = QLabel("Select role(s) to see total cost.")
        self.total_cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_cost_label.setObjectName("SubtleText") # For styling
        contract_layout.addWidget(self.total_cost_label)
        
        main_layout.addWidget(contract_container)

    def _connect_signals(self):
        self.available_roles_list.itemSelectionChanged.connect(self._update_total_cost_preview)
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        self.available_roles_list.customContextMenuRequested.connect(self._show_role_context_menu)
        self.hire_button.clicked.connect(self._confirm_hire)

    def update_available_roles(self, available_roles: list):
        self.available_roles_list.clear()

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
        self._update_total_cost_preview()

    def set_discount_tiers(self, tiers: dict):
        """Receives the discount configuration from the presenter."""
        self._bulk_discount_tiers = tiers

    def _update_total_cost_preview(self):
        """Calculates and displays the total cost preview for selected roles."""
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items:
            self.total_cost_label.setText("Select role(s) to see total cost.")
            return

        bloc_groups = defaultdict(list)
        for item in selected_items:
            role_data = item.data(Qt.ItemDataRole.UserRole)
            bloc_id = role_data.get('bloc_id') if role_data.get('bloc_id') is not None else f"nobloc_{role_data['scene_id']}"
            bloc_groups[bloc_id].append(role_data)
        
        total_upfront_cost = 0
        total_deferred_cost = 0

        for bloc_id, roles in bloc_groups.items():
            num_roles = len(roles)
            discount_multiplier = self._bulk_discount_tiers.get(num_roles, 1.0)
            
            bloc_base_subtotal = sum(r.get('base_cost', 0) for r in roles)
            bloc_rush_subtotal = sum(r.get('rush_fee', 0) for r in roles)
            bloc_travel_subtotal = sum(r.get('travel_fee', 0) for r in roles)
            
            # Apply discount multiplier only to the base salary portion
            discounted_base_cost = bloc_base_subtotal * discount_multiplier
            
            total_upfront_cost += bloc_travel_subtotal
            total_deferred_cost += (discounted_base_cost + bloc_rush_subtotal)
            
        grand_total = total_upfront_cost + total_deferred_cost
        
        self.total_cost_label.setText(f"<b>Total:</b> ${int(grand_total):,} (Upfront: ${int(total_upfront_cost):,}, On Shoot: ${int(total_deferred_cost):,})")

    def _on_role_double_clicked(self, item: QListWidgetItem):
        if role_data := item.data(Qt.ItemDataRole.UserRole):
            self.open_scene_dialog_requested.emit(role_data['scene_id'])

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
        
        roles_to_cast, scene_ids = [], set()
        for item in selected_items:
            role_data = item.data(Qt.ItemDataRole.UserRole)
            if role_data['scene_id'] in scene_ids:
                QMessageBox.warning(self, "Casting Error", "Cannot cast for multiple roles in the same scene.\nA talent can only be cast once per scene.")
                return
            scene_ids.add(role_data['scene_id'])
            # We only need to pass a subset of the data to the controller
            roles_to_cast.append({
                'scene_id': role_data['scene_id'], 
                'virtual_performer_id': role_data['virtual_performer_id']
            })
        self.hire_confirmed.emit(roles_to_cast)