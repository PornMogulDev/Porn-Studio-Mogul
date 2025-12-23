from PyQt6.QtCore import Qt, QModelIndex, pyqtSignal, QPoint, QSize
from typing import List
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QMenu, QTableView, QHeaderView, 
    QToolButton, QSizePolicy
)

from data.game_state import Talent
from ui.widgets.buttons.help_button import HelpButton
from ui.models.talent_table_model import TalentTableModel
from ui.widgets.buttons.view_menu_button import ViewMenuButton
from ui.widgets.role_details_widget import RoleDetailsWidget
from ui.widgets.scene_summary_widget import SceneSummaryWidget
from ui.widgets.entity_card.smart_table_view import SmartTableView

class TalentTab(QWidget):
    # Signals for the Presenter
    standard_filters_changed = pyqtSignal(dict)
    context_menu_requested = pyqtSignal(list, QPoint)
    add_talent_to_category_requested = pyqtSignal(list, int)
    remove_talent_from_category_requested = pyqtSignal(list, int)
    open_talent_profile_requested = pyqtSignal(object)
    initial_load_requested = pyqtSignal()
    help_requested = pyqtSignal(str)
    smart_hover_entered = pyqtSignal(object, QPoint)
    smart_hover_left = pyqtSignal()
    
    # New Signals
    filter_panel_toggled = pyqtSignal(bool)

    def __init__(self, icon_manager):
        super().__init__()
        self.icon_manager = icon_manager
        self.talent_model = None
        self.advanced_filters = {}
        self.settings_manager = None
        self.is_filter_panel_expanded = True
        
        # --- UI Components ---
        self.view_options_button: ViewMenuButton = None
        self.role_details_widget: RoleDetailsWidget = None
        self.scene_summary_widget: SceneSummaryWidget = None
        self.talent_table_view: SmartTableView = None
        self.main_splitter: QSplitter = None
        self.info_panel_container: QWidget = None
        self.filter_sidebar_container: QWidget = None
        self.talent_filter_widget = None
        
        self.setup_ui()

    def create_model_and_load(self, settings_manager, icon_manager, ui_manager, cup_size_order: List[str]):
        """Called by the presenter to inject dependencies and trigger initial load."""
        self.settings_manager = settings_manager
        self.icon_manager = icon_manager
        
        # Inject UI Manager into summary widget for smart links
        if self.scene_summary_widget:
            self.scene_summary_widget.ui_manager = ui_manager

        if self.talent_model is None:
            self.talent_model = TalentTableModel(
                settings_manager=settings_manager,
                icon_manager=icon_manager,
                cup_size_order=cup_size_order
            )
            self.talent_table_view.setModel(self.talent_model)
            self._configure_table_view_headers()
            self._load_and_apply_column_visibility()
            self._setup_visibility_controls()

            self.settings_manager.signals.setting_changed.connect(self._on_setting_changed)
            self._update_table_icon_size()

            self.initial_load_requested.emit()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # --- Top controls container ---
        top_bar_layout = QHBoxLayout()
        help_btn = HelpButton("talent", self.icon_manager, self)
        self.view_options_button = ViewMenuButton(self.icon_manager, self)
        self.view_options_button.setToolTip("Show/Hide Columns")
        
        self.name_filter_input = QLineEdit(placeholderText="Filter by name...")
        # Note: Advanced Filter button removed as filters are now integrated in the sidebar
        
        top_bar_layout.addWidget(help_btn)
        top_bar_layout.addWidget(self.view_options_button)
        top_bar_layout.addWidget(self.name_filter_input)
        main_layout.addLayout(top_bar_layout)

        # --- Main Splitter (Horizontal) ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        
        # 1. Left Pane: Info Panel (Vertical Splitter inside a Widget)
        self.info_panel_container = QWidget()
        info_layout = QVBoxLayout(self.info_panel_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.info_splitter = QSplitter(Qt.Orientation.Vertical)
        self.role_details_widget = RoleDetailsWidget(self)
        self.scene_summary_widget = SceneSummaryWidget(parent=self)
        
        self.info_splitter.addWidget(self.role_details_widget)
        self.info_splitter.addWidget(self.scene_summary_widget)
        info_layout.addWidget(self.info_splitter)
        
        # Initially hidden (only shown in Casting Mode)
        self.info_panel_container.hide() 
        self.main_splitter.addWidget(self.info_panel_container)
        
        # 2. Middle Pane: Talent Table
        self.talent_table_view = SmartTableView()
        self._configure_table_view_properties()
        self.main_splitter.addWidget(self.talent_table_view)
        
        # 3. Right Pane: Filter Sidebar
        self.filter_sidebar_container = QWidget()
        self.filter_sidebar_layout = QHBoxLayout(self.filter_sidebar_container)
        self.filter_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_sidebar_layout.setSpacing(0)
        
        # Toggle Button (Chevron)
        self.toggle_filter_btn = QToolButton()
        self.toggle_filter_btn.setCheckable(True)
        self.toggle_filter_btn.setChecked(True)
        # Initial Icon state (Expanded -> chevron_right to close)
        self.icon_manager.apply_icon(self.toggle_filter_btn, "chevron_right", "accent")
        
        self.toggle_filter_btn.setToolTip("Collapse Filters")
        self.toggle_filter_btn.setFixedWidth(20)
        self.toggle_filter_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding  # Match vertical height
        )
        
        self.toggle_filter_btn.clicked.connect(self._toggle_filter_panel)
        
        self.filter_sidebar_layout.addWidget(self.toggle_filter_btn)
        
        # Placeholder for the filter widget (injected later)
        self.filter_placeholder_layout = QVBoxLayout()
        self.filter_sidebar_layout.addLayout(self.filter_placeholder_layout)
        
        self.main_splitter.addWidget(self.filter_sidebar_container)
        main_layout.addWidget(self.main_splitter)
        
        # --- Layout Priorities ---
        self.main_splitter.setStretchFactor(0, 0) # Info Panel
        self.main_splitter.setStretchFactor(1, 1) # Table (grows)
        self.main_splitter.setStretchFactor(2, 0) # Filter Panel

        # --- Connections ---
        self.talent_table_view.customContextMenuRequested.connect(self.show_talent_list_context_menu)
        self.talent_table_view.doubleClicked.connect(self.show_talent_profile)
        self.name_filter_input.textChanged.connect(self.filter_talent_list)
        
        self.talent_table_view.smart_hover_entered.connect(self.smart_hover_entered)
        self.talent_table_view.smart_hover_left.connect(self.smart_hover_left)
        self.talent_table_view.smart_alt_clicked.connect(self.show_talent_profile_direct)
        
        self.view_options_button.visibility_changed.connect(self._on_visibility_changed)
        help_btn.help_requested.connect(self.help_requested)

    def set_filter_widget(self, widget: QWidget):
        """Injected by Presenter. Replaces any placeholder in the right sidebar."""
        self.talent_filter_widget = widget
        self.filter_sidebar_layout.addWidget(widget)
        # Ensure initial state matches toggle button
        widget.setVisible(self.is_filter_panel_expanded)
        
        # Forward signals from the embedded widget
        # Assuming widget has 'filters_applied' signal
        if hasattr(widget, 'filters_applied'):
            widget.filters_applied.connect(self.on_filters_applied)
        # Also connect local role selection signals if present
        if hasattr(widget, 'scene_selected'):
            # These might be connected directly by the presenter, 
            # but we ensure the view hierarchy is respected if needed.
            pass

    def _toggle_filter_panel(self):
        """Internal slot to toggle filter visibility and update icon."""
        self.is_filter_panel_expanded = not self.is_filter_panel_expanded
        self.set_filter_panel_visible(self.is_filter_panel_expanded)
        # Emit signal if presenter needs to track/save this state
        self.filter_panel_toggled.emit(self.is_filter_panel_expanded)

    def set_filter_panel_visible(self, visible: bool):
        """Programmatically set filter panel state."""
        self.is_filter_panel_expanded = visible
        self.toggle_filter_btn.setChecked(visible)
        
        if self.talent_filter_widget:
            self.talent_filter_widget.setVisible(visible)
        
        # Collapse/expand the entire filter sidebar in the splitter
        sizes = self.main_splitter.sizes()
        if visible:
            # Restore: give filter panel reasonable space (e.g., 250px or 20% of total)
            if sizes[2] < 200:  # If currently collapsed
                total = sum(sizes)
                self.main_splitter.setSizes([sizes[0], total - 250, 250])
            self.icon_manager.apply_icon(self.toggle_filter_btn, "chevron_right", "accent")
            self.toggle_filter_btn.setToolTip("Collapse Filters")
        else:
            # Collapse: set filter panel width to just the button width (20px)
            total = sum(sizes)
            self.main_splitter.setSizes([sizes[0], total - 20, 20])
            self.icon_manager.apply_icon(self.toggle_filter_btn, "chevron_left", "accent")
            self.toggle_filter_btn.setToolTip("Expand Filters")

    # --- Info Panel Management ---

    def set_info_panel_visible(self, visible: bool):
        """Shows or hides the entire left sidebar."""
        was_visible = self.info_panel_container.isVisible()
        self.info_panel_container.setVisible(visible)

        if visible and not was_visible:
            # We just showed the panel. Check if it defaulted to a collapsed state (width ~0).
            sizes = self.main_splitter.sizes()
            total_width = sum(sizes)
            current_info_width = sizes[0]
            
            # If it's too small (collapsed), force it to take up space (e.g., 20% or min 280px)
            if current_info_width < 50 and total_width > 0:
                target_width = max(280, int(total_width * 0.20))
                remaining_width = total_width - target_width - sizes[2]
                self.main_splitter.setSizes([target_width, remaining_width, sizes[2]])

    def configure_info_panel(self, show_role: bool, show_summary: bool):
        """Configures which widgets are visible inside the info panel."""
        self.role_details_widget.setVisible(show_role)
        self.scene_summary_widget.setVisible(show_summary)
        
        # If both are hidden, hide the container to save space
        if not show_role and not show_summary:
            self.info_panel_container.hide()

    def update_scene_summary(self, summary_data: dict):
        """Updates the scene summary widget."""
        self.scene_summary_widget.update_summary(summary_data)

    def display_role_details(self, html: str):
        """Updates the content of the role details panel."""
        self.role_details_widget.update_role_details(html)
    
    def clear_role_details(self):
        """Clears the role details display and shows the placeholder."""
        self.role_details_widget.clear()
        self.scene_summary_widget.update_summary({}) # Clear summary too

    # --- Existing Functionality ---

    def show_talent_profile_direct(self, talent):
         self.open_talent_profile_requested.emit(talent)

    def _configure_table_view_properties(self):
        """Sets the static properties for the QTableView."""
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.setAlternatingRowColors(True)
        self.talent_table_view.horizontalHeader().setStretchLastSection(True)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.talent_table_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.talent_table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def _on_setting_changed(self, key):
        if key in {"font_size", "theme"}:
            if key == "font_size":
                self._update_table_icon_size()
            self.view_options_button.refresh_icon()
            # Refresh toggle icon (re-applies icon with current theme colors)
            self.set_filter_panel_visible(self.is_filter_panel_expanded)

    def _update_table_icon_size(self):
        """Calculates and sets the table icon size based on font scaling."""
        target_size = self.icon_manager.get_target_size()
        width = target_size.width()
        height = int(width / 1.5) # Roughly 3:2 aspect ratio for flags
        self.talent_table_view.setIconSize(QSize(width, height))

    def _configure_table_view_headers(self):
        """Sets the initial column sizes."""
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.talent_table_view.resizeColumnsToContents()
        header.resizeSection(0, 175) # Alias
        header.resizeSection(1, 50) # Age
        header.resizeSection(2, 100) # Gender
        header.resizeSection(3, 120) # Orientation
        header.resizeSection(4, 150) # Ethnicity
        header.resizeSection(5, 120) # Nationality
        header.resizeSection(6, 160) # Base Location
        header.resizeSection(7, 160) # Effective Location
        header.resizeSection(8, 75) # Dick Size
        header.resizeSection(9, 75) # Cup Size
        header.resizeSection(10, 75) # Performance
        header.resizeSection(11, 75) # Acting
        header.resizeSection(12, 75) # Dom
        header.resizeSection(13, 75) # Sub
        header.resizeSection(14, 75) # Stamina
        header.resizeSection(15, 75) # Popularity
        header.resizeSection(16, 50) # Demand
        if self.talent_model and 'Demand' in self.talent_model.headers:
            demand_index = self.talent_model.headers.index('Demand')
            header.resizeSection(demand_index, 100)

    # --- Public Methods for Presenter ---

    def update_talent_list(self, talents: list):
        self.talent_model.update_data(talents)

    def on_filters_applied(self, filters: dict):
        self.advanced_filters = filters
        self.filter_talent_list()

        if self.settings_manager.get_setting("auto_hide_filter_on_apply", True):
            self.set_filter_panel_visible(False)

    def refresh_from_state(self):
        self.filter_talent_list()
        
    def filter_talent_list(self):
        all_filters = self.advanced_filters.copy()
        all_filters['text'] = self.name_filter_input.text()
        self.standard_filters_changed.emit(all_filters)

    # --- Internal Logic & Slots ---

    def _setup_visibility_controls(self):
        """Configures the ViewMenuButton for columns."""
        if not self.talent_model: return
        
        items = []
        for i, header in enumerate(self.talent_model.headers):
            item = {
                'key': header, 
                'name': header,
            }
            if header == "Demand":
                user_pref = self.settings_manager.get_setting("demand_column_user_preference", True)
                item['visible'] = user_pref
                item['tooltip'] = "This column is only visible during Casting Mode if checked."
                # Custom icon for the Demand column
                item['active_icon'] = "exclamation_mark"
                item['active_color_role'] = "warning"
            else:
                item['visible'] = not self.talent_table_view.isColumnHidden(i)
                # item['tooltip'] = f"Toggle visibility of the {header} column." # I don't think this makes much sense to have

            items.append(item)

        self.view_options_button.set_items(items)
    
    def _on_visibility_changed(self, key: str, visible: bool):
        if not self.talent_model: return

        self.view_options_button.update_item_visibility(key, visible)

        if key == "Demand":
            self.settings_manager.set_setting("demand_column_user_preference", visible)
            # The presenter handles actual column showing/hiding based on mode
        else:
            try:
                index = self.talent_model.headers.index(key)
                self.talent_table_view.setColumnHidden(index, not visible)
                self._save_column_visibility_settings()
            except ValueError:
                pass 
            
    def _save_column_visibility_settings(self):
        if not self.talent_model: return
        # Standardizing to dictionary storage (header_name: bool) for now, but we should simply use lists for it
        settings = {}
        for i, header in enumerate(self.talent_model.headers):
            settings[header] = not self.talent_table_view.isColumnHidden(i)
        self.settings_manager.set_setting("talent_tab_visible_columns", settings)
        
    def _load_and_apply_column_visibility(self):
        if not self.talent_model: return
        settings = self.settings_manager.get_setting("talent_tab_visible_columns", {})
        if not isinstance(settings, dict):
            settings = {}
        for i, header_text in enumerate(self.talent_model.headers):
            # Special case: Demand column visibility is strictly controlled by logic + pref, not just saved state
            if header_text == "Demand": continue 
            # Default to True if not explicitly saved as False
            is_visible = settings.get(header_text, True)
            self.talent_table_view.setColumnHidden(i, not is_visible)

    def show_talent_profile(self, index: QModelIndex):
        if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
            self.open_talent_profile_requested.emit(talent)

    def show_talent_list_context_menu(self, pos):
        index = self.talent_table_view.indexAt(pos)
        if not index.isValid(): return

        if not self.talent_table_view.selectionModel().isSelected(index):
            self.talent_table_view.clearSelection()
            self.talent_table_view.selectRow(index.row())

        selected_indexes = self.talent_table_view.selectionModel().selectedRows()
        selected_talents = [self.talent_model.data(idx, Qt.ItemDataRole.UserRole) for idx in selected_indexes]
        
        if selected_talents:
            global_pos = self.talent_table_view.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(selected_talents, global_pos)

    def set_demand_column_visible(self, visible: bool):
        """Public method for Presenter to control Demand column visibility based on mode."""
        if not self.talent_model: return
        if "Demand" in self.talent_model.headers:
            index = self.talent_model.headers.index("Demand")
            self.talent_table_view.setColumnHidden(index, not visible)
            # Update the menu checkmark to reflect the actual state
            self.view_options_button.update_item_visibility("Demand", visible)

    def display_talent_context_menu(self, talents: List[Talent], all_categories: list, pos: QPoint):
        menu = QMenu(self)
        talent_ids = [t.id for t in talents]
        add_menu = menu.addMenu("Add to Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(lambda checked=False, t_ids=talent_ids, c_id=category['id']: 
                    self.add_talent_to_category_requested.emit(t_ids, c_id))
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        remove_menu = menu.addMenu("Remove from Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(lambda checked=False, t_ids=talent_ids, c_id=category['id']:  
                    self.remove_talent_from_category_requested.emit(t_ids, c_id))
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        menu.exec(pos)