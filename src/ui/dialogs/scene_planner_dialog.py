from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QDialogButtonBox,
    QSpinBox, QGroupBox, QWidget, QScrollArea, QStackedWidget,
    QCheckBox, QMessageBox, QMenu, QTabWidget
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QPoint,
    QSize
)
from PyQt6.QtGui import QKeyEvent

from utils.scene_summary_builder import prepare_summary_data
from ui.widgets.scene_summary_widget import SceneSummaryWidget
from ui.widgets.scene_planner.draggable_list_widget import DraggableListWidget
from ui.widgets.scene_planner.drop_enabled_list_widget import DropEnabledListWidget
from ui.widgets.scene_planner.action_segment_widget import ActionSegmentItemWidget
from ui.widgets.scene_planner.slot_assignment_widget import SlotAssignmentWidget
from data.game_state import ActionSegment
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin
from ui.widgets.help_button import HelpButton
    
class ScenePlannerDialog(GeometryManagerMixin, QDialog):
    # --- Signals for User Actions ---
    view_loaded = pyqtSignal()
    save_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    delete_requested = pyqtSignal(float)
    title_changed = pyqtSignal(str)
    focus_target_changed = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    ds_level_changed = pyqtSignal(int)
    performer_count_changed = pyqtSignal(int)
    composition_changed = pyqtSignal(list)
    protagonist_toggled = pyqtSignal(int, bool)
    total_runtime_changed = pyqtSignal(int)
    toggle_favorite_requested = pyqtSignal(str, str) # tag_name, tag_type
    
    # Thematic Tags
    thematic_search_changed = pyqtSignal(str)
    thematic_filter_requested = pyqtSignal()
    add_thematic_tags_requested = pyqtSignal(list)
    remove_thematic_tags_requested = pyqtSignal(list)
    
    # Physical Tags
    physical_search_changed = pyqtSignal(str)
    physical_filter_requested = pyqtSignal()
    add_physical_tags_requested = pyqtSignal(list)
    remove_physical_tags_requested = pyqtSignal(list)
    selected_physical_tag_changed = pyqtSignal(object) # QListWidgetItem or None
    physical_tag_assignment_changed = pyqtSignal(str, int, bool) # tag_name, vp_id, is_checked
    
    # Action Tags
    action_search_changed = pyqtSignal(str)
    action_filter_requested = pyqtSignal()
    add_action_segments_requested = pyqtSignal(list)
    remove_action_segments_requested = pyqtSignal(list)
    selected_action_segment_changed = pyqtSignal(object) # QListWidgetItem or None
    segment_runtime_changed = pyqtSignal(int, int) # segment_id, new_value
    segment_parameter_changed = pyqtSignal(int, str, int) # segment_id, role, new_value
    slot_assignment_changed = pyqtSignal(int, str, object) # segment_id, slot_id, vp_id or None
    hire_for_role_requested = pyqtSignal(int) # vp_id

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.presenter = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.available_ethnicities = self.controller.get_available_ethnicities()
        self.viewer_groups = [group['name'] for group in self.controller.market_data.get('viewer_groups', [])]
        
        self.setWindowTitle("Scene Planner")
        self.defaultSize = QSize(1366, 768)

        # Makes the dialog's window work with the snap layout features
        # and gives it maximize and minimize buttons
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowMinMaxButtonsHint | 
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setup_ui()
        self._connect_signals()
        self._restore_geometry()
    
        QTimer.singleShot(0, self.view_loaded.emit)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()
        help_btn = HelpButton("scene_planner", self)
        help_btn.help_requested.connect(self.controller.signals.show_help_requested)
        header_layout.addWidget(help_btn, 0)
        self.bloc_info_label = QLabel()
        font = self.bloc_info_label.font(); font.setItalic(True); self.bloc_info_label.setFont(font)
        header_layout.addWidget(self.bloc_info_label, 1)
        header_layout.addStretch()
        self.view_toggle_btn = QPushButton("View Summary")
        header_layout.addWidget(self.view_toggle_btn, 0)
        main_layout.addLayout(header_layout)

        self.main_stack = QStackedWidget()
        main_layout.addWidget(self.main_stack)
        
        # Page 0: Editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0,0,0,0)
        editor_layout.addWidget(self._create_overview_group(), 1)
        editor_layout.addWidget(self._create_composition_group(), 5)
        editor_layout.addWidget(self._create_content_design_group(), 7)
        self.main_stack.addWidget(editor_widget)
        
        # Page 1: Summary
        self.summary_widget = SceneSummaryWidget()
        self.main_stack.addWidget(self.summary_widget)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(10)
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Design", "Casting", "Scheduled"])
        item = self.status_combo.model().item(self.status_combo.findText("Scheduled"))
        if item: item.setEnabled(False)
        self.total_runtime_spinbox = QSpinBox(); self.total_runtime_spinbox.setRange(1, 240); self.total_runtime_spinbox.setSuffix(" min")
        bottom_layout.addWidget(QLabel("Total Runtime:")); bottom_layout.addWidget(self.total_runtime_spinbox)
        bottom_layout.addWidget(QLabel("Status:"))
        bottom_layout.addWidget(self.status_combo)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.delete_button = self.button_box.addButton("Delete Scene", QDialogButtonBox.ButtonRole.DestructiveRole)
        bottom_layout.addWidget(self.button_box, 3)
        main_layout.addLayout(bottom_layout)

    def _create_overview_group(self):
        container = QWidget(); top_layout = QHBoxLayout(container)
        details_layout = QHBoxLayout(); self.title_edit = QLineEdit(); 
        self.focus_target_combo = QComboBox(); self.focus_target_combo.addItems(self.viewer_groups)
        details_layout.addWidget(QLabel("Title:")); details_layout.addWidget(self.title_edit)
        details_layout.addWidget(QLabel("Focus Target:")); details_layout.addWidget(self.focus_target_combo)
        top_layout.addLayout(details_layout)
        return container

    def _create_composition_group(self):
        self.composition_container = QWidget()
        comp_layout = QVBoxLayout(self.composition_container)
        perf_layout = QHBoxLayout()
        perf_layout.addWidget(QLabel("Number of Performers:"))
        self.performer_count_spinbox = QSpinBox(); self.performer_count_spinbox.setRange(1, 40) 
        perf_layout.addWidget(self.performer_count_spinbox)
        perf_layout.addWidget(QLabel("Dom/Sub Dynamic Level:"))
        self.ds_level_spinbox = QSpinBox(); self.ds_level_spinbox.setRange(0, 3)
        perf_layout.addWidget(self.ds_level_spinbox)
        perf_layout.addStretch()
        comp_layout.addLayout(perf_layout)
        self.performer_editors_layout = QVBoxLayout(); self.performer_editors_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_content_widget = QWidget(); scroll_content_widget.setLayout(self.performer_editors_layout)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setWidget(scroll_content_widget)
        comp_layout.addWidget(scroll_area)
        return self.composition_container

    def _create_content_design_group(self):
        tags_widget = QWidget(); main_layout = QVBoxLayout(tags_widget)
        
        self.content_tabs = QTabWidget()
        self.content_tabs.addTab(self._create_thematic_panel(), "Thematic Tags")
        self.content_tabs.addTab(self._create_physical_panel(), "Physical Tags")
        self.content_tabs.addTab(self._create_action_panel(), "Action Segments")
        main_layout.addWidget(self.content_tabs)
        return tags_widget

    def _create_thematic_panel(self) -> QWidget:
        panel = QWidget(); layout = QHBoxLayout(panel)
        # Available
        available_col = QVBoxLayout(); available_col.addWidget(QLabel("<h3>Available Thematic Tags</h3>"))
        self.thematic_search_input = QLineEdit(placeholderText="Search themes..."); available_col.addWidget(self.thematic_search_input)
        self.thematic_filter_btn = QPushButton("Advanced Filter..."); available_col.addWidget(self.thematic_filter_btn)
        self.available_thematic_list = DraggableListWidget()
        self.available_thematic_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_col.addWidget(self.available_thematic_list)
        # Add/Remove
        add_remove_col = QVBoxLayout(); add_remove_col.addStretch()
        self.add_thematic_btn = QPushButton("Add >>"); self.remove_thematic_btn = QPushButton("<< Remove")
        add_remove_col.addWidget(self.add_thematic_btn); add_remove_col.addWidget(self.remove_thematic_btn); add_remove_col.addStretch()
        # Selected
        selected_col = QVBoxLayout(); selected_col.addWidget(QLabel("<h3>Selected Themes</h3>"))
        self.selected_thematic_list = DropEnabledListWidget()
        self.selected_thematic_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        selected_col.addWidget(self.selected_thematic_list)
        layout.addLayout(available_col, 1); layout.addLayout(add_remove_col); layout.addLayout(selected_col, 1)
        return panel

    def _create_physical_panel(self) -> QWidget:
        panel = QWidget(); layout = QHBoxLayout(panel)
        # Available
        available_col = QVBoxLayout(); available_col.addWidget(QLabel("<h3>Available Physical Tags</h3>"))
        self.physical_search_input = QLineEdit(placeholderText="Search tags..."); available_col.addWidget(self.physical_search_input)
        self.physical_filter_btn = QPushButton("Advanced Filter..."); available_col.addWidget(self.physical_filter_btn)
        self.available_physical_list = DraggableListWidget()
        self.available_physical_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_col.addWidget(self.available_physical_list)
        # Add/Remove
        add_remove_col = QVBoxLayout(); add_remove_col.addStretch()
        self.add_physical_btn = QPushButton("Add >>"); self.remove_physical_btn = QPushButton("<< Remove")
        add_remove_col.addWidget(self.add_physical_btn); add_remove_col.addWidget(self.remove_physical_btn); add_remove_col.addStretch()
        # Selected
        selected_col = QVBoxLayout(); selected_col.addWidget(QLabel("<h3>Selected Tags</h3>"))
        self.selected_physical_list = DropEnabledListWidget()
        self.selected_physical_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        selected_col.addWidget(self.selected_physical_list)
        # Assignment
        assignment_col_layout = QVBoxLayout(); assignment_col_layout.addWidget(QLabel("<h3>Assignments</h3>"))
        self.physical_assignment_group = QGroupBox("Assign to Performer(s)")
        self.physical_assignment_layout = QVBoxLayout(self.physical_assignment_group); self.physical_assignment_group.setVisible(False)
        assignment_col_layout.addWidget(self.physical_assignment_group); assignment_col_layout.addStretch()
        layout.addLayout(available_col, 3); layout.addLayout(add_remove_col, 1); layout.addLayout(selected_col, 3); layout.addLayout(assignment_col_layout, 4)
        return panel

    def _create_action_panel(self) -> QWidget:
        panel = QWidget(); layout = QHBoxLayout(panel)
        # Available
        available_actions_col = QVBoxLayout(); available_actions_col.addWidget(QLabel("<h3>Available Actions</h3>"))
        self.action_search_input = QLineEdit(placeholderText="Search actions..."); available_actions_col.addWidget(self.action_search_input)
        self.action_filter_btn = QPushButton("Advanced Filter..."); available_actions_col.addWidget(self.action_filter_btn)
        self.available_actions_list = DraggableListWidget()
        self.available_actions_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        available_actions_col.addWidget(self.available_actions_list)
        # Add/Remove
        add_remove_actions_col = QVBoxLayout(); add_remove_actions_col.addStretch()
        self.add_action_btn = QPushButton("Add >>"); self.remove_action_btn = QPushButton("<< Remove")
        add_remove_actions_col.addWidget(self.add_action_btn); add_remove_actions_col.addWidget(self.remove_action_btn); add_remove_actions_col.addStretch()
        # Selected
        selected_actions_col = QVBoxLayout(); selected_actions_col.addWidget(QLabel("<h3>Action Segments</h3>"))
        self.selected_actions_list = DropEnabledListWidget()
        self.selected_actions_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        selected_actions_col.addWidget(self.selected_actions_list)
        self.total_percent_label = QLabel("<b>Total Assigned: 0%</b>"); self.total_percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        selected_actions_col.addWidget(self.total_percent_label)
        # Details
        details_col = QVBoxLayout(); details_col.addWidget(QLabel("<h3>Segment Details</h3>"))
        self.segment_stack = QStackedWidget(); placeholder = QLabel("Select a segment to edit its details."); placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); self.segment_stack.addWidget(placeholder)
        self.segment_detail_widget = QWidget(); segment_detail_layout = QVBoxLayout(self.segment_detail_widget); self.segment_title_label = QLabel(); segment_detail_layout.addWidget(self.segment_title_label)
        runtime_percent_layout = QHBoxLayout(); runtime_percent_layout.addWidget(QLabel("Runtime Percentage:")); self.runtime_percent_spinbox = QSpinBox(); self.runtime_percent_spinbox.setRange(1, 100); self.runtime_percent_spinbox.setSuffix("%")
        runtime_percent_layout.addWidget(self.runtime_percent_spinbox); runtime_percent_layout.addStretch(); segment_detail_layout.addLayout(runtime_percent_layout)
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); self.slots_widget = QWidget(); self.slots_layout = QVBoxLayout(self.slots_widget); self.slots_layout.setAlignment(Qt.AlignmentFlag.AlignTop); scroll_area.setWidget(self.slots_widget); segment_detail_layout.addWidget(scroll_area)
        self.segment_stack.addWidget(self.segment_detail_widget); details_col.addWidget(self.segment_stack)
        layout.addLayout(available_actions_col, 5); layout.addLayout(add_remove_actions_col, 1); layout.addLayout(selected_actions_col, 10); layout.addLayout(details_col, 7)
        return panel

    def _connect_signals(self):
        # --- General ---
        self.title_edit.textChanged.connect(self.title_changed)
        self.focus_target_combo.currentTextChanged.connect(self.focus_target_changed)
        self.total_runtime_spinbox.valueChanged.connect(self.total_runtime_changed)
        self.status_combo.currentTextChanged.connect(self.status_changed)
        self.ds_level_spinbox.valueChanged.connect(self.ds_level_changed)
        self.button_box.accepted.connect(self.save_requested); self.button_box.rejected.connect(self.cancel_requested)
        self.view_toggle_btn.clicked.connect(self._toggle_view)
        self.delete_button.clicked.connect(self.handle_delete_scene)

        # --- Composition ---
        self.composition_update_timer = QTimer(self); self.composition_update_timer.setSingleShot(True); self.composition_update_timer.setInterval(300)
        self.composition_update_timer.timeout.connect(self._emit_composition_change)
        self.performer_count_spinbox.valueChanged.connect(self.performer_count_changed)
        
        # --- Thematic ---
        self.thematic_search_input.textChanged.connect(self.thematic_search_changed)
        self.thematic_filter_btn.clicked.connect(self.thematic_filter_requested)
        self.add_thematic_btn.clicked.connect(lambda: self.add_thematic_tags_requested.emit([item.text() for item in self.available_thematic_list.selectedItems()]))
        self.remove_thematic_btn.clicked.connect(lambda: self.remove_thematic_tags_requested.emit([item.text() for item in self.selected_thematic_list.selectedItems()]))
        # Add by double click or drop
        self.available_thematic_list.itemDoubleClicked.connect(lambda item: self.add_thematic_tags_requested.emit([item.text()]))
        self.selected_thematic_list.item_dropped.connect(lambda text: self.add_thematic_tags_requested.emit([text]))
        # Remove by keypress, double click, or drop
        self.selected_thematic_list.item_delete_requested.connect(lambda: self.remove_thematic_tags_requested.emit([self.selected_thematic_list.currentItem().text()]) if self.selected_thematic_list.currentItem() else None)
        self.selected_thematic_list.itemDoubleClicked.connect(lambda item: self.remove_thematic_tags_requested.emit([item.text()]))
        self.available_thematic_list.item_dropped.connect(lambda text: self.remove_thematic_tags_requested.emit([text]))
        
        # --- Physical ---
        self.physical_search_input.textChanged.connect(self.physical_search_changed)
        self.physical_filter_btn.clicked.connect(self.physical_filter_requested)
        self.add_physical_btn.clicked.connect(lambda: self.add_physical_tags_requested.emit([item.text() for item in self.available_physical_list.selectedItems()]))
        self.remove_physical_btn.clicked.connect(lambda: self.remove_physical_tags_requested.emit([item.text() for item in self.selected_physical_list.selectedItems()]))
        # Add by double click or drop
        self.available_physical_list.itemDoubleClicked.connect(lambda item: self.add_physical_tags_requested.emit([item.text()]))
        self.selected_physical_list.item_dropped.connect(lambda text: self.add_physical_tags_requested.emit([text]))
        # Remove by keypress, double click, or drop
        self.selected_physical_list.item_delete_requested.connect(lambda: self.remove_physical_tags_requested.emit([self.selected_physical_list.currentItem().text()]) if self.selected_physical_list.currentItem() else None)
        self.selected_physical_list.itemDoubleClicked.connect(lambda item: self.remove_physical_tags_requested.emit([item.text()]))
        self.available_physical_list.item_dropped.connect(lambda text: self.remove_physical_tags_requested.emit([text]))
        self.selected_physical_list.currentItemChanged.connect(lambda current, _: self.selected_physical_tag_changed.emit(current))
        
        # --- Action ---
        self.action_search_input.textChanged.connect(self.action_search_changed)
        self.action_filter_btn.clicked.connect(self.action_filter_requested)
        self.add_action_btn.clicked.connect(lambda: self.add_action_segments_requested.emit([item.text() for item in self.available_actions_list.selectedItems()]))
        self.remove_action_btn.clicked.connect(lambda: self.remove_action_segments_requested.emit([item.data(Qt.ItemDataRole.UserRole) for item in self.selected_actions_list.selectedItems()]))
        # Add by double click or drop
        self.available_actions_list.itemDoubleClicked.connect(lambda item: self.add_action_segments_requested.emit([item.text()]))
        self.selected_actions_list.item_dropped.connect(lambda text: self.add_action_segments_requested.emit([text]))
        # Remove by keypress, double click, or drop
        self.selected_actions_list.item_delete_requested.connect(lambda: self.remove_action_segments_requested.emit([self.selected_actions_list.currentItem().data(Qt.ItemDataRole.UserRole)]) if self.selected_actions_list.currentItem() else None)
        self.selected_actions_list.itemDoubleClicked.connect(lambda item: self.remove_action_segments_requested.emit([item.data(Qt.ItemDataRole.UserRole)]))
        self.available_actions_list.item_dropped.connect(lambda text: self.remove_action_segments_requested.emit([int(text)]))
        self.selected_actions_list.currentItemChanged.connect(lambda current, _: self.selected_action_segment_changed.emit(current))
        self.runtime_percent_spinbox.valueChanged.connect(self._emit_segment_runtime_change)
        
        # --- Context Menus for Favorites ---
        for list_widget, tag_type in [(self.available_thematic_list, 'thematic'), (self.selected_thematic_list, 'thematic'),
                                     (self.available_physical_list, 'physical'), (self.selected_physical_list, 'physical'),
                                     (self.available_actions_list, 'action'), (self.selected_actions_list, 'action')]:
            list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(lambda pos, lw=list_widget, tt=tag_type: self._show_tag_context_menu(lw, pos, tt))

    # --- Public Update Methods ---
    def update_summary_view(self, summary_data: dict):
        """Passes summary data to the summary widget."""
        self.summary_widget.update_summary(summary_data)
    def update_general_info(self, title: str, status: str, focus_target: str, runtime: int, ds_level: int, bloc_text: str):
        for w in [self.title_edit, self.status_combo, self.focus_target_combo, self.total_runtime_spinbox, self.ds_level_spinbox]: w.blockSignals(True)
        self.title_edit.setText(title)
        self.status_combo.setCurrentText(status.title())
        self.focus_target_combo.setCurrentText(focus_target)
        self.total_runtime_spinbox.setValue(runtime)
        self.ds_level_spinbox.setValue(ds_level)
        self.bloc_info_label.setText(bloc_text if bloc_text else "")
        for w in [self.title_edit, self.status_combo, self.focus_target_combo, self.total_runtime_spinbox, self.ds_level_spinbox]: w.blockSignals(False)

    def update_performer_editors(self, performers_with_talent: List[Dict], ds_level: int, protagonist_ids: List[int], is_casting_enabled: bool, is_design_editable: bool):
        self.performer_count_spinbox.blockSignals(True); self.performer_count_spinbox.setValue(len(performers_with_talent)); self.performer_count_spinbox.blockSignals(False)
        while self.performer_editors_layout.count():
            child = self.performer_editors_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for i, data in enumerate(performers_with_talent):
            row_widget = QWidget(); h_layout = QHBoxLayout(row_widget); h_layout.setContentsMargins(0, 2, 0, 2)
            name_edit = QLineEdit(data['display_name']); gender_combo = QComboBox(); gender_combo.addItems(["Female", "Male"])
            ethnicity_combo = QComboBox(); ethnicity_combo.addItem("Any"); ethnicity_combo.addItems(self.available_ethnicities)
            disposition_combo = QComboBox(); disposition_combo.addItems(["Switch", "Dom", "Sub"])
            protagonist_checkbox = QCheckBox("Protagonist"); protagonist_checkbox.setToolTip("The talent's performance will have a bigger importance in the scene relative to non-protagonists")
            gender_combo.setCurrentText(data['gender']); ethnicity_combo.setCurrentText(data['ethnicity']); disposition_combo.setCurrentText(data['disposition'])
            protagonist_checkbox.setChecked(data['vp_id'] in protagonist_ids)
            if data['is_cast']: name_edit.setToolTip(f"Playing the role of '{data['vp_name']}'")
            is_role_uncast = not data['is_cast']
            is_role_editable = is_role_uncast and is_design_editable
            hire_button = QPushButton("Hire")
            hire_button.clicked.connect(lambda checked=False, vp_id=data['vp_id']: self.hire_for_role_requested.emit(vp_id))
            hire_button.setEnabled(is_casting_enabled and is_role_uncast)
            
            h_layout.addWidget(QLabel(f"{i+1}:")); h_layout.addWidget(name_edit); h_layout.addWidget(QLabel("Gender:")); h_layout.addWidget(gender_combo)
            h_layout.addWidget(QLabel("Ethnicity:")); h_layout.addWidget(ethnicity_combo); h_layout.addWidget(QLabel("Disposition:")); h_layout.addWidget(disposition_combo)
            h_layout.addWidget(protagonist_checkbox); h_layout.addStretch(); h_layout.addWidget(hire_button)
            name_edit.setEnabled(is_role_editable); gender_combo.setEnabled(is_role_editable); ethnicity_combo.setEnabled(is_role_editable); disposition_combo.setEnabled(ds_level > 0 and is_role_editable); protagonist_checkbox.setEnabled(is_role_editable)
            protagonist_checkbox.toggled.connect(lambda checked, vid=data['vp_id']: self.protagonist_toggled.emit(vid, checked))
            for w in [name_edit, gender_combo, ethnicity_combo, disposition_combo]: w.installEventFilter(self); w.setProperty("editor_widget", True)
            self.performer_editors_layout.addWidget(row_widget)

    def update_available_thematic_tags(self, tags: List[Dict]):
        self.available_thematic_list.clear()
        for tag_data in tags: self.available_thematic_list.addItem(self._create_list_item_with_tooltip(tag_data))

    def update_selected_thematic_tags(self, selected_tags_data: List[Dict]):
        self.selected_thematic_list.clear()
        for tag_data in selected_tags_data: self.selected_thematic_list.addItem(self._create_list_item_with_tooltip(tag_data))

    def update_available_physical_tags(self, tags: List[Dict]):
        self.available_physical_list.clear()
        for tag_data in tags: self.available_physical_list.addItem(self._create_list_item_with_tooltip(tag_data))

    def update_selected_physical_tags(self, selected_tags_data: List[Dict], selection_name: str):
        self.selected_physical_list.clear()
        new_current_item = None
        for tag_data in selected_tags_data:
            item = self._create_list_item_with_tooltip(tag_data)
            self.selected_physical_list.addItem(item)
            if tag_data['full_name'] == selection_name: new_current_item = item
        if new_current_item: self.selected_physical_list.setCurrentItem(new_current_item)
            
    def update_physical_assignment_panel(self, tag_data: Optional[Dict], eligible_performers: List[Dict], assigned_vp_ids: List[int], is_editable: bool):
        while self.physical_assignment_layout.count():
            child = self.physical_assignment_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not tag_data: self.physical_assignment_group.setVisible(False); return

        self.physical_assignment_group.setVisible(True)
        tag_name = tag_data['full_name']

        if not eligible_performers:
            label = QLabel("No performer fulfills the requirements for the selected tag.")
            label.setWordWrap(True)
            self.physical_assignment_layout.addWidget(label)
        else:
            for p_data in eligible_performers:
                checkbox = QCheckBox(p_data['display_name'])
                checkbox.setChecked(p_data['vp_id'] in assigned_vp_ids)
                checkbox.setEnabled(is_editable)
                checkbox.toggled.connect(lambda checked, tn=tag_name, vid=p_data['vp_id']: self.physical_tag_assignment_changed.emit(tn, vid, checked))
                self.physical_assignment_layout.addWidget(checkbox)

    def update_available_action_tags(self, tags: List[Dict]):
        self.available_actions_list.clear()
        for tag_data in tags: self.available_actions_list.addItem(self._create_list_item_with_tooltip(tag_data))

    def update_selected_action_segments(self, segments: List[ActionSegment], tag_defs: Dict, selection_id: Optional[int]):
        self.selected_actions_list.blockSignals(True)
        self.selected_actions_list.clear()
        total_percent = 0; new_selection_index = -1
        for i, segment in enumerate(segments):
            tag_def = tag_defs.get(segment.tag_name)
            item = QListWidgetItem(); item.setData(Qt.ItemDataRole.UserRole, segment.id)
            self.selected_actions_list.addItem(item)
            if tag_def and tag_def.get("is_template"):
                widget = ActionSegmentItemWidget(segment, tag_def)
                widget.parameter_changed.connect(self.segment_parameter_changed)
                item.setSizeHint(widget.sizeHint())
                self.selected_actions_list.setItemWidget(item, widget)
            else: item.setText(f"{segment.tag_name} ({segment.runtime_percentage}%)")
            total_percent += segment.runtime_percentage
            if segment.id == selection_id: new_selection_index = i
        self.total_percent_label.setText(f"<b>Total Assigned: {total_percent}%</b>")
        self.total_percent_label.setStyleSheet("color: red;" if total_percent > 100 else "")
        self.selected_actions_list.blockSignals(False)
        if new_selection_index != -1: self.selected_actions_list.setCurrentRow(new_selection_index)
        elif self.selected_actions_list.count() > 0: self.selected_actions_list.setCurrentRow(0)

    def update_segment_details(self, segment: Optional[ActionSegment], tag_defs: Dict, vp_options_by_slot: Dict[str, List[tuple]], is_editable: bool):
        if not segment: self.segment_stack.setCurrentIndex(0); return
        self.segment_stack.setCurrentIndex(1)
        self.segment_title_label.setText(f"<h3>Editing: {segment.tag_name}</h3>")
        self.runtime_percent_spinbox.blockSignals(True); self.runtime_percent_spinbox.setValue(segment.runtime_percentage); self.runtime_percent_spinbox.setEnabled(is_editable); self.runtime_percent_spinbox.blockSignals(False)
        while self.slots_layout.count():
            child = self.slots_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not (tag_def := tag_defs.get(segment.tag_name)): return
        assignments_map = {sa.slot_id: sa.virtual_performer_id for sa in segment.slot_assignments}
        for slot_def in tag_def.get('slots', []):
            count = segment.parameters.get(slot_def['role']) if slot_def.get("parameterized_by") == "count" else slot_def.get('count', 1)
            for i in range(count):
                base_name = tag_def.get('name', segment.tag_name)
                slot_id = f"{base_name}_{slot_def['role']}_{i+1}"
                slot_widget = SlotAssignmentWidget(segment.id, slot_id, slot_def)
                slot_widget.assignment_changed.connect(self.slot_assignment_changed)
                slot_widget.setEnabled(is_editable)
                widget_options = vp_options_by_slot.get(slot_id, [])
                current_vp = assignments_map.get(slot_id)
                slot_widget.update_options(widget_options, current_vp)
                self.slots_layout.addWidget(slot_widget)
            
    def set_ui_lock_state(self, is_editable: bool, is_cast_locked: bool):
        self.status_combo.setEnabled(not is_cast_locked)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Close" if is_cast_locked else "OK")
        widgets_to_toggle = [self.title_edit, self.delete_button, self.total_runtime_spinbox,
                             self.focus_target_combo, self.performer_count_spinbox, self.ds_level_spinbox, self.content_tabs]
        for widget in widgets_to_toggle: widget.setEnabled(is_editable)
        self.runtime_percent_spinbox.setEnabled(is_editable)
        for i in range(self.slots_layout.count()):
            if widget := self.slots_layout.itemAt(i).widget(): widget.setEnabled(is_editable)
        for i in range(self.physical_assignment_layout.count()):
            if widget := self.physical_assignment_layout.itemAt(i).widget(): widget.setEnabled(is_editable)

    def flush_pending_composition_changes(self):
        """Immediately stops the update timer and emits any pending composition changes."""
        if self.composition_update_timer.isActive():
            self.composition_update_timer.stop()
            self._emit_composition_change()
    # --- Private Helpers ---
    def _create_list_item_with_tooltip(self, tag_data: dict) -> QListWidgetItem:
        item = QListWidgetItem(tag_data['full_name']); item.setData(Qt.ItemDataRole.UserRole, tag_data)
        if tooltip := tag_data.get("tooltip"): item.setToolTip(tooltip)
        return item

    def _toggle_view(self):
        current_index = self.main_stack.currentIndex()
        if current_index == 0:
            self.main_stack.setCurrentIndex(1)
            self.view_toggle_btn.setText("Edit Scene")
        else:
            self.main_stack.setCurrentIndex(0)
            self.view_toggle_btn.setText("View Summary")

    def _show_tag_context_menu(self, list_widget: QListWidget, pos: QPoint, tag_type: str):
        item = list_widget.itemAt(pos)
        if not item: return
        tag_name = ""
        if list_widget is self.selected_actions_list:
            widget = self.selected_actions_list.itemWidget(item)
            if isinstance(widget, ActionSegmentItemWidget): tag_name = widget.segment.tag_name
        else: tag_name = item.text()
        if not tag_name: return
        menu = QMenu(self); fav_action = menu.addAction("Toggle Favorite")
        if menu.exec(list_widget.mapToGlobal(pos)) == fav_action: self.toggle_favorite_requested.emit(tag_name, tag_type)

    def eventFilter(self, source, event):
        if source.property("editor_widget") and (isinstance(event, QKeyEvent) or event.type() in [event.Type.FocusOut]): self.composition_update_timer.start()
        return super().eventFilter(source, event)

    def _emit_composition_change(self):
        performers_data = []
        for i in range(self.performer_editors_layout.count()):
            row_widget = self.performer_editors_layout.itemAt(i).widget()
            name_edit, combos = row_widget.findChild(QLineEdit), row_widget.findChildren(QComboBox)
            if name_edit and len(combos) == 3:
                performers_data.append({"name": name_edit.text(), "gender": combos[0].currentText(), "ethnicity": combos[1].currentText(), "disposition": combos[2].currentText()})
        self.composition_changed.emit(performers_data)
        
    def _emit_segment_runtime_change(self, value: int):
        if item := self.selected_actions_list.currentItem():
            self.segment_runtime_changed.emit(item.data(Qt.ItemDataRole.UserRole), value)

    def handle_delete_scene(self):
        reply = QMessageBox.question(self, 'Confirm Deletion', "Are you sure you want to permanently delete this scene?\nThis action cannot be undone.", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.delete_requested.emit(0.0)