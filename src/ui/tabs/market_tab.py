from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGroupBox,
    QFormLayout, QLabel, QHBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.view_models import MarketGroupViewModel, SentimentViewModel
from ui.widgets.help_button import HelpButton

class MarketTab(QWidget):
    """
    A "dumb" view to display detailed information about market viewer groups.
    All logic is handled by the MarketTabPresenter.
    """
    group_selected = pyqtSignal(str)
    help_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_group_widget = None
        self.setup_ui()
    
        # Connect the selector's signal to an internal method that emits our custom signal
        self.group_selector.currentTextChanged.connect(self._on_group_selection_changed)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        help_btn = HelpButton("market", self)
        # The presenter will handle the signal connection from the controller
        help_btn.help_requested.connect(self.help_requested)
        main_layout.addWidget(help_btn)
        
        # Dropdown to select the viewer group
        self.group_selector = QComboBox()
        self.group_selector.setPlaceholderText("Select a Viewer Group...")
        main_layout.addWidget(self.group_selector)

        # Container for the selected group's details
        self.details_scroll_area = QScrollArea()
        self.details_scroll_area.setWidgetResizable(True)
        self.details_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.details_scroll_area, 1) # Add stretch factor

    def update_group_selector(self, group_names: List[str]):
        """Clears and rebuilds the combo box with a list of group names."""
        self.group_selector.blockSignals(True)
        self.group_selector.clear()

        if not group_names:
            self.group_selector.setPlaceholderText("No viewer groups found.")
        else:
            self.group_selector.addItems(group_names)
        
        self.group_selector.blockSignals(False)

        # If items were added, set to the first one, which will trigger
        # currentTextChanged and notify the presenter.
        if self.group_selector.count() > 0:
            self.group_selector.setCurrentIndex(0)
        else: # Handle case where there are no groups
            self._on_group_selection_changed("")

    def _on_group_selection_changed(self, group_name: str):
        """Emits a signal to the presenter when the user selects a group."""
        self.group_selected.emit(group_name)

    def display_group_details(self, vm: MarketGroupViewModel):
        """Creates and displays the widget based on the provided view model."""
        if self.current_group_widget:
            self.current_group_widget.deleteLater()
            self.current_group_widget = None
        
        if not vm.is_visible:
            placeholder = QLabel("No viewer group selected." if not vm.title else vm.title)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.details_scroll_area.setWidget(placeholder)
            return
        
        container_widget = QWidget()
        main_vbox = QVBoxLayout(container_widget)

        # --- Title Label ---
        title_label = QLabel(vm.title)
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; margin-bottom: 5px;")
        main_vbox.addWidget(title_label)
        
        # --- Top Section: Attributes & Sentiments ---
        top_hbox_widget = QWidget()
        top_hbox_layout = QHBoxLayout(top_hbox_widget)
        top_hbox_layout.setContentsMargins(0,0,0,0)
        top_hbox_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # --- Attributes (Left side) ---
        attr_box = QGroupBox("Attributes")
        attr_box.setStyleSheet("font-weight: normal;")
        attr_layout = QFormLayout(attr_box)
        for label, value in vm.attributes:
            attr_layout.addRow(label, QLabel(value))
        top_hbox_layout.addWidget(attr_box, 1)
        
        # --- Orientation Sentiments (Right side) ---
        if box := self._create_sentiment_box("Orientation", vm.orientation_sentiments):
            top_hbox_layout.addWidget(box, 1)
        
        # --- Dominance Sentiments (Right side) ---
        if box := self._create_sentiment_box("D/s Dynamic Preferences", vm.dom_sub_sentiments):
            top_hbox_layout.addWidget(box, 1)
        
        main_vbox.addWidget(top_hbox_widget)
        
        # --- Tag Sentiments ---
        if any([vm.thematic_sentiments, vm.physical_sentiments, vm.action_sentiments]):
            prefs_wrapper_box = QGroupBox("Tag Sentiments")
            prefs_wrapper_box.setStyleSheet("font-weight: normal;")
            prefs_wrapper_layout = QHBoxLayout(prefs_wrapper_box)
            prefs_wrapper_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            if box := self._create_sentiment_box("Thematic", vm.thematic_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := self._create_sentiment_box("Physical", vm.physical_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)
            if box := self._create_sentiment_box("Action", vm.action_sentiments):
                prefs_wrapper_layout.addWidget(box, 1)

            main_vbox.addWidget(prefs_wrapper_box, 1)
            
        # --- Popularity Spillover ---
        if vm.spillover_details:
            spillover_box = QGroupBox("Popularity Spillover")
            spillover_box.setStyleSheet("font-weight: normal;")
            box_layout = QVBoxLayout(spillover_box)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMinimumHeight(80)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            
            scroll_widget = QWidget()
            spillover_layout = QFormLayout(scroll_widget)
            
            for label, value in vm.spillover_details:
                spillover_layout.addRow(label, QLabel(value))
            
            scroll_area.setWidget(scroll_widget)
            box_layout.addWidget(scroll_area)
            main_vbox.addWidget(spillover_box)
        
        main_vbox.addStretch()

        self.current_group_widget = container_widget
        self.details_scroll_area.setWidget(self.current_group_widget)

    def _create_sentiment_box(self, title: str, sentiments: List[SentimentViewModel]) -> QGroupBox | None:
        """Helper method to create a standardized box for displaying sentiments."""
        if not sentiments: return None
        
        box = QGroupBox(title)
        box.setStyleSheet("font-weight: normal;")
        box_layout = QVBoxLayout(box)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(120)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content_widget = QWidget()
        layout = QFormLayout(scroll_content_widget)

        for sentiment_vm in sentiments:
            value_label = QLabel(sentiment_vm.value_str)
            if sentiment_vm.color:
                value_label.setStyleSheet(f"color: {sentiment_vm.color};")
            
            layout.addRow(f"{sentiment_vm.label}:", value_label)
        
        scroll_area.setWidget(scroll_content_widget)
        box_layout.addWidget(scroll_area)
        return box