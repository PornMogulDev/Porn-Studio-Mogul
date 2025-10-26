from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QStackedWidget, QLabel, QListWidget,
    QPushButton, QMenu, QMessageBox, QListWidgetItem
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal

class HiringWidget(QWidget):
    """A widget for assigning a talent to available roles."""
    hire_confirmed = pyqtSignal(list)  # roles_to_cast
    open_scene_dialog_requested = pyqtSignal(int)  # scene_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        contract_container = QGroupBox("Assign to Role")
        contract_layout = QVBoxLayout(contract_container)
        self.roles_stack = QStackedWidget()
        
        roles_list_widget = QWidget()
        roles_list_layout = QVBoxLayout(roles_list_widget)
        roles_list_layout.addWidget(QLabel("Available Roles (from scenes in 'casting'):"))
        self.available_roles_list = QListWidget()
        self.available_roles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.available_roles_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        roles_list_layout.addWidget(self.available_roles_list)
        
        roles_no_scenes_widget = QLabel("There are no uncast roles available for this talent.")
        roles_no_scenes_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        roles_no_scenes_widget.setWordWrap(True)
        
        self.roles_stack.addWidget(roles_list_widget)
        self.roles_stack.addWidget(roles_no_scenes_widget)
        contract_layout.addWidget(self.roles_stack)
        
        self.hire_button = QPushButton("Assign Talent to Selected Role(s)")
        contract_layout.addWidget(self.hire_button)
        
        main_layout.addWidget(contract_container)

    def _connect_signals(self):
        self.available_roles_list.itemDoubleClicked.connect(self._on_role_double_clicked)
        self.available_roles_list.customContextMenuRequested.connect(self._show_role_context_menu)
        self.hire_button.clicked.connect(self._confirm_hire)

    def update_available_roles(self, available_roles: list):
        self.available_roles_list.clear()

        if not available_roles:
            self.roles_stack.setCurrentIndex(1)
            return

        self.roles_stack.setCurrentIndex(0)
        for role_data in available_roles:
            tags_text = ""
            if tags := role_data.get('tags'):
                tags_to_show = tags[:3]
                if len(tags) > 3: tags_to_show.append("...")
                tags_text = f" (Tags: {', '.join(tags_to_show)})"

            display_text = f"{role_data['scene_title']} - Role: {role_data['vp_name']} (Cost: ${role_data['cost']:,}){tags_text}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, {'scene_id': role_data['scene_id'], 'virtual_performer_id': role_data['virtual_performer_id'], 'cost': role_data['cost']})
            
            if not role_data['is_available']:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor("gray"))
                item.setToolTip(f"Unavailable: {role_data['refusal_reason']}")
            elif tags:
                item.setToolTip(f"Performs: {', '.join(tags)}")
            
            self.available_roles_list.addItem(item)

    def _on_role_double_clicked(self, item: QListWidgetItem):
        if role_data := item.data(Qt.ItemDataRole.UserRole):
            self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def _show_role_context_menu(self, pos):
        item = self.available_roles_list.itemAt(pos)
        if not item:
            return

        if role_data := item.data(Qt.ItemDataRole.UserRole):
            menu = QMenu(self)
            view_scene_action = menu.addAction("View Scene")
            
            global_pos = self.available_roles_list.viewport().mapToGlobal(pos)
            
            action = menu.exec(global_pos)
            if action == view_scene_action:
                self.open_scene_dialog_requested.emit(role_data['scene_id'])

    def _confirm_hire(self):
        selected_items = self.available_roles_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Roles Selected", "Please select one or more roles to assign the talent to.")
            return
        
        roles_to_cast, scene_ids = [], set()
        for item in selected_items:
            role_data = item.data(Qt.ItemDataRole.UserRole)
            if role_data['scene_id'] in scene_ids:
                QMessageBox.warning(self, "Casting Error", "Cannot cast for multiple roles in the same scene.\nA talent can only be cast once per scene.")
                return
            scene_ids.add(role_data['scene_id'])
            roles_to_cast.append(role_data)
        self.hire_confirmed.emit(roles_to_cast)