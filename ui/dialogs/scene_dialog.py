from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QDialogButtonBox, QSpinBox, QGroupBox, QWidget,
    QScrollArea, QFormLayout, QStackedWidget, QCheckBox, QMessageBox, QMenu, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QMimeData, QPoint
from PyQt6.QtGui import QDrag, QKeyEvent, QFont

from game_state import Scene, ActionSegment
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None): super().__init__(parent); self.setDragEnabled(True)
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item:
            mime_data = QMimeData(); mime_data.setText(item.text()); drag = QDrag(self)
            drag.setMimeData(mime_data); drag.exec(Qt.DropAction.CopyAction)

class DropEnabledListWidget(QListWidget):
    item_dropped = pyqtSignal(str)
    item_delete_requested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.setDropIndicatorShown(True)
    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
    def dragMoveEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
    def dropEvent(self, event):
        if event.mimeData().hasText(): self.item_dropped.emit(event.mimeData().text()); event.acceptProposedAction()
        else: super().dropEvent(event)
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Delete and self.currentItem(): self.item_delete_requested.emit()
        else: super().keyPressEvent(event)

class ActionSegmentItemWidget(QWidget):
    parameter_changed = pyqtSignal(int, str, int)
    def __init__(self, segment: ActionSegment, tag_def: dict, parent=None):
        super().__init__(parent); self.segment = segment; self.tag_def = tag_def
        self.setup_ui()
    def setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(4, 2, 4, 2)
        param_text = []
        for role, value in self.segment.parameters.items():
            param_text.append(f"{value} {role}(s)")
        label_text = f"{self.segment.tag_name} ({self.segment.runtime_percentage}%)"
        if param_text: label_text += f" [{', '.join(param_text)}]"
        layout.addWidget(QLabel(label_text), 1)
        for slot in self.tag_def.get("slots", []):
            if "parameterized_by" in slot and slot["parameterized_by"] == "count":
                role = slot['role']; spinbox = QSpinBox()
                spinbox.setRange(slot.get('min_count', 1), slot.get('max_count', 10))
                spinbox.setValue(self.segment.parameters.get(role, 1))
                spinbox.valueChanged.connect(lambda val, r=role: self.parameter_changed.emit(self.segment.id, r, val))
                layout.addWidget(QLabel(f"{role}s:"))
                layout.addWidget(spinbox)

class SlotAssignmentWidget(QWidget):
    assignment_changed = pyqtSignal(int, str, object) # object allows for None
    def __init__(self, segment_id: int, slot_id: str, slot_def: dict, parent=None):
        super().__init__(parent)
        self.segment_id = segment_id; self.slot_id = slot_id; self.slot_def = slot_def
        self.setup_ui()
    def setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 5, 0, 5)
        label_text = f"<b>{self.slot_def['role']}</b> (Requires: {self.slot_def['gender']})"
        layout.addWidget(QLabel(label_text)); self.performer_combo = QComboBox(); layout.addWidget(self.performer_combo)
        self.performer_combo.currentIndexChanged.connect(self._on_selection_change)

    def update_options(self, options: List[tuple], current_vp_id: Optional[int]):
        self.performer_combo.blockSignals(True)
        self.performer_combo.clear()
        self.performer_combo.addItem("Unassigned", -1)
        for display_name, vp_id in options:
            self.performer_combo.addItem(display_name, vp_id)

        index = self.performer_combo.findData(current_vp_id)
        self.performer_combo.setCurrentIndex(index if index != -1 else 0)
        self.performer_combo.blockSignals(False)

    def _on_selection_change(self):
        vp_id = self.performer_combo.currentData()
        self.assignment_changed.emit(self.segment_id, self.slot_id, vp_id if vp_id != -1 else None)
    
class SceneDialog(GeometryManagerMixin, QDialog):
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
    total_runtime_changed = pyqtSignal(int)
    toggle_favorite_requested = pyqtSignal(str, str) # tag_name, tag_type
    
    # Thematic Tags
    thematic_search_changed = pyqtSignal(str)
    thematic_filter_requested = pyqtSignal()
    add_thematic_tag_requested = pyqtSignal(str)
    remove_thematic_tag_requested = pyqtSignal(str)
    
    # Physical Tags
    physical_search_changed = pyqtSignal(str)
    physical_filter_requested = pyqtSignal()
    add_physical_tag_requested = pyqtSignal(str)
    remove_physical_tag_requested = pyqtSignal(str)
    selected_physical_tag_changed = pyqtSignal(object) # QListWidgetItem or None
    physical_tag_assignment_changed = pyqtSignal(str, int, bool) # tag_name, vp_id, is_checked
    
    # Action Tags
    action_search_changed = pyqtSignal(str)
    action_filter_requested = pyqtSignal()
    add_action_segment_requested = pyqtSignal(str)
    remove_action_segment_requested = pyqtSignal(int)
    selected_action_segment_changed = pyqtSignal(object) # QListWidgetItem or None
    segment_runtime_changed = pyqtSignal(int, int) # segment_id, new_value
    segment_parameter_changed = pyqtSignal(int, str, int) # segment_id, role, new_value
    slot_assignment_changed = pyqtSignal(int, str, object) # segment_id, slot_id, vp_id or None

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.available_ethnicities = self.controller.get_available_ethnicities()
        self.viewer_groups = [group['name'] for group in self.controller.market_data.get('viewer_groups', [])]
        
        self.setWindowTitle("Scene Planner")
        self.setMinimumSize(1366, 768)

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
        self.bloc_info_label = QLabel()
        font = self.bloc_info_label.font(); font.setItalic(True); self.bloc_info_label.setFont(font)
        main_layout.addWidget(self.bloc_info_label)
        main_layout.addWidget(self._create_overview_group(), 1)
        main_layout.addWidget(self._create_composition_group(), 3)
        main_layout.addWidget(self._create_content_design_group(), 5)
        
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
        group = QGroupBox("Scene Overview"); top_layout = QHBoxLayout(group)
        details_layout = QFormLayout(); self.title_edit = QLineEdit(); 
        self.focus_target_combo = QComboBox(); self.focus_target_combo.addItems(self.viewer_groups)
        details_layout.addRow("Title:", self.title_edit); details_layout.addRow("Focus Target:", self.focus_target_combo)
        top_layout.addLayout(details_layout)
        return group

    def _create_composition_group(self):
        self.composition_group = QGroupBox("Composition")
        comp_layout = QVBoxLayout(self.composition_group)
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
        return self.composition_group

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
        self.available_thematic_list = DraggableListWidget(); available_col.addWidget(self.available_thematic_list)
        # Add/Remove
        add_remove_col = QVBoxLayout(); add_remove_col.addStretch()
        self.add_thematic_btn = QPushButton("Add >>"); self.remove_thematic_btn = QPushButton("<< Remove")
        add_remove_col.addWidget(self.add_thematic_btn); add_remove_col.addWidget(self.remove_thematic_btn); add_remove_col.addStretch()
        # Selected
        selected_col = QVBoxLayout(); selected_col.addWidget(QLabel("<h3>Selected Themes</h3>"))
        self.selected_thematic_list = DropEnabledListWidget(); selected_col.addWidget(self.selected_thematic_list)
        layout.addLayout(available_col, 1); layout.addLayout(add_remove_col); layout.addLayout(selected_col, 1)
        return panel

    def _create_physical_panel(self) -> QWidget:
        panel = QWidget(); layout = QHBoxLayout(panel)
        # Available
        available_col = QVBoxLayout(); available_col.addWidget(QLabel("<h3>Available Physical Tags</h3>"))
        self.physical_search_input = QLineEdit(placeholderText="Search tags..."); available_col.addWidget(self.physical_search_input)
        self.physical_filter_btn = QPushButton("Advanced Filter..."); available_col.addWidget(self.physical_filter_btn)
        self.available_physical_list = DraggableListWidget(); available_col.addWidget(self.available_physical_list)
        # Add/Remove
        add_remove_col = QVBoxLayout(); add_remove_col.addStretch()
        self.add_physical_btn = QPushButton("Add >>"); self.remove_physical_btn = QPushButton("<< Remove")
        add_remove_col.addWidget(self.add_physical_btn); add_remove_col.addWidget(self.remove_physical_btn); add_remove_col.addStretch()
        # Selected
        selected_col = QVBoxLayout(); selected_col.addWidget(QLabel("<h3>Selected Tags</h3>"))
        self.selected_physical_list = DropEnabledListWidget(); selected_col.addWidget(self.selected_physical_list)
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
        self.available_actions_list = DraggableListWidget(); available_actions_col.addWidget(self.available_actions_list)
        # Add/Remove
        add_remove_actions_col = QVBoxLayout(); add_remove_actions_col.addStretch()
        self.add_action_btn = QPushButton("Add >>"); self.remove_action_btn = QPushButton("<< Remove")
        add_remove_actions_col.addWidget(self.add_action_btn); add_remove_actions_col.addWidget(self.remove_action_btn); add_remove_actions_col.addStretch()
        # Selected
        selected_actions_col = QVBoxLayout(); selected_actions_col.addWidget(QLabel("<h3>Action Segments</h3>"))
        self.selected_actions_list = DropEnabledListWidget(); selected_actions_col.addWidget(self.selected_actions_list)
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
        layout.addLayout(available_actions_col, 3); layout.addLayout(add_remove_actions_col, 1); layout.addLayout(selected_actions_col, 3); layout.addLayout(details_col, 4)
        return panel

    def _connect_signals(self):
        # General
        self.title_edit.textChanged.connect(self.title_changed)
        self.focus_target_combo.currentTextChanged.connect(self.focus_target_changed)
        self.total_runtime_spinbox.valueChanged.connect(self.total_runtime_changed)
        self.status_combo.currentTextChanged.connect(self.status_changed)
        self.ds_level_spinbox.valueChanged.connect(self.ds_level_changed)
        self.button_box.accepted.connect(self.save_requested); self.button_box.rejected.connect(self.cancel_requested)
        self.delete_button.clicked.connect(self.handle_delete_scene)
        # Composition
        self.composition_update_timer = QTimer(self); self.composition_update_timer.setSingleShot(True); self.composition_update_timer.setInterval(300)
        self.composition_update_timer.timeout.connect(self._emit_composition_change)
        self.performer_count_spinbox.valueChanged.connect(self.performer_count_changed)
        # Thematic
        self.thematic_search_input.textChanged.connect(self.thematic_search_changed)
        self.thematic_filter_btn.clicked.connect(self.thematic_filter_requested)
        self.add_thematic_btn.clicked.connect(lambda: self.add_thematic_tag_requested.emit(self.available_thematic_list.currentItem().text()) if self.available_thematic_list.currentItem() else None)
        self.remove_thematic_btn.clicked.connect(lambda: self.remove_thematic_tag_requested.emit(self.selected_thematic_list.currentItem().text()) if self.selected_thematic_list.currentItem() else None)
        self.available_thematic_list.itemDoubleClicked.connect(lambda item: self.add_thematic_tag_requested.emit(item.text()))
        self.selected_thematic_list.item_dropped.connect(self.add_thematic_tag_requested)
        self.selected_thematic_list.item_delete_requested.connect(lambda: self.remove_thematic_tag_requested.emit(self.selected_thematic_list.currentItem().text()) if self.selected_thematic_list.currentItem() else None)
        # Physical
        self.physical_search_input.textChanged.connect(self.physical_search_changed)
        self.physical_filter_btn.clicked.connect(self.physical_filter_requested)
        self.add_physical_btn.clicked.connect(lambda: self.add_physical_tag_requested.emit(self.available_physical_list.currentItem().text()) if self.available_physical_list.currentItem() else None)
        self.remove_physical_btn.clicked.connect(lambda: self.remove_physical_tag_requested.emit(self.selected_physical_list.currentItem().text()) if self.selected_physical_list.currentItem() else None)
        self.available_physical_list.itemDoubleClicked.connect(lambda item: self.add_physical_tag_requested.emit(item.text()))
        self.selected_physical_list.item_dropped.connect(self.add_physical_tag_requested)
        self.selected_physical_list.item_delete_requested.connect(lambda: self.remove_physical_tag_requested.emit(self.selected_physical_list.currentItem().text()) if self.selected_physical_list.currentItem() else None)
        self.selected_physical_list.currentItemChanged.connect(lambda current, _: self.selected_physical_tag_changed.emit(current))
        # Action
        self.action_search_input.textChanged.connect(self.action_search_changed)
        self.action_filter_btn.clicked.connect(self.action_filter_requested)
        self.add_action_btn.clicked.connect(lambda: self.add_action_segment_requested.emit(self.available_actions_list.currentItem().text()) if self.available_actions_list.currentItem() else None)
        self.remove_action_btn.clicked.connect(lambda: self.remove_action_segment_requested.emit(self.selected_actions_list.currentItem().data(Qt.ItemDataRole.UserRole)) if self.selected_actions_list.currentItem() else None)
        self.available_actions_list.itemDoubleClicked.connect(lambda item: self.add_action_segment_requested.emit(item.text()))
        self.selected_actions_list.item_dropped.connect(self.add_action_segment_requested)
        self.selected_actions_list.item_delete_requested.connect(lambda: self.remove_action_segment_requested.emit(self.selected_actions_list.currentItem().data(Qt.ItemDataRole.UserRole)) if self.selected_actions_list.currentItem() else None)
        self.selected_actions_list.currentItemChanged.connect(lambda current, _: self.selected_action_segment_changed.emit(current))
        self.runtime_percent_spinbox.valueChanged.connect(self._emit_segment_runtime_change)
        # Context Menus for Favorites
        for list_widget, tag_type in [(self.available_thematic_list, 'thematic'), (self.selected_thematic_list, 'thematic'),
                                     (self.available_physical_list, 'physical'), (self.selected_physical_list, 'physical'),
                                     (self.available_actions_list, 'action'), (self.selected_actions_list, 'action')]:
            list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(lambda pos, lw=list_widget, tt=tag_type: self._show_tag_context_menu(lw, pos, tt))

    # --- Public Update Methods ---
    def update_general_info(self, title: str, status: str, focus_target: str, runtime: int, ds_level: int, bloc_text: str):
        for w in [self.title_edit, self.status_combo, self.focus_target_combo, self.total_runtime_spinbox, self.ds_level_spinbox]: w.blockSignals(True)
        self.title_edit.setText(title)
        self.status_combo.setCurrentText(status.title())
        self.focus_target_combo.setCurrentText(focus_target)
        self.total_runtime_spinbox.setValue(runtime)
        self.ds_level_spinbox.setValue(ds_level)
        self.bloc_info_label.setText(bloc_text)
        for w in [self.title_edit, self.status_combo, self.focus_target_combo, self.total_runtime_spinbox, self.ds_level_spinbox]: w.blockSignals(False)

    def update_performer_editors(self, performers_with_talent: List[Dict], ds_level: int):
        self.performer_count_spinbox.blockSignals(True); self.performer_count_spinbox.setValue(len(performers_with_talent)); self.performer_count_spinbox.blockSignals(False)
        while self.performer_editors_layout.count():
            child = self.performer_editors_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for i, data in enumerate(performers_with_talent):
            row_widget = QWidget(); h_layout = QHBoxLayout(row_widget); h_layout.setContentsMargins(0, 2, 0, 2)
            name_edit = QLineEdit(data['display_name']); gender_combo = QComboBox(); gender_combo.addItems(["Female", "Male"])
            ethnicity_combo = QComboBox(); ethnicity_combo.addItems(self.available_ethnicities)
            disposition_combo = QComboBox(); disposition_combo.addItems(["Switch", "Dom", "Sub"])
            gender_combo.setCurrentText(data['gender']); ethnicity_combo.setCurrentText(data['ethnicity']); disposition_combo.setCurrentText(data['disposition'])
            if data['is_cast']: name_edit.setToolTip(f"Playing the role of '{data['vp_name']}'")
            h_layout.addWidget(QLabel(f"{i+1}:")); h_layout.addWidget(name_edit, 2); h_layout.addWidget(QLabel("Gender:")); h_layout.addWidget(gender_combo, 1)
            h_layout.addWidget(QLabel("Ethnicity:")); h_layout.addWidget(ethnicity_combo, 1); h_layout.addWidget(QLabel("Disposition:")); h_layout.addWidget(disposition_combo, 1)
            name_edit.setEnabled(not data['is_cast']); gender_combo.setEnabled(not data['is_cast']); ethnicity_combo.setEnabled(not data['is_cast']); disposition_combo.setEnabled(ds_level > 0)
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
            
    def update_physical_assignment_panel(self, tag_data: Optional[Dict], performers_with_talent: List[Dict], assigned_vp_ids: List[int], is_editable: bool):
        while self.physical_assignment_layout.count():
            child = self.physical_assignment_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not tag_data: self.physical_assignment_group.setVisible(False); return

        self.physical_assignment_group.setVisible(True)
        tag_name = tag_data['full_name']
        eligible_performers = []
        for p_data in performers_with_talent:
             gender_ok = not (req := tag_data.get('gender')) or req == "Any" or p_data['gender'] == req
             ethnicity_ok = not (req := tag_data.get('ethnicity')) or req == "Any" or p_data['ethnicity'] == req
             if gender_ok and ethnicity_ok:
                eligible_performers.append(p_data)

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
        widgets_to_toggle = [self.title_edit, self.delete_button, self.composition_group, self.total_runtime_spinbox, 
                             self.focus_target_combo, self.ds_level_spinbox, self.content_tabs, self.add_thematic_btn,
                             self.remove_thematic_btn, self.add_physical_btn, self.remove_physical_btn, 
                             self.add_action_btn, self.remove_action_btn]
        for widget in widgets_to_toggle: widget.setEnabled(is_editable)
        self.runtime_percent_spinbox.setEnabled(is_editable)
        for i in range(self.slots_layout.count()):
            if widget := self.slots_layout.itemAt(i).widget(): widget.setEnabled(is_editable)
        for i in range(self.physical_assignment_layout.count()):
            if widget := self.physical_assignment_layout.itemAt(i).widget(): widget.setEnabled(is_editable)

    # --- Private Helpers ---
    def _create_list_item_with_tooltip(self, tag_data: dict) -> QListWidgetItem:
        item = QListWidgetItem(tag_data['full_name']); item.setData(Qt.ItemDataRole.UserRole, tag_data)
        if tooltip := tag_data.get("tooltip"): item.setToolTip(tooltip)
        return item
        
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