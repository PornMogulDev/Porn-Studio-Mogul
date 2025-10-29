from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QDialogButtonBox, 
    QFormLayout, QWidget, QTabWidget, QRadioButton, QButtonGroup, 
    QPushButton, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer
from data.game_state import Scene
from utils.scene_summary_builder import prepare_summary_data
from ui.widgets.scene_summary_widget import SceneSummaryWidget
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class ShotSceneDetailsDialog(GeometryManagerMixin, QDialog):
    def __init__(self, scene: Scene, controller, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.controller = controller
        self.settings_manager = self.controller.settings_manager

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.setWindowTitle(f"Details: {self.scene.title}")
        self.defaultSize = QSize(750, 800)
        
        self.editing_option_group = QButtonGroup()
        
        self.setup_ui()
        self._restore_geometry()

        QTimer.singleShot(0, self.populate_data)

        # Connect to the signal to refresh data if the scene changes while open
        self.controller.signals.scenes_changed.connect(self._on_scene_changed)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Main Tab Widget ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- Tab 1: Financial & Market ---
        financial_tab = QWidget()
        financial_layout = QVBoxLayout(financial_tab)
        
        financial_group = QGroupBox("Financial Summary")
        financial_group_layout = QVBoxLayout(financial_group)
        self.expenses_label = QLabel()
        self.expenses_label.setWordWrap(True)
        self.revenue_label = QLabel()
        self.revenue_label.setWordWrap(True)
        self.profit_label = QLabel()
        financial_group_layout.addWidget(self.expenses_label)
        financial_group_layout.addWidget(self.revenue_label)
        financial_group_layout.addWidget(self.profit_label)
        financial_layout.addWidget(financial_group)
        
        market_group = QGroupBox("Market Interest")
        market_layout = QVBoxLayout(market_group)
        self.market_interest_label = QLabel()
        self.market_interest_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        market_layout.addWidget(self.market_interest_label)
        financial_layout.addWidget(market_group)
        
        self.tabs.addTab(financial_tab, "Financials")
        
        # --- Tab 2: Design Summary ---
        self.summary_widget = SceneSummaryWidget(self)
        self.tabs.addTab(self.summary_widget, "Design Summary")

        # --- Tab 3: Post-Production (will be created dynamically) ---
        self.post_prod_tab_index = -1

        # --- Dialog Button Box ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def populate_data(self):
        """Populates all UI elements with data from the current self.scene object."""
        theme = self.controller.get_current_theme()

        # --- Financial Summary ---
        salary_expenses = sum(self.scene.pps_salaries.values())
        bloc_cost_share = 0
        editing_cost = 0

        # 1. Bloc production costs
        if self.scene.bloc_id:
            bloc = self.controller.get_bloc_by_id(self.scene.bloc_id)
            if bloc and len(bloc.scenes) > 0:
                bloc_cost_share = bloc.production_cost / len(bloc.scenes)

        # 2. Editing cost
        if editing_tier_id := (self.scene.post_production_choices or {}).get('editing_tier'):
            editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
            tier_data = next((t for t in editing_tiers if t['id'] == editing_tier_id), None)
            if tier_data:
                editing_cost = tier_data.get('cost', 0)
        
        total_expenses = int(salary_expenses + bloc_cost_share + editing_cost)
        
        # Build Expenses HTML
        expenses_html = "<h4>Expenses</h4>"
        if bloc_cost_share > 0:
            expenses_html += f"Bloc Production Share: <font color='{theme.color_bad}'>-${int(bloc_cost_share):,}</font><br>"
        if editing_cost > 0:
            expenses_html += f"Post-Production: <font color='{theme.color_bad}'>-${editing_cost:,}</font><br>"
        
        expenses_html += "Talent Salaries:<br>"
        for vp_id, talent_id in self.scene.final_cast.items():
            talent = self.controller.talent_service.get_talent_by_id(talent_id)
            salary = self.scene.pps_salaries.get(str(talent_id), 0)
            if talent:
                expenses_html += f"&nbsp;&nbsp;• {talent.alias}: <font color='{theme.color_bad}'>-${salary:,}</font><br>"
        
        expenses_html += f"<br><b>Total Expenses: <font color='{theme.color_bad}'>-${total_expenses:,}</font></b>"
        self.expenses_label.setText(expenses_html)
        
        # Build Revenue & Profit HTML
        revenue_html = "<h4>Revenue</h4>"
        if self.scene.status == 'released':
            revenue = self.scene.revenue
            profit = revenue - total_expenses
            
            # This is a simplified per-group revenue estimate for display purposes
            for group, interest in self.scene.viewer_group_interest.items():
                group_revenue = self._calculate_revenue_for_group(group)
                revenue_html += f"&nbsp;&nbsp;• {group}: <font color='{theme.color_good}'>+${group_revenue:,}</font><br>"

            revenue_html += f"<br><b>Total Revenue: <font color='{theme.color_good}'>+${revenue:,}</font></b>"
            
            profit_color = theme.color_good if profit >= 0 else theme.color_bad
            profit_text = f"<h4>Profit</h4><b><font color='{profit_color}'>${profit:,}</font></b>"
        else:
            revenue_html += "<i>Scene not yet released.</i>"
            profit_text = f"<h4>Profit</h4><b><font color='{theme.color_bad}'>(${-total_expenses:,})</font></b>"

        self.revenue_label.setText(revenue_html)
        self.profit_label.setText(profit_text)

        # --- Market Interest ---
        market_interest_lines = []
        for group, interest in sorted(self.scene.viewer_group_interest.items()):
            color = theme.color_good if interest > 1.0 else theme.color_bad if interest < 1.0 else theme.text
            line = f"{group}: <font color='{color}'>{interest:.2f}</font>"
            market_interest_lines.append(line)
        self.market_interest_label.setText("<br>".join(market_interest_lines) or "N/A")

        # --- Design Summary Tab ---
        summary_data = prepare_summary_data(self.scene, self.controller)
        self.summary_widget.update_summary(summary_data)
        
        # --- Dynamic Post-Production Tab ---
        self._setup_post_production_tab()
    
    def _calculate_revenue_for_group(self, group_name: str) -> int:
        """A simplified estimate of a single group's revenue contribution for display."""
        if not self.scene.revenue or not self.scene.viewer_group_interest:
            return 0
        
        # This approximates revenue share based on interest scores, which is close enough for a UI report.
        total_interest_score = sum(self.scene.viewer_group_interest.values())
        group_interest_score = self.scene.viewer_group_interest.get(group_name, 0)
        
        if total_interest_score == 0:
            return 0
            
        return int(self.scene.revenue * (group_interest_score / total_interest_score))

    def _setup_post_production_tab(self):
        """Creates or updates the post-production tab based on scene status."""
        # If the tab exists, remove it before rebuilding to ensure it's fresh
        if self.post_prod_tab_index != -1:
            self.tabs.removeTab(self.post_prod_tab_index)
            self.post_prod_tab_index = -1
            self.post_prod_tab = None 

        if self.scene.status != 'shot':
            return

        self.post_prod_tab = QWidget()
        layout = QVBoxLayout(self.post_prod_tab)
        options_widget = self._create_editing_options_widget()
        layout.addWidget(options_widget)

        self.post_prod_tab_index = self.tabs.addTab(self.post_prod_tab, "Post-Production")
            
    def _create_editing_options_widget(self) -> QWidget:
        """Creates the widget with radio buttons for editing choices."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        options_group = QGroupBox("Editing Options")
        options_layout = QFormLayout(options_group)
        
        editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
        camera_setup_tier = "1"
        if self.scene.bloc_id and (bloc := self.controller.get_bloc_by_id(self.scene.bloc_id)):
            camera_setup_tier = bloc.production_settings.get('Camera Setup', '1')

        self.editing_option_group = QButtonGroup(self)
        for i, tier in enumerate(editing_tiers):
            base_mod = tier.get('base_quality_modifier', 1.0)
            synergy_mod = tier.get('synergy_mods', {}).get(camera_setup_tier, 0.0)
            final_mod = base_mod + synergy_mod

            radio_button = QRadioButton(tier['name'])
            radio_button.setProperty("tier_id", tier['id'])
            radio_button.setToolTip(tier['description'])
            if i == 0: radio_button.setChecked(True)

            self.editing_option_group.addButton(radio_button)

            theme = self.controller.get_current_theme()
            info_text = (f"Cost: <font color='{theme.color_bad}'>${tier['cost']:,}</font> | "
                         f"Time: {tier['weeks']}w | "
                         f"Quality Mod: <b>{final_mod:.2f}x</b>")
            options_layout.addRow(radio_button, QLabel(info_text))
        
        layout.addWidget(options_group)
        layout.addStretch()

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        start_editing_btn = QPushButton("Start Editing")
        start_editing_btn.clicked.connect(self._start_editing)
        bottom_layout.addWidget(start_editing_btn)
        layout.addLayout(bottom_layout)
        return widget

    def _start_editing(self):
        """Handler for the 'Start Editing' button click."""
        checked_button = self.editing_option_group.checkedButton()
        if not checked_button:
            return
            
        tier_id = checked_button.property("tier_id")
    
        self.controller.start_editing_scene(self.scene.id, tier_id)

    def _on_scene_changed(self):
        """Slot to refresh the dialog's data when any scene changes."""
        # A more complex app might get a list of changed IDs from the signal.
        # For now, we just re-fetch the data for our scene ID.
        fresh_scene = self.controller.get_scene_for_planner(self.scene.id)
        if fresh_scene:
            self.scene = fresh_scene
            self.populate_data() # This re-runs all the display logic
        else:
            # The scene was likely deleted, close the dialog.
            self.reject()