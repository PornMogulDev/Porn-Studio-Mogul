from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QLineEdit, QHBoxLayout,
QTableView, QHeaderView, QLabel, QMenu,
QWidgetAction, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex, QPoint
from PyQt6.QtGui import QAction
from typing import List, Dict

from data.game_state import Talent
from ui.models.talent_table_model import TalentTableModel
from ui.widgets.view_menu_button import ViewMenuButton

class TalentTableWidget(QWidget):
    """
    Widget displaying talent available for hiring, with advanced features.
    This widget includes a name filter and a table view. It supports
    double-clicking to open a talent profile and right-clicking for a
    context menu to manage Go-To list assignments. It operates in
    'casting' mode to display role-specific data like hiring cost.
    """
    # Signals for the presenter/coordinator
    open_talent_profile_requested = pyqtSignal(object)  # Talent
    name_filter_changed = pyqtSignal(str)
    context_menu_requested = pyqtSignal(list, QPoint)

    # Signals for direct connection in the presenter
    add_talent_to_category_requested = pyqtSignal(list, int)
    remove_talent_from_category_requested = pyqtSignal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.talent_model = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

         # --- Top controls layout ---
        top_controls_layout = QHBoxLayout()

        # Name filter
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("Filter by name...")
        top_controls_layout.addWidget(self.name_filter) # Add to the new HBox

        # View Button
        self.view_options_button = ViewMenuButton(self)
        self.view_options_button.setToolTip("Show/Hide Columns")
        top_controls_layout.addWidget(self.view_options_button)

        # Add the entire horizontal layout to the main vertical layout
        layout.addLayout(top_controls_layout)

        # Talent table
        self.talent_table_view = QTableView()
        self.talent_table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.talent_table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.talent_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.talent_table_view.verticalHeader().setVisible(False)
        self.talent_table_view.setSortingEnabled(True)
        self.talent_table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.talent_table_view)

        # Status label
        self.status_label = QLabel("Select a role and apply filters to view available talent")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        self.name_filter.textChanged.connect(self.name_filter_changed.emit)
        self.talent_table_view.doubleClicked.connect(self._on_talent_double_clicked)
        self.talent_table_view.customContextMenuRequested.connect(self._on_context_menu_requested)
        self.view_options_button.visibility_changed.connect(self._on_column_visibility_changed)

    def initialize_model(self, settings_manager, cup_size_order: List[str]):
        """Initialize the table model with dependencies."""
        if self.talent_model:
            return  # Avoid re-initialization
            
        self.talent_model = TalentTableModel(
            settings_manager=settings_manager,
            cup_size_order=cup_size_order,
            mode='casting'  # Use casting mode for this widget
        )
        self.talent_table_view.setModel(self.talent_model)
        self._load_and_apply_column_visibility() 
        self._setup_column_visibility_control()
        self.talent_table_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._configure_table_headers()
    
    def _setup_column_visibility_control(self):
        """Configures the ViewMenuButton to control column visibility."""
        if not self.talent_model: return
        items = [
            {
                'key': header,
                'name': header,
                'visible': not self.talent_table_view.isColumnHidden(i),
            } for i, header in enumerate(self.talent_model.headers)
        ]
        self.view_options_button.set_items(items)

    def _configure_table_headers(self):
        """Configure column widths and resize modes."""
        header = self.talent_table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 150) # Alias
        header.resizeSection(1, 50) # Age
        header.resizeSection(2, 100) # Gender
        header.resizeSection(3, 120) # Orientation
        header.resizeSection(4, 150) # Ethnicity
        header.resizeSection(5, 120) # Nationality
        header.resizeSection(6, 150) # Location
        header.resizeSection(7, 75) # Dick Size
        header.resizeSection(8, 75) # Cup Size
        header.resizeSection(9, 100) # Performance
        header.resizeSection(10, 100) # Acting
        header.resizeSection(11, 100) # Dom
        header.resizeSection(12, 100) # Sub
        header.resizeSection(13, 100) # Stamina
        header.resizeSection(14, 100) # Popularity

    def _on_column_visibility_changed(self, column_key: str, visible: bool):
        """Hides or shows a column based on the key (header text)."""
        if not self.talent_model: return
        try:
            index = self.talent_model.headers.index(column_key)
            self.talent_table_view.setColumnHidden(index, not visible)
            self._save_column_visibility_settings()
        except ValueError:
            pass # Header not found

    def _save_column_visibility_settings(self):
        if not self.talent_model: return
            
        visible_columns = [
            self.talent_model.headers[i]
            for i in range(len(self.talent_model.headers))
            if not self.talent_table_view.isColumnHidden(i)
        ]
        
        self.talent_model.settings_manager.set_setting(
            "hiring_table_visible_columns", visible_columns
        )

    def _load_and_apply_column_visibility(self):
        if not self.talent_model: return

        visible_columns = self.talent_model.settings_manager.get_setting(
            "hiring_table_visible_columns", self.talent_model.headers
        )
        visible_set = set(visible_columns)
        
        for i, header_text in enumerate(self.talent_model.headers):
            self.talent_table_view.setColumnHidden(i, header_text not in visible_set)

    def update_talent_table(self, talent_data: List[Dict]):
        """Update table with talent data. Expects a list of CastingTalentCache items."""
        if self.talent_model:
            self.talent_model.update_data(talent_data)
            count = len(talent_data)
            self.status_label.setText(f"Showing {count} available talent")

    def _on_talent_double_clicked(self, index: QModelIndex):
        """Handle double-click on talent, emitting signal to open profile."""
        if index.isValid():
            if talent := self.talent_model.data(index, Qt.ItemDataRole.UserRole):
                self.open_talent_profile_requested.emit(talent)

    def _on_context_menu_requested(self, pos: QPoint):
        """Handle right-click, emitting signal for presenter to build the menu."""
        index = self.talent_table_view.indexAt(pos)
        if not index.isValid():
            return

        # If the right-clicked item is not already selected, clear selection and select it.
        if not self.talent_table_view.selectionModel().isSelected(index):
            self.talent_table_view.clearSelection()
            self.talent_table_view.selectRow(index.row())

        selected_indexes = self.talent_table_view.selectionModel().selectedRows()
        selected_talents = [self.talent_model.data(idx, Qt.ItemDataRole.UserRole) for idx in selected_indexes]

        if selected_talents:
            global_pos = self.talent_table_view.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(selected_talents, global_pos)
            
    def display_talent_context_menu(self, talents: List[Talent], all_categories: List[Dict], pos: QPoint):
        """Creates and displays the context menu for selected talent."""
        menu = QMenu(self)
        talent_ids = [t.id for t in talents]

        add_menu = menu.addMenu("Add to Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=talent_ids, c_id=category['id']: 
                    self.add_talent_to_category_requested.emit(t_ids, c_id)
                )
                add_menu.addAction(action)
        else:
            add_menu.setEnabled(False)

        remove_menu = menu.addMenu("Remove from Go-To Category...")
        if all_categories:
            for category in sorted(all_categories, key=lambda c: c['name']):
                action = QAction(category['name'], self)
                action.triggered.connect(
                    lambda checked=False, t_ids=talent_ids, c_id=category['id']:  
                    self.remove_talent_from_category_requested.emit(t_ids, c_id)
                )
                remove_menu.addAction(action)
        else:
            remove_menu.setEnabled(False)

        menu.exec(pos)

    def get_name_filter(self) -> str:
        """Returns the current text in the name filter QLineEdit."""
        return self.name_filter.text().strip()