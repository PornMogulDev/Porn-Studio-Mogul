from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QStackedWidget, QLabel, QListWidget,
    QPushButton, QHBoxLayout, QListWidgetItem, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class StandardHiringPage(QWidget):
    preview_cost_requested = pyqtSignal(list)
    hire_confirmed = pyqtSignal(dict)  # {'roles': [...], 'upfront_cost': X}
    sponsor_tour_clicked = pyqtSignal(list) # list of role dicts
    negotiate_contract_clicked = pyqtSignal()
    open_scene_dialog_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._danger_color = QColor("red")
        self._current_cost_breakdown = None
        self._current_talent_base_location = ""
        self._current_studio_location = ""
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        contract_container = QGroupBox("Assign to Role")
        contract_layout = QVBoxLayout(contract_container)
        
        self.roles_stack = QStackedWidget()
        
        # List View
        roles_list_widget = QWidget()
        roles_list_layout = QVBoxLayout(roles_list_widget)
        roles_list_layout.addWidget(QLabel("Available Roles (from scenes in 'casting'):"))
        self.available_roles_list = QListWidget()
        self.available_roles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_roles_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        roles_list_layout.addWidget(self.available_roles_list)
        self.roles_stack.addWidget(roles_list_widget)
        
        # Empty State
        roles_no_scenes_widget = QLabel("There are no uncast roles available for this talent.")
        roles_no_scenes_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roles_no_scenes_widget.setWordWrap(True)
        self.roles_stack.addWidget(roles_no_scenes_widget)
        
        contract_layout.addWidget(self.roles_stack)

        # Buttons
        self.negotiate_button = QPushButton("Offer Exclusive Contract")
        contract_layout.addWidget(self.negotiate_button)

        button_layout = QHBoxLayout()
        self.hire_button = QPushButton("Assign Talent to Selected Role(s)")
        self.sponsor_tour_button = QPushButton("Sponsor Tour...")
        self.sponsor_tour_button.setToolTip("Select multiple non-local roles (1-4 weeks duration) to enable.")
        self.sponsor_tour_button.setEnabled(False)
        
        button_layout.addWidget(self.hire_button)
        button_layout.addWidget(self.sponsor_tour_button)
        contract_layout.addLayout(button_layout)

        self.total_cost_label = QLabel("Select role(s) to see total cost.")
        self.total_cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_cost_label.setObjectName("totalCostLabel")
        contract_layout.addWidget(self.total_cost_label)
        
        layout.addWidget(contract_container)

    def _connect_signals(self):
        self.available_roles_list.itemSelectionChanged.connect(self._request_cost_preview)
        self.available_roles_list.itemSelectionChanged.connect(self._update_ui_state)
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        self.available_roles_list.customContextMenuRequested.connect(self._show_role_context_menu)
        
        self.hire_button.clicked.connect(self._confirm_hire)
        self.sponsor_tour_button.clicked.connect(self._on_sponsor_tour_clicked)
        self.negotiate_button.clicked.connect(self.negotiate_contract_clicked.emit)

    def set_theme_colors(self, danger_color: QColor):
        self._danger_color = danger_color

    def update_available_roles(self, available_roles: list, talent_base: str, studio_loc: str, is_contracted: bool):
        self.available_roles_list.clear()
        self._current_talent_base_location = talent_base
        self._current_studio_location = studio_loc
        
        if is_contracted:
            self.negotiate_button.setEnabled(False)
            self.negotiate_button.setText("Exclusive Contract Active")
        else:
            self.negotiate_button.setEnabled(True)
            self.negotiate_button.setText("Offer Exclusive Contract")

        if not available_roles:
            self.roles_stack.setCurrentIndex(1)
            return

        self.roles_stack.setCurrentIndex(0)
        for role_data in available_roles:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, role_data)
            item.setToolTip(role_data.get('tooltip_html', ''))

            if role_data['is_available']:
                total_cost = role_data.get('cost', 0)
                if is_contracted and total_cost == 0:
                    cost_text = "<b>Cost: $0 (Contract)</b>"
                else:
                    base = role_data.get('base_cost', total_cost)
                    travel = role_data.get('travel_fee', 0)
                    rush = role_data.get('rush_fee', 0)
                    parts = [f"Base: ${base:,}"]
                    if travel > 0: parts.append(f"Travel: ${travel:,}")
                    if rush > 0: parts.append(f"Rush: ${rush:,}")
                    cost_text = f"Cost: ${total_cost:,} ({', '.join(parts)})"
                
                item.setText(f"{role_data['scene_title']} - Role: {role_data['vp_name']} ({cost_text})")
            else:
                reason = role_data.get('refusal_reason', 'Unknown')
                item.setText(f"{role_data['scene_title']} - Role: {role_data['vp_name']} (Unavailable: {reason})")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            
            self.available_roles_list.addItem(item)
        
        self._update_ui_state()

    def update_cost_preview(self, cost_breakdown: dict):
        self._current_cost_breakdown = cost_breakdown
        if not cost_breakdown:
            self._update_cost_label("Error calculating cost.", "error")
            self.hire_button.setEnabled(False)
            return

        # Reset colors
        for i in range(self.available_roles_list.count()):
            self.available_roles_list.item(i).setForeground(Qt.GlobalColor.black)

        invalid_roles = cost_breakdown.get('invalid_roles', [])
        if invalid_roles:
            self.hire_button.setEnabled(False)
            reasons = set(r['error_reason'] for r in invalid_roles)
            self._update_cost_label(f"Cannot Hire: {'; '.join(reasons)}", "error")
            
            invalid_keys = set((r['scene_id'], r['virtual_performer_id']) for r in invalid_roles)
            for i in range(self.available_roles_list.count()):
                item = self.available_roles_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                if (data['scene_id'], data['virtual_performer_id']) in invalid_keys:
                    item.setForeground(self._danger_color)
            return

        upfront = cost_breakdown.get('total_upfront_cost', 0)
        deferred = sum(r['final_salary'] for r in cost_breakdown.get('roles_with_final_salaries', []))
        total = upfront + deferred
        
        self.hire_button.setEnabled(True)
        self._update_cost_label(
            f"Total: ${int(total):,} (Upfront: ${int(upfront):,}, On Shoot: ${int(deferred):,})", 
            "neutral"
        )

    def _update_cost_label(self, text, status):
        self.total_cost_label.setText(text)
        self.total_cost_label.setProperty("status", status)
        self.total_cost_label.style().unpolish(self.total_cost_label)
        self.total_cost_label.style().polish(self.total_cost_label)

    def _request_cost_preview(self):
        selected = self.available_roles_list.selectedItems()
        if not selected:
            self.hire_button.setEnabled(False)
            self._update_cost_label("Select role(s) to see total cost.", "neutral")
            self._current_cost_breakdown = None
            return
        
        self.total_cost_label.setText("<i>Calculating...</i>")
        roles_data = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
        self.preview_cost_requested.emit(roles_data)

    def _update_ui_state(self):
        self._request_cost_preview()
        # Update Sponsor Tour Button
        selected = self.available_roles_list.selectedItems()
        if len(selected) < 2 or self._current_talent_base_location == self._current_studio_location:
            self.sponsor_tour_button.setEnabled(False)
            return

        roles_data = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
        role_dates = [(r['scheduled_year'] * 52 + r['scheduled_week']) for r in roles_data]
        duration = max(role_dates) - min(role_dates) + 1
        
        self.sponsor_tour_button.setEnabled(1 <= duration <= 4)

    def _on_sponsor_tour_clicked(self):
        selected = self.available_roles_list.selectedItems()
        if not selected: return
        roles = [{
            'scene_id': i.data(Qt.ItemDataRole.UserRole)['scene_id'],
            'virtual_performer_id': i.data(Qt.ItemDataRole.UserRole)['virtual_performer_id']
        } for i in selected]
        self.sponsor_tour_clicked.emit(roles)

    def _confirm_hire(self):
        if not self.available_roles_list.selectedItems():
            QMessageBox.warning(self, "No Roles", "Please select roles.")
            return
        if not self._current_cost_breakdown:
            QMessageBox.critical(self, "Error", "Cost not calculated.")
            return
        
        roles_list = self._current_cost_breakdown.get('roles_with_final_salaries', [])
        if len(roles_list) != len(set(r['scene_id'] for r in roles_list)):
            QMessageBox.warning(self, "Error", "Talent can only be cast once per scene.")
            return
            
        self.hire_confirmed.emit({
            'upfront_cost': self._current_cost_breakdown.get('total_upfront_cost', 0),
            'roles': roles_list
        })

    def _on_role_double_clicked(self, item):
        if data := item.data(Qt.ItemDataRole.UserRole):
            self.open_scene_dialog_requested.emit(data['scene_id'])

    def _show_role_context_menu(self, pos):
        item = self.available_roles_list.itemAt(pos)
        if not item: return
        if data := item.data(Qt.ItemDataRole.UserRole):
            menu = QMenu(self)
            action = menu.addAction("View Scene")
            if menu.exec(self.available_roles_list.viewport().mapToGlobal(pos)) == action:
                self.open_scene_dialog_requested.emit(data['scene_id'])