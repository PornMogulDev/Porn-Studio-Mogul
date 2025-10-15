from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton,
QLabel, QSpinBox, QHeaderView
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QDialog

from ui.dialogs.scene_dialog import SceneDialog
from ui.dialogs.shooting_bloc_dialog import ShootingBlocDialog
from data.game_state import Scene, ShootingBloc
from ui.presenters.scene_planner_presenter import ScenePlannerPresenter # Import the presenter

class ScheduleTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setup_ui()
    
        # --- Connections ---
        self.controller.signals.scenes_changed.connect(self.refresh_schedule)
        self.controller.signals.time_changed.connect(self.update_year_selector)
        self.year_spinbox.valueChanged.connect(self.refresh_schedule)
        self.plan_scene_btn.clicked.connect(self.plan_shooting_bloc)
        self.tree_view.doubleClicked.connect(self.handle_double_click)
        
        # Initial setup
        self.update_year_selector()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Top Control Bar ---
        top_bar = QHBoxLayout()
        self.plan_scene_btn = QPushButton("Plan Shooting Bloc")
        top_bar.addWidget(self.plan_scene_btn)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Viewing Year:"))
        self.year_spinbox = QSpinBox()
        top_bar.addWidget(self.year_spinbox)
        main_layout.addLayout(top_bar)

        # --- Tree View ---
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.tree_view)
        
    def update_year_selector(self):
        current_year = self.controller.game_state.year
        self.year_spinbox.setRange(current_year, current_year + 10)
        self.year_spinbox.setValue(current_year)
        self.refresh_schedule()

    def refresh_schedule(self):
        self.model.clear()
        current_week = self.controller.game_state.week
        viewing_year = self.year_spinbox.value()
        
        all_blocs = self.controller.get_blocs_for_schedule_view(viewing_year)
        blocs_by_week = {}
        for bloc in all_blocs:
            week = bloc.scheduled_week
            if week not in blocs_by_week: blocs_by_week[week] = []
            blocs_by_week[week].append(bloc)

        start_week = current_week if viewing_year == self.controller.game_state.year else 1
        
        for week_num in range(start_week, 53):
            week_item = QStandardItem(f"Week {week_num}")
            week_item.setEditable(False)
            week_item.setData({'type': 'week_header', 'week': week_num, 'year': viewing_year}, Qt.ItemDataRole.UserRole)

            if week_num in blocs_by_week:
                # Iterate through blocs in the week
                for bloc in sorted(blocs_by_week[week_num], key=lambda b: b.id):
                    scene_count = len(bloc.scenes)
                    plural_s = 's' if scene_count > 1 else ''
                    bloc_item = QStandardItem(f"Shooting Bloc ({scene_count} scene{plural_s})")
                    bloc_item.setData({'type': 'bloc', 'data': bloc}, Qt.ItemDataRole.UserRole)
                    
                    prod_settings_tooltip = "\n".join(
                        f"  - {cat.replace('_', ' ').title()}: {tier}" 
                        for cat, tier in bloc.production_settings.items()
                    )
                    bloc_item.setToolTip(f"Production Settings:\n{prod_settings_tooltip}")

                    # Iterate through scenes within the bloc
                    for scene in sorted(bloc.scenes, key=lambda s: s.title):
                        status_text = scene.display_status
                        scene_item = QStandardItem(f"  - {scene.title} [{status_text}]")
                        scene_item.setToolTip(f"'{scene.title}' - Status: {status_text}")
                        scene_item.setData({'type': 'scene', 'data': scene}, Qt.ItemDataRole.UserRole)
                        bloc_item.appendRow(scene_item)
                    
                    week_item.appendRow(bloc_item)
            
            self.model.appendRow(week_item)
        self.tree_view.expandAll()

    def plan_shooting_bloc(self):
        """Opens the dialog to plan a new shooting bloc."""
        dialog = ShootingBlocDialog(self.controller, self.controller.settings_manager, self)
        dialog.exec()

    def handle_double_click(self, index):
        item = self.model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(item_data, dict): return
        item_type = item_data.get('type')

        if item_type == 'scene':
            scene = item_data.get('data')
            if isinstance(scene, Scene):
                # MVP Refactoring: Create the View, then the Presenter which manages it.
                dialog = SceneDialog(self.controller, parent=self.window())
                presenter = ScenePlannerPresenter(self.controller, scene.id, dialog)
                dialog.exec()
        
        elif item_type == 'week_header':
            week = item_data.get('week')
            year = item_data.get('year')
            dialog = ShootingBlocDialog(self.controller, self.controller.settings_manager, self)
            dialog.set_schedule(week, year)
            dialog.exec()