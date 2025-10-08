from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QListWidget, 
    QDialogButtonBox, QFormLayout, QTreeView, QSplitter, QWidget, QTabWidget,
    QRadioButton, QButtonGroup, QPushButton
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal
from collections import defaultdict
from game_state import Scene
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class ShotSceneDetailsDialog(GeometryManagerMixin, QDialog):
    def __init__(self, scene: Scene, controller, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        
        self.setWindowTitle(f"Details: {self.scene.title}")
        self.setMinimumSize(850, 700)
        
        # For post-production tab
        self.editing_option_group = QButtonGroup()
        
        self.setup_ui()
        self.populate_data()
        self._restore_geometry()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Top Panel: Permanent Scene Details ---
        details_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Panel (Details) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.financial_group = QGroupBox("Financial Summary")
        self.financial_layout = QFormLayout(self.financial_group)
        left_layout.addWidget(self.financial_group)
        
        quality_group = QGroupBox("Quality Report")
        quality_layout = QVBoxLayout(quality_group)
        self.tag_quality_label = QLabel()
        quality_layout.addWidget(self.tag_quality_label)
        self.tag_qualities_list = QListWidget()
        quality_layout.addWidget(self.tag_qualities_list)
        self.penalties = QLabel("Revenue Modifiers:")
        quality_layout.addWidget(self.penalties)
        left_layout.addWidget(quality_group)
        
        auto_tags_group = QGroupBox("Detected Cast Tags (Auto)")
        auto_tags_layout = QVBoxLayout(auto_tags_group)
        self.auto_tags_list = QListWidget()
        auto_tags_layout.addWidget(self.auto_tags_list)
        left_layout.addWidget(auto_tags_group)
        
        market_group = QGroupBox("Market Interest")
        market_layout = QVBoxLayout(market_group)
        # FIX: Replace QListWidget with QLabel for rich text support
        self.market_interest_label = QLabel()
        self.market_interest_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        market_layout.addWidget(self.market_interest_label)
        left_layout.addWidget(market_group)

        # --- Right Panel (Details) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        cast_group = QGroupBox("Cast Contributions")
        cast_layout = QVBoxLayout(cast_group)
        self.cast_tree = QTreeView()
        self.cast_model = QStandardItemModel()
        self.cast_tree.setModel(self.cast_model)
        self.cast_tree.setHeaderHidden(True)
        self.cast_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        cast_layout.addWidget(self.cast_tree)
        right_layout.addWidget(cast_group)
        
        details_splitter.addWidget(left_panel)
        details_splitter.addWidget(right_panel)
        details_splitter.setStretchFactor(0, 1)
        details_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(details_splitter)

        # --- Bottom Panel: Action Tabs ---
        self.action_tabs = QTabWidget()
        main_layout.addWidget(self.action_tabs)
        
        # --- Dialog Button Box ---
        # The standard buttons will be set dynamically based on scene status
        self.button_box = QDialogButtonBox()
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)


    def _create_post_production_tab(self) -> QWidget:
        """Creates the widget for the Post-Production tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        options_group = QGroupBox("Editing Options")
        options_layout = QFormLayout(options_group)
        
        editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
        
        # Get the camera setup used for this scene to calculate synergy
        camera_setup_tier = "1" # Default to single camera
        if self.scene.bloc_id:
            bloc = self.controller.get_bloc_by_id(self.scene.bloc_id)
            if bloc:
                camera_setup_tier = bloc.production_settings.get('Camera Setup', '1')

        # Use a button group to make radio buttons mutually exclusive
        self.editing_option_group = QButtonGroup(self)

        for i, tier in enumerate(editing_tiers):
            # Calculate final modifier for display
            base_mod = tier.get('base_quality_modifier', 1.0)
            synergy_mod = tier.get('synergy_mods', {}).get(camera_setup_tier, 0.0)
            final_mod = base_mod + synergy_mod

            radio_button = QRadioButton(tier['name'])
            radio_button.setProperty("tier_id", tier['id']) # Store the ID for later
            radio_button.setToolTip(tier['description'])
            if i == 0: radio_button.setChecked(True) # Default to the first option

            self.editing_option_group.addButton(radio_button)

            info_text = (f"Cost: <font color='red'>${tier['cost']:,}</font> | "
                         f"Time: {tier['weeks']}w | "
                         f"Quality Mod: <b>{final_mod:.2f}x</b>")
            options_layout.addRow(radio_button, QLabel(info_text))
        
        layout.addWidget(options_group)
        layout.addStretch()

        # Action button at the bottom
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
        if self.controller.start_editing_scene(self.scene.id, tier_id):
            self.accept() # Close dialog on success


    def populate_data(self):
        """Populates all UI elements, including the dynamic action tabs."""
        # --- Populate Permanent Details ---
        salary_expenses = sum(self.scene.pps_salaries.values())
        bloc_cost_share = 0
        editing_cost = 0
        
        tooltip_lines = [f"Talent Salaries: ${salary_expenses:,}"]

        # 1. Calculate share of bloc production costs
        if self.scene.bloc_id:
            bloc = self.controller.get_bloc_by_id(self.scene.bloc_id)
            if bloc and len(bloc.scenes) > 0:
                bloc_cost_share = bloc.production_cost / len(bloc.scenes)
                tooltip_lines.append(f"Bloc Production Share: ${int(bloc_cost_share):,}")

        # 2. Calculate editing cost
        if editing_tier_id := (self.scene.post_production_choices or {}).get('editing_tier'):
            editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
            tier_data = next((t for t in editing_tiers if t['id'] == editing_tier_id), None)
            if tier_data:
                editing_cost = tier_data.get('cost', 0)
                tooltip_lines.append(f"Post-Production: ${editing_cost:,}")
        
        total_expenses = int(salary_expenses + bloc_cost_share + editing_cost)
        
        # Create labels for the financial summary
        expenses_label = QLabel("<b>Expenses:</b>")
        expenses_label.setToolTip("\n".join(tooltip_lines))
        expenses_value_label = QLabel(f"<font color='red'>- ${total_expenses:,}</font>")

        if self.scene.status == 'released':
            revenue = self.scene.revenue
            profit = revenue - total_expenses
            revenue_text = f"<font color='green'>+ ${revenue:,}</font>"
            profit_color = "green" if profit >= 0 else "red"
            profit_text = f"<font color='{profit_color}'>${profit:,}</font>"
        else:
            revenue_text = "N/A (Not Released)"
            profit = -total_expenses
            profit_text = f"<font color='red'>(${abs(profit):,})</font>"
        
        self.financial_layout.addRow(QLabel("<b>Revenue:</b>"), QLabel(revenue_text))
        self.financial_layout.addRow(expenses_label, expenses_value_label)
        self.financial_layout.addRow(QLabel("<b>Profit:</b>"), QLabel(profit_text))

        self.tag_quality_label.setText(f"<b>Tag Qualities:</b>")
        self.tag_qualities_list.clear()
        for tag, quality in sorted(self.scene.tag_qualities.items()):
            self.tag_qualities_list.addItem(f"{tag}: {quality:.2f}")

        if self.scene.revenue_modifier_details:
             penalty_text = ", ".join([f"{k}: {v}x" for k, v in self.scene.revenue_modifier_details.items()])
             self.penalties.setText(f"<b>Revenue Modifiers:</b> {penalty_text}")
             self.penalties.setVisible(True)
        else:
            self.penalties.setVisible(False)

        self.auto_tags_list.clear()
        if self.scene.auto_tags:
            self.auto_tags_list.addItems(sorted(self.scene.auto_tags))
        else:
            self.auto_tags_list.addItem("N/A")

        # FIX: Build a single HTML string for the QLabel
        market_interest_lines = []
        for group, interest in sorted(self.scene.viewer_group_interest.items()):
            color = "green" if interest > 1.0 else "red" if interest < 1.0 else "gray"
            line = f"{group}: <font color='{color}'>{interest:.2%}</font>"
            market_interest_lines.append(line)
        
        if market_interest_lines:
            self.market_interest_label.setText("<br>".join(market_interest_lines))
        else:
            self.market_interest_label.setText("N/A")

        self.cast_model.clear()
        contribs_by_talent = defaultdict(list)
        for contrib in self.scene.performer_contributions:
            contribs_by_talent[contrib.talent_id].append(contrib)

        for vp_id, talent_id in self.scene.final_cast.items():
            talent = self.controller.talent_service.get_talent_by_id(talent_id)
            if not talent: continue
            
            talent_item = QStandardItem(talent.alias)
            talent_item.setEditable(False)

            contributions = contribs_by_talent.get(talent_id)
            if contributions:
                sorted_contributions = sorted(contributions, key=lambda c: c.contribution_key)
                for contrib in sorted_contributions:
                    contrib_item = QStandardItem(f"{contrib.contribution_key}: {contrib.quality_score:.2f} quality")
                    contrib_item.setEditable(False)
                    talent_item.appendRow(contrib_item)

            self.cast_model.appendRow(talent_item)
        self.cast_tree.expandAll()

        # --- Populate Dynamic Action Tabs ---
        self.action_tabs.clear()
        
        if self.scene.status == 'shot':
            post_prod_widget = self._create_post_production_tab()
            self.action_tabs.addTab(post_prod_widget, "Post-Production")
            self.action_tabs.setVisible(True)
            self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        
        elif self.scene.status == 'ready_to_release':
            # Placeholder for future distribution tab
            dist_widget = QLabel("Distribution and marketing options will be available here in a future update.")
            dist_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.action_tabs.addTab(dist_widget, "Distribution")
            self.action_tabs.setVisible(True)
            self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Close)

        else: # 'released' or 'in_editing' etc. No actions available.
            self.action_tabs.setVisible(False)
            self.button_box.setStandardButtons(QDialogButtonBox.StandardButton.Close)