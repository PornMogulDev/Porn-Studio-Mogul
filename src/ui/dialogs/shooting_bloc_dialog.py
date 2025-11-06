from typing import Dict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QSpinBox, QComboBox, QDialogButtonBox, QWidget, QLineEdit, QCheckBox
)
from PyQt6.QtCore import QSize

from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.shooting_bloc_presenter import ShootingBlocPresenter
from ui.widgets.help_button import HelpButton

class ShootingBlocDialog(GeometryManagerMixin, QDialog):
    """
    The View component for planning a new shooting bloc. This class is
    responsible only for displaying UI elements and forwarding user
    interactions to its presenter. It contains no business logic.
    """
    def __init__(self, controller, parent: QWidget = None):
        super().__init__(parent)
        # Note: The controller is passed directly to the presenter. The view does not use it.
        self.prod_settings_data = controller.data_manager.production_settings_data
        self.policies_data = controller.data_manager.on_set_policies_data
        self.settings_manager = controller.settings_manager
        self.presenter = ShootingBlocPresenter(controller, self)
        
        self.setWindowTitle("Plan New Shooting Bloc")
        self.defaultSize = QSize(400, 800)
        self.setMinimumSize(350,750)
        
        # --- UI element storage ---
        self.prod_setting_combos: Dict[str, QComboBox] = {}
        self.policy_checkboxes: Dict[str, QCheckBox] = {}

        # --- Setup Flow ---
        self.setup_ui()
        self._connect_signals()
        
        # Initialize schedule and load defaults via the presenter
        self.set_default_schedule()
        self.presenter.load_initial_data()
        
        self._restore_geometry()

    def setup_ui(self):
        """Creates and arranges all the widgets for the dialog."""
        main_layout = QVBoxLayout(self)
        self.help_btn = HelpButton("shooting_bloc", self)
        main_layout.addWidget(self.help_btn)

        # --- Scheduling Group ---
        scheduling_group = QGroupBox("Scheduling & Details")
        form_layout = QFormLayout(scheduling_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., '2010 W25 Shoot'")
        
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
        """Connects widget signals to presenter methods."""
        # The help button signal is handled by the controller, which is fine.
        self.help_btn.help_requested.connect(self.presenter.controller.signals.show_help_requested)
        
        # The 'accept' action is intercepted and handled by the presenter.
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # Any change in a value that affects cost now notifies the presenter.
        self.num_scenes_spinbox.valueChanged.connect(self.presenter.request_cost_update)
        
        for combo in self.prod_setting_combos.values():
            combo.currentIndexChanged.connect(self.presenter.request_cost_update)
            combo.currentIndexChanged.connect(lambda state, c=combo: self._update_tooltip(c))
        
        for checkbox in self.policy_checkboxes.values():
            checkbox.stateChanged.connect(self.presenter.request_cost_update)

    def accept(self):
        """
        Overrides the default QDialog.accept() behavior. Instead of closing
        the dialog immediately, it delegates the confirmation logic to the
        presenter. The presenter is then responsible for closing the dialog
        (by calling `commit_and_close`) if the action is successful.
        """
        self.presenter.confirm_plan()

    def commit_and_close(self):
        """
        This method is called by the presenter to finalize the dialog's
        'accepted' state and close it.
        """
        super().accept()

    # --- Methods for Presenter Interaction ---

    def get_current_selections(self) -> Dict:
        """
        Gathers the current state of all relevant UI widgets and returns them
        in a dictionary for the presenter to use. This method contains no logic.
        """
        prod_settings = {}
        for category, combo in self.prod_setting_combos.items():
            if tier_data := combo.currentData():
                prod_settings[category] = tier_data['tier_name']

        policies = [
            policy_id for policy_id, checkbox in self.policy_checkboxes.items() 
            if checkbox.isChecked()
        ]

        return {
            "week": self.week_spinbox.value(),
            "year": self.year_spinbox.value(),
            "num_scenes": self.num_scenes_spinbox.value(),
            "name": self.name_edit.text(),
            "production_settings": prod_settings,
            "policies": policies,
        }

    def apply_defaults(self, defaults: Dict):
        """
        Applies a set of default values, provided by the presenter, to the UI widgets.
        This method is "dumb" and simply sets widget states.
        """
        saved_prod_settings = defaults.get("production_settings", {})
        for category, tier_name in saved_prod_settings.items():
            if combo := self.prod_setting_combos.get(category):
                for i in range(combo.count()):
                    tier_data = combo.itemData(i)
                    if tier_data and tier_data['tier_name'] == tier_name:
                        combo.setCurrentIndex(i)
                        break

        saved_policies = defaults.get("policies", [])
        for policy_id, checkbox in self.policy_checkboxes.items():
            checkbox.setChecked(policy_id in saved_policies)
            
    def set_total_cost_display(self, cost: int):
        """Updates the total cost label with a formatted string."""
        self.total_cost_label.setText(f"${cost:,}")

    # --- Standard UI Helper Methods ---
    
    def set_default_schedule(self):
        """Sets the initial date in the spinboxes to the current game date."""
        # This method is simple enough to remain in the view.
        current_year = self.presenter.controller.game_state.year
        current_week = self.presenter.controller.game_state.week
        
        self.week_spinbox.setRange(1, 52)
        self.year_spinbox.setRange(current_year, current_year + 10)
        
        self.week_spinbox.setValue(current_week)
        self.year_spinbox.setValue(current_year)

    def set_schedule(self, week: int, year: int):
        """Allows external callers (like the UIManager) to preset the schedule."""
        self.week_spinbox.setValue(week)
        self.year_spinbox.setValue(year)

    def _update_tooltip(self, combo_box: QComboBox):
        """Updates the tooltip of a combo box based on its current selection."""
        tier_data = combo_box.currentData()
        if tier_data and (desc := tier_data.get('description')):
            combo_box.setToolTip(desc)