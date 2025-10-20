from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QScrollArea, QGroupBox, QFormLayout, QLabel, QHBoxLayout, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt

from ui.widgets.help_button import HelpButton

class MarketTab(QWidget):
    """A tab to display detailed information about market viewer groups using a dropdown."""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # Store data locally to repopulate view on selection change
        self.market_groups_data = []
        self.market_states_data = {}
        self.current_group_widget = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        help_btn = HelpButton("market", self)
        help_btn.help_requested.connect(self.controller.signals.show_help_requested)
        main_layout.addWidget(help_btn)
        # Dropdown to select the viewer group
        self.group_selector = QComboBox()
        self.group_selector.setPlaceholderText("Select a Viewer Group...")
        self.group_selector.currentTextChanged.connect(self._on_group_selected)
        main_layout.addWidget(self.group_selector)

        # Container for the selected group's details
        # The QScrollArea ensures the content of a single large group is scrollable
        self.details_scroll_area = QScrollArea()
        self.details_scroll_area.setWidgetResizable(True)
        self.details_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.details_scroll_area, 1) # Add stretch factor

    def refresh_view(self):
        """Clears and rebuilds the combo box and shows the first group."""
        # Clear previous state
        if self.current_group_widget:
            self.current_group_widget.deleteLater()
            self.current_group_widget = None
        
        self.group_selector.clear()

        # Store the latest data
        self.market_groups_data = self.controller.market_data.get('viewer_groups', [])
        self.market_states_data = self.controller.get_all_market_states()

        # Populate the combo box, blocking signals to prevent premature updates
        self.group_selector.blockSignals(True)
        group_names = [g.get('name') for g in self.market_groups_data if g.get('name')]
        if not group_names:
            self.group_selector.setPlaceholderText("No viewer groups found.")
        else:
            self.group_selector.addItems(group_names)
        self.group_selector.blockSignals(False)
        
        # Trigger the view for the first item if it exists
        if self.group_selector.count() > 0:
            self.group_selector.setCurrentIndex(0)
            self._on_group_selected(self.group_selector.itemText(0))
        else: # Handle case where there are no groups
            self._on_group_selected(None)


    def _on_group_selected(self, group_name):
        """Creates and displays the widget for the selected group."""
        # Clear the previous widget from the scroll area
        if self.current_group_widget:
            self.current_group_widget.deleteLater()
            self.current_group_widget = None
        
        if not group_name:
            # If no group is selected or available, set a placeholder
            placeholder = QLabel("No viewer group selected.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.details_scroll_area.setWidget(placeholder)
            return

        group_data = next((g for g in self.market_groups_data if g.get('name') == group_name), None)
        
        if not group_data:
            return

        dynamic_state = self.market_states_data.get(group_name)
        
        # Create the new group widget and set it as the scroll area's content
        self.current_group_widget = self._create_group_widget(group_name, group_data, dynamic_state)
        self.details_scroll_area.setWidget(self.current_group_widget)

    def _create_group_widget(self, group_name, original_group_data, dynamic_state):
        """Creates a QGroupBox that displays all info for a single viewer group, resolving inheritance."""
        resolved_data = self.controller.get_resolved_group_data(group_name)

        # The main container is now a QWidget instead of a QGroupBox,
        # as the selection is handled by the combo box.
        container_widget = QWidget()
        main_vbox = QVBoxLayout(container_widget)

        # --- Title Label ---
        title_text = resolved_data.get('name', 'Unknown Group')
        if inherits_from := original_group_data.get('inherits_from'):
            title_text += f" (inherits from {inherits_from})"
        title_label = QLabel(title_text)
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 5px;")
        main_vbox.addWidget(title_label)
        
        prefs_data = resolved_data.get('preferences', {})
        
        def create_sentiment_box(title, data_dict, is_additive=False):
            if not data_dict: return None
            
            box = QGroupBox(title)
            box.setStyleSheet("font-weight: normal;")
            box_layout = QVBoxLayout(box)

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(120)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            scroll_content_widget = QWidget()
            layout = QFormLayout(scroll_content_widget)

            sorted_items = sorted(data_dict.items(), key=lambda item: item[1], reverse=True)
            for key, sentiment in sorted_items:
                if is_additive:
                    label = QLabel(f"{sentiment:+.2f}")
                    if sentiment > 0: label.setStyleSheet("color: #008000;")
                    elif sentiment < 0: label.setStyleSheet("color: #C00000;")
                else:
                    label = QLabel(f"{sentiment:.2f}x")
                    if sentiment > 1.0: label.setStyleSheet("color: #008000;")
                    elif sentiment < 1.0: label.setStyleSheet("color: #C00000;")
                layout.addRow(f"{key}:", label)
            
            scroll_area.setWidget(scroll_content_widget)
            box_layout.addWidget(scroll_area)
            return box
        
        # --- Top Section: Attributes & Orientation Sentiments ---
        top_hbox_widget = QWidget()
        top_hbox_layout = QHBoxLayout(top_hbox_widget)
        top_hbox_layout.setContentsMargins(0,0,0,0)
        top_hbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- Attributes (Left side) ---
        attr_box = QGroupBox("Attributes")
        attr_box.setStyleSheet("font-weight: normal;")
        attr_layout = QVBoxLayout(attr_box)
        
        attr_layout.addWidget(QLabel(f"Market Share: {resolved_data.get('market_share_percent', 0):.1f}%"))
        attr_layout.addWidget(QLabel(f"Spending Power: {resolved_data.get('spending_power', 1.0):.2f}x"))
        attr_layout.addWidget(QLabel(f"Focus Bonus: {resolved_data.get('focus_bonus', 1.0):.2f}x"))
        if dynamic_state:
            attr_layout.addWidget(QLabel(f"Spending Willingness: {(dynamic_state.current_saturation * 100):.2f}%"))
        attr_layout.addStretch()
        top_hbox_layout.addWidget(attr_box, 1)
        
        # --- Orientation Sentiments (Right side) ---
        orientation_sentiments = prefs_data.get('orientation_sentiments', {})
        if box := create_sentiment_box("Orientation Sentiments", orientation_sentiments):
            top_hbox_layout.addWidget(box, 1)
        
        main_vbox.addWidget(top_hbox_widget)
        
        # --- Tag Sentiments ---
        thematic_sentiments = prefs_data.get('thematic_sentiments', {})
        physical_sentiments = prefs_data.get('physical_sentiments', {})
        action_sentiments = prefs_data.get('action_sentiments', {})

        if any([thematic_sentiments, physical_sentiments, action_sentiments]):
            prefs_wrapper_box = QGroupBox("Tag Sentiments")
            prefs_wrapper_box.setStyleSheet("font-weight: normal;")
            prefs_wrapper_layout = QHBoxLayout(prefs_wrapper_box)
            prefs_wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            if box := create_sentiment_box("Thematic (Additive)", thematic_sentiments, is_additive=True):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := create_sentiment_box("Physical", physical_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := create_sentiment_box("Action", action_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)

            main_vbox.addWidget(prefs_wrapper_box, 1)

        # Scaling Sentiments
        scaling_sentiments = prefs_data.get('scaling_sentiments', {})
        if scaling_sentiments:
            scaling_box = QGroupBox("Scaling Sentiments")
            scaling_box.setStyleSheet("font-weight: normal;")
            box_layout = QVBoxLayout(scaling_box)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(80)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            scroll_widget = QWidget()
            scaling_layout = QVBoxLayout(scroll_widget)
            
            for tag, rules in scaling_sentiments.items():
                rule_str = f"<b>{tag}:</b> "
                details = []
                if 'based_on_role' in rules: details.append(f"scales on '{rules['based_on_role']}' count")
                if 'applies_after' in rules: details.append(f"after {rules['applies_after']}")
                if 'bonuses' in rules: details.append(f"bonuses: {rules['bonuses']}")
                if 'bonus_per_unit' in rules: details.append(f"bonus/unit: {rules['bonus_per_unit']:+.2f}")
                if 'penalty_after' in rules: details.append(f"penalty after {rules['penalty_after']}")
                if 'penalty_per_unit' in rules: details.append(f"penalty/unit: {rules['penalty_per_unit']:.2f}")
                rule_str += ", ".join(details)
                scaling_layout.addWidget(QLabel(rule_str))
                
            scroll_area.setWidget(scroll_widget)
            box_layout.addWidget(scroll_area)
            main_vbox.addWidget(scaling_box)
            
        # Popularity Spillover
        spillover_data = resolved_data.get('popularity_spillover', {})
        if spillover_data:
            spillover_box = QGroupBox("Popularity Spillover")
            spillover_box.setStyleSheet("font-weight: normal;")
            box_layout = QVBoxLayout(spillover_box)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(80)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            scroll_widget = QWidget()
            spillover_layout = QFormLayout(scroll_widget)
            
            for target, rate in spillover_data.items():
                spillover_layout.addRow(f"To {target}:", QLabel(f"{rate*100:.0f}%"))
            
            scroll_area.setWidget(scroll_widget)
            box_layout.addWidget(scroll_area)
            main_vbox.addWidget(spillover_box)
        
        main_vbox.addStretch() # Pushes content to the top

        return container_widget