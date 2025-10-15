from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup, QDialogButtonBox,
)
from data.game_state import Scene
from ui.mixins.geometry_manager_mixin import GeometryManagerMixin

class DeletionPenaltyDialog(QDialog):
    """A reusable dialog to ask the user how much salary to pay when deleting a scene."""
    def __init__(self, scene_title: str, total_salary: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Deletion")
        self.total_salary = total_salary
        self._selected_percentage = 0.0
        self.setup_ui(scene_title)

    def setup_ui(self, scene_title: str):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Scene '{scene_title}' has talent cast with total salaries of ${self.total_salary:,}."))
        layout.addWidget(QLabel("Choose how much to pay in severance:"))

        self.button_group = QButtonGroup(self)
        
        rb_0 = QRadioButton(f"Pay 0% (${0:,})")
        rb_0.setProperty("percentage", 0.0)
        rb_50 = QRadioButton(f"Pay 50% (${int(self.total_salary * 0.5):,})")
        rb_50.setProperty("percentage", 0.5)
        rb_100 = QRadioButton(f"Pay 100% (${self.total_salary:,})")
        rb_100.setProperty("percentage", 1.0)
        
        self.button_group.addButton(rb_0)
        self.button_group.addButton(rb_50)
        self.button_group.addButton(rb_100)
        
        layout.addWidget(rb_0)
        layout.addWidget(rb_50)
        layout.addWidget(rb_100)
        
        rb_0.setChecked(True) # Default to 0%

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        checked_button = self.button_group.checkedButton()
        if checked_button:
            self._selected_percentage = checked_button.property("percentage")
        super().accept()

    def get_selected_percentage(self) -> float:
        return self._selected_percentage


class IncompleteCastingDialog(GeometryManagerMixin, QDialog):
    """A dialog shown when advancing the week with an incompletely cast scene."""
    def __init__(self, scene: Scene, controller, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.controller = controller
        self.settings_manager = self.controller.settings_manager
        self.setWindowTitle("Incomplete Scene")
        self.setup_ui()
        self._restore_geometry()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        if self.scene.status == 'design':
            message = (f"The scene '{self.scene.title}' is scheduled for this week but is still in the design phase."
                       "\n\nYou cannot proceed until this is resolved.")
        else: # 'casting'
            cast_count = len(self.scene.final_cast)
            total_slots = len(self.scene.virtual_performers)
            message = (f"The scene '{self.scene.title}' is scheduled for this week but casting is incomplete "
                       f"({cast_count}/{total_slots} roles filled).\n\nYou cannot proceed until this is resolved.")

        layout.addWidget(QLabel(message))

        button_box = QDialogButtonBox()
        go_back_btn = button_box.addButton("Go Back", QDialogButtonBox.ButtonRole.RejectRole)
        delete_btn = button_box.addButton("Delete Scene...", QDialogButtonBox.ButtonRole.DestructiveRole)
        
        layout.addWidget(button_box)

        go_back_btn.clicked.connect(self.reject)
        delete_btn.clicked.connect(self.handle_delete)
    
    def handle_delete(self):
        total_salary = sum(self.scene.pps_salaries.values())
        
        if total_salary > 0:
            penalty_dialog = DeletionPenaltyDialog(self.scene.title, total_salary, self)
            if penalty_dialog.exec() == QDialog.DialogCode.Accepted:
                percent = penalty_dialog.get_selected_percentage()
                self.controller.delete_scene(self.scene.id, penalty_percentage=percent)
                self.accept() # Close this dialog, signaling deletion occurred
            # If penalty dialog is cancelled, do nothing, leaving this dialog open
        else: # No cast, no penalty needed
            self.controller.delete_scene(self.scene.id)
            self.accept()