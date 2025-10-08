from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGroupBox, QFormLayout, QLabel, QHBoxLayout
)
from PyQt6.QtCore import Qt

class MarketTab(QWidget):
    """A tab to display detailed information about market viewer groups."""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.group_widgets = {} # To hold the widgets for each group for potential future updates
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(scroll_area)

        # Container widget for the scroll area content
        self.scroll_content_widget = QWidget()
        scroll_area.setWidget(self.scroll_content_widget)

        # Layout for the container widget
        self.content_layout = QVBoxLayout(self.scroll_content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def refresh_view(self):
        """Clears and rebuilds the entire market view from controller data."""
        # Clear existing widgets
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.group_widgets.clear()

        market_data = self.controller.market_data.get('viewer_groups', [])
        market_states = self.controller.get_all_market_states()

        for group_data in market_data:
            group_name = group_data.get('name')
            if not group_name:
                continue

            # Get the dynamic state for this group
            dynamic_state = market_states.get(group_name)
            
            # Pass original data to check for 'inherits_from' key for display
            group_box = self._create_group_widget(group_name, group_data, dynamic_state)
            self.content_layout.addWidget(group_box)
            self.group_widgets[group_name] = group_box

    def _create_group_widget(self, group_name, original_group_data, dynamic_state):
        """Creates a QGroupBox that displays all info for a single viewer group, resolving inheritance."""
        resolved_data = self.controller.get_resolved_group_data(group_name)

        title = resolved_data.get('name', 'Unknown Group')
        inherits_from = original_group_data.get('inherits_from')
        if inherits_from:
            title += f" (inherits from {inherits_from})"
            
        group_box = QGroupBox(title)
        group_box.setStyleSheet("QGroupBox { font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 7px; padding: 0 5px 0 5px; }")
        
        main_vbox = QVBoxLayout(group_box)
        
        # --- General Attributes ---
        attr_box = QGroupBox("Attributes")
        attr_box.setStyleSheet("font-weight: normal;")
        attr_layout = QFormLayout(attr_box)
        attr_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        
        attr_layout.addRow("Market Share:", QLabel(f"{resolved_data.get('market_share_percent', 0):.1f}%"))
        attr_layout.addRow("Spending Power:", QLabel(f"{resolved_data.get('spending_power', 1.0):.2f}x"))
        attr_layout.addRow("Focus Bonus:", QLabel(f"{resolved_data.get('focus_bonus', 1.0):.2f}x"))
        
        if dynamic_state:
            saturation_percent = dynamic_state.current_saturation * 100
            attr_layout.addRow("Current Saturation:", QLabel(f"{saturation_percent:.2f}%"))
        
        main_vbox.addWidget(attr_box)

        # --- Preferences ---
        prefs_data = resolved_data.get('preferences', {})
        
        def create_sentiment_box(title, data_dict):
            if not data_dict:
                return None
            box = QGroupBox(title)
            box.setStyleSheet("font-weight: normal;")
            layout = QFormLayout(box)
            sorted_items = sorted(data_dict.items(), key=lambda item: item[1], reverse=True)
            for key, sentiment in sorted_items:
                label = QLabel(f"{sentiment:+.2f}")
                if sentiment > 1.0:
                    label.setStyleSheet("color: #008000;") # Green for positive
                elif sentiment < 1.0:
                    label.setStyleSheet("color: #C00000;") # Red for negative
                layout.addRow(f"{key}:", label)
            return box
        
        orient_sentiments = prefs_data.get('orientation_sentiments', {})
        concept_sentiments = prefs_data.get('concept_sentiments', {})
        tag_sentiments = prefs_data.get('tag_sentiments', {})

        if any([orient_sentiments, concept_sentiments, tag_sentiments]):
            prefs_wrapper_box = QGroupBox("Sentiments")
            prefs_wrapper_box.setStyleSheet("font-weight: normal;")
            prefs_wrapper_layout = QHBoxLayout(prefs_wrapper_box)
            prefs_wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            if box := create_sentiment_box("Orientation", orient_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := create_sentiment_box("Concept", concept_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := create_sentiment_box("Specific Tag", tag_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)

            main_vbox.addWidget(prefs_wrapper_box)

        # Scaling Sentiments
        scaling_sentiments = prefs_data.get('scaling_sentiments', {})
        if scaling_sentiments:
            scaling_box = QGroupBox("Scaling Sentiments")
            scaling_box.setStyleSheet("font-weight: normal;")
            scaling_layout = QVBoxLayout(scaling_box)
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
            main_vbox.addWidget(scaling_box)
            
        # Popularity Spillover
        spillover_data = resolved_data.get('popularity_spillover', {})
        if spillover_data:
            spillover_box = QGroupBox("Popularity Spillover")
            spillover_box.setStyleSheet("font-weight: normal;")
            spillover_layout = QFormLayout(spillover_box)
            for target, rate in spillover_data.items():
                spillover_layout.addRow(f"To {target}:", QLabel(f"{rate*100:.0f}%"))
            main_vbox.addWidget(spillover_box)

        return group_box