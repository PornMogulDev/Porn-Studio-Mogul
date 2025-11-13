from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QDialogButtonBox, 
    QFormLayout, QWidget, QTabWidget, QRadioButton, QButtonGroup, 
    QPushButton, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer
from ui.widgets.scene_summary_widget import SceneSummaryWidget
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.presenters.shot_scene_details_presenter import ShotSceneDetailsPresenter

class ShotSceneDetailsDialog(GeometryManagerMixin, QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.presenter = None 

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.defaultSize = QSize(750, 800)
        
        self.editing_option_group = QButtonGroup()
        
        self.setup_ui()
        self._restore_geometry()

    def set_presenter(self, presenter: ShotSceneDetailsPresenter):
        """Links the dialog with its presenter and triggers initial data load."""
        self.presenter = presenter
        # Defer the initial load until the presenter is fully set up.
        QTimer.singleShot(0, self.presenter.load_initial_data)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Main Tab Widget ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- Tab 1: Financial & Market ---
        financial_tab = QWidget()
        financial_layout = QVBoxLayout(financial_tab)
        
        financial_group = QGroupBox("Financial Summary")
        # Use QHBoxLayout for horizontal arrangement
        financial_group_layout = QHBoxLayout(financial_group)
        
        # Create individual widgets for each section to manage layout
        expenses_widget = QWidget()
        expenses_layout = QVBoxLayout(expenses_widget)
        self.expenses_label = QLabel()
        self.expenses_label.setWordWrap(True)
        expenses_layout.addWidget(self.expenses_label)
        
        revenue_widget = QWidget()
        revenue_layout = QVBoxLayout(revenue_widget)
        self.revenue_label = QLabel()
        self.revenue_label.setWordWrap(True)
        revenue_layout.addWidget(self.revenue_label)
        
        profit_widget = QWidget()
        profit_layout = QHBoxLayout(profit_widget)
        self.profit_label = QLabel()
        profit_layout.addWidget(self.profit_label)
        
        financial_group_layout.addWidget(expenses_widget, 3, Qt.AlignmentFlag.AlignBottom)
        financial_group_layout.addWidget(revenue_widget, 3, Qt.AlignmentFlag.AlignBottom)
        financial_group_layout.addWidget(profit_widget, 1, Qt.AlignmentFlag.AlignBottom)
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
        self.setWindowTitle(f"Details: {self.presenter.get_scene_title()}")

        # --- Financial & Market Summary ---
        financial_vm = self.presenter.get_financial_view_model()
        self.expenses_label.setText(financial_vm.expenses_html)
        self.revenue_label.setText(financial_vm.revenue_html)
        self.profit_label.setText(financial_vm.profit_html)
        self.market_interest_label.setText(financial_vm.market_interest_html)

        # --- Design Summary Tab ---
        summary_data = self.presenter.get_summary_data()
        self.summary_widget.update_summary(summary_data)
        
        # --- Dynamic Post-Production Tab ---
        self._setup_post_production_tab()

    def set_active_tab(self, tab_name: str):
        """Finds a tab by its text and sets it as the current tab."""
        tab_name_lower = tab_name.lower()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower() == tab_name_lower:
                self.tabs.setCurrentIndex(i)
                break

    def _setup_post_production_tab(self):
        """Creates or updates the post-production tab based on scene status."""
        # If the tab exists, remove it before rebuilding to ensure it's fresh
        if self.post_prod_tab_index != -1:
            self.tabs.removeTab(self.post_prod_tab_index)
            self.post_prod_tab_index = -1
            self.post_prod_tab = None 

        pp_vm = self.presenter.get_post_production_view_model()
        if not pp_vm.is_visible:
            return

        self.post_prod_tab = QWidget()
        layout = QVBoxLayout(self.post_prod_tab)
        options_widget = self._create_editing_options_widget(pp_vm.options)
        layout.addWidget(options_widget)

        self.post_prod_tab_index = self.tabs.addTab(self.post_prod_tab, "Post-Production")
            
    def _create_editing_options_widget(self, options) -> QWidget:
        """Creates the widget with radio buttons for editing choices."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        options_group = QGroupBox("Editing Options")
        options_layout = QFormLayout(options_group)
        
        self.editing_option_group = QButtonGroup(self)
        for option in options:
            radio_button = QRadioButton(option.name)
            radio_button.setProperty("tier_id", option.tier_id)
            radio_button.setToolTip(option.tooltip)
            if option.is_checked:
                radio_button.setChecked(True)
            self.editing_option_group.addButton(radio_button)
            options_layout.addRow(radio_button, QLabel(option.info_text))
        
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
    
        self.presenter.start_editing(tier_id)

    def closeEvent(self, event):
        """Override to ensure the presenter disconnects its signals."""
        self.presenter.disconnect_signals()
        super().closeEvent(event)