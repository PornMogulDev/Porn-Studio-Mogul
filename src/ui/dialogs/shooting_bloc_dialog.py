from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QSpinBox, QComboBox, QDialogButtonBox, QWidget, QLineEdit, QCheckBox
)
from PyQt6.QtGui import QFont

from data.settings_manager import SettingsManager
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class ShootingBlocDialog(GeometryManagerMixin, QDialog):
    def __init__(self, controller, settings_manager: SettingsManager, parent: QWidget = None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = settings_manager
        self.prod_settings_data = self.controller.data_manager.production_settings_data
        self.policies_data = self.controller.data_manager.on_set_policies_data
        
        self.setWindowTitle("Plan New Shooting Bloc")
        self.setMinimumSize(300,800)
        
        # UI element storage
        self.prod_setting_combos = {} # Key: category, Value: QComboBox
        self.policy_checkboxes = {} # Key: policy_id, Value: QCheckBox

        self.setup_ui()
        self._connect_signals()
        
        self.set_default_schedule()
        self._load_and_apply_defaults()
        self._update_total_cost()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Scheduling Group ---
        scheduling_group = QGroupBox("Scheduling & Details")
        form_layout = QFormLayout(scheduling_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., '2024 W25 Shoot'")
        
        self.num_scenes_spinbox = QSpinBox()
        self.num_scenes_spinbox.setRange(1, 4)
        
        self.week_spinbox = QSpinBox()
        self.year_spinbox = QSpinBox()

        form_layout.addRow("Bloc Name (Optional):", self.name_edit)
        form_layout.addRow("Number of Scenes:", self.num_scenes_spinbox)
        form_layout.addRow("Scheduled Week:", self.week_spinbox)
        form_layout.addRow("Scheduled Year:", self.year_spinbox)
        main_layout.addWidget(scheduling_group)

        # --- Production Settings Group ---
        prod_group = QGroupBox("Production Settings")
        prod_form_layout = QFormLayout(prod_group)
        
        for category, tiers in sorted(self.prod_settings_data.items()):
            combo = QComboBox()
            for tier in tiers:
                if tier.get('cost_per_scene') is not None:
                    display_text = f"{tier['tier_name']} (+${tier['cost_per_scene']:,}/scene)"
                elif tier.get('cost_multiplier') is not None:
                    display_text = f"{tier['tier_name']} (x{tier['cost_multiplier']} equipment cost)"
                else:
                    display_text = tier['tier_name']

                combo.addItem(display_text, tier)
            
            self.prod_setting_combos[category] = combo
            prod_form_layout.addRow(f"{category.replace('_', ' ').title()}:", combo)
        main_layout.addWidget(prod_group)

        # --- On-Set Policies Group ---
        policies_group = QGroupBox("On-Set Policies")
        policies_layout = QVBoxLayout(policies_group)

        for policy_id, policy_data in sorted(self.policies_data.items(), key=lambda item: item[1]['name']):
            checkbox = QCheckBox(policy_data['name'])
            tooltip = f"{policy_data['description']}"
            if (cost := policy_data.get('cost_per_bloc', 0)) > 0:
                tooltip += f"\n\nCost: +${cost:,} (per bloc)"
            
            checkbox.setToolTip(tooltip)
            self.policy_checkboxes[policy_id] = checkbox
            policies_layout.addWidget(checkbox)
        main_layout.addWidget(policies_group)


        # --- Cost and Buttons ---
        cost_layout = QHBoxLayout()
        cost_layout.addWidget(QLabel("<b>Total Production Cost:</b>"))
        self.total_cost_label = QLabel("$0")
        font = self.total_cost_label.font()
        font.setPointSize(12)
        font.setBold(True)
        self.total_cost_label.setFont(font)
        cost_layout.addStretch()
        cost_layout.addWidget(self.total_cost_label)
        main_layout.addLayout(cost_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Plan Bloc")
        main_layout.addWidget(self.button_box)

    def _connect_signals(self):
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        self.num_scenes_spinbox.valueChanged.connect(self._update_total_cost)
        
        for combo in self.prod_setting_combos.values():
            combo.currentIndexChanged.connect(self._update_total_cost)
            combo.currentIndexChanged.connect(lambda state, c=combo: self._update_tooltip(c))
        
        for checkbox in self.policy_checkboxes.values():
            checkbox.stateChanged.connect(self._update_total_cost)

    def set_default_schedule(self):
        current_year = self.controller.game_state.year
        current_week = self.controller.game_state.week
        
        self.week_spinbox.setRange(1, 52)
        self.year_spinbox.setRange(current_year, current_year + 10)
        
        self.week_spinbox.setValue(current_week)
        self.year_spinbox.setValue(current_year)

    def set_schedule(self, week: int, year: int):
        self.week_spinbox.setValue(week)
        self.year_spinbox.setValue(year)

    def _load_and_apply_defaults(self):
        last_settings = self.settings_manager.get_setting("last_shooting_bloc_settings", {})
        if not last_settings:
            return

        saved_prod_settings = last_settings.get("production_settings", {})
        for category, tier_name in saved_prod_settings.items():
            if combo := self.prod_setting_combos.get(category):
                for i in range(combo.count()):
                    tier_data = combo.itemData(i)
                    if tier_data and tier_data['tier_name'] == tier_name:
                        combo.setCurrentIndex(i)
                        break

        saved_policies = last_settings.get("policies", [])
        for policy_id, checkbox in self.policy_checkboxes.items():
            checkbox.setChecked(policy_id in saved_policies)

    def _update_total_cost(self):
        num_scenes = self.num_scenes_spinbox.value()
        cost_per_scene = 0

        cam_equip_combo = self.prod_setting_combos.get("Camera Equipment")
        cam_setup_combo = self.prod_setting_combos.get("Camera Setup")
        
        equip_cost = 0
        if cam_equip_combo and (data := cam_equip_combo.currentData()):
            equip_cost = data.get('cost_per_scene', 0)
            
        setup_multiplier = 1
        if cam_setup_combo and (data := cam_setup_combo.currentData()):
            setup_multiplier = data.get('cost_multiplier', 1)

        cost_per_scene += equip_cost * setup_multiplier

        for category, combo in self.prod_setting_combos.items():
            if category in ["Camera Equipment", "Camera Setup"]:
                continue
            
            if tier_data := combo.currentData():
                cost_per_scene += tier_data.get('cost_per_scene', 0)

        settings_cost = cost_per_scene * num_scenes
        
        policies_cost = 0
        for policy_id, checkbox in self.policy_checkboxes.items():
            if checkbox.isChecked():
                if policy_data := self.policies_data.get(policy_id):
                    policies_cost += policy_data.get('cost_per_bloc', 0)
        
        total_cost = settings_cost + policies_cost
        self.total_cost_label.setText(f"${total_cost:,}")
        
        for combo in self.prod_setting_combos.values():
            self._update_tooltip(combo)

    def _update_tooltip(self, combo_box: QComboBox):
        tier_data = combo_box.currentData()
        if tier_data and (desc := tier_data.get('description')):
            combo_box.setToolTip(desc)

    def accept(self):
        saved_prod_settings = {}
        for category, combo in self.prod_setting_combos.items():
            if tier_data := combo.currentData():
                saved_prod_settings[category] = tier_data['tier_name']
        
        saved_policies = [
            policy_id for policy_id, checkbox in self.policy_checkboxes.items() 
            if checkbox.isChecked()
        ]
        
        settings_to_save = {
            "production_settings": saved_prod_settings,
            "policies": saved_policies
        }
        self.settings_manager.set_setting("last_shooting_bloc_settings", settings_to_save)
        
        week = self.week_spinbox.value()
        year = self.year_spinbox.value()
        num_scenes = self.num_scenes_spinbox.value()
        name = self.name_edit.text()
        
        settings = {}
        for category, combo in self.prod_setting_combos.items():
            if tier_data := combo.currentData():
                settings[category] = tier_data['tier_name']

        selected_policies = [policy_id for policy_id, checkbox in self.policy_checkboxes.items() if checkbox.isChecked()]
        
        if self.controller.create_shooting_bloc(week, year, num_scenes, settings, name, selected_policies):
            super().accept()