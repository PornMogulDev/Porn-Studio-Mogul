from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel, QScrollArea, QFrame
from PyQt6.QtCore import Qt
from typing import Dict

class SceneSummaryWidget(QWidget):
    """A read-only widget to display a structured summary of a scene."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setup_ui()
        self.update_summary({}) # Start with a blank slate

    def setup_ui(self):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.scroll_content = QWidget()
        self.content_layout = QVBoxLayout(self.scroll_content)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(scroll_area)

    def _clear_layout(self, layout):
        """Removes all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def update_summary(self, summary_data: Dict):
        """Clears and rebuilds the entire summary view with new data."""
        self._clear_layout(self.content_layout)

        # 1. Composition
        comp_group = QGroupBox("Composition")
        comp_layout = QVBoxLayout(comp_group)
        performers = summary_data.get("performers", [])
        if performers:
            for i, p_data in enumerate(performers):
                details = (f"<b>{p_data['role_name']}</b> ({p_data['gender']}, {p_data['ethnicity']}) "
                           f"| Cast: <b>{p_data['cast_talent_alias']}</b>")
                comp_layout.addWidget(QLabel(details))
        else:
            comp_layout.addWidget(QLabel("No performers defined."))
        self.content_layout.addWidget(comp_group)

        # 2. Thematic Tags
        thematic_group = QGroupBox("Thematic Tags")
        thematic_layout = QVBoxLayout(thematic_group)
        thematic_tags = summary_data.get("thematic_tags", [])
        if thematic_tags:
            label = QLabel(" • " + "\n • ".join(thematic_tags))
            label.setWordWrap(True)
            thematic_layout.addWidget(label)
        else:
            thematic_layout.addWidget(QLabel("No thematic tags selected."))
        self.content_layout.addWidget(thematic_group)
        
        # 3. Physical Tags
        physical_group = QGroupBox("Physical Tags and Assignments")
        physical_layout = QVBoxLayout(physical_group)
        physical_tags = summary_data.get("physical_tags", [])
        if physical_tags:
            for p_tag_data in physical_tags:
                assign_text = ", ".join(p_tag_data['assigned_performers']) or "<i>None</i>"
                label = QLabel(f"<b>{p_tag_data['tag_name']}:</b> {assign_text}")
                physical_layout.addWidget(label)
        else:
            physical_layout.addWidget(QLabel("No physical tags selected."))
        self.content_layout.addWidget(physical_group)

        # 4. Action Segments
        actions_group = QGroupBox("Action Segments and Roles")
        actions_layout = QVBoxLayout(actions_group)
        action_segments = summary_data.get("action_segments", [])
        if action_segments:
            for a_seg_data in action_segments:
                seg_label = QLabel(f"<b>{a_seg_data['segment_name']}</b>")
                actions_layout.addWidget(seg_label)
                
                if not a_seg_data['assignments']:
                     role_label = QLabel("  • <i>(No roles defined)</i>")
                     actions_layout.addWidget(role_label)
                else:
                    for assignment in a_seg_data['assignments']:
                        role_label = QLabel(f"  • {assignment['role']}: {assignment['assigned_performer']}")
                        actions_layout.addWidget(role_label)
        else:
            actions_layout.addWidget(QLabel("No action segments defined."))
        self.content_layout.addWidget(actions_group)