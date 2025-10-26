from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QScrollArea, QLabel
from PyQt6.QtCore import Qt

class AffinitiesWidget(QWidget):
    """A widget to display a talent's tag affinities."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        affinities_group = QGroupBox("Tag Affinities")
        affinities_layout = QVBoxLayout(affinities_group)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.affinities_content_widget = QWidget()
        self.affinities_layout = QVBoxLayout(self.affinities_content_widget)
        self.affinities_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.affinities_content_widget)
        
        affinities_layout.addWidget(scroll_area)
        main_layout.addWidget(affinities_group)

    def display_affinities(self, affinities: list):
        # Clear existing widgets
        while self.affinities_layout.count():
            child = self.affinities_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add new widgets
        for tag, affinity in affinities:
            self.affinities_layout.addWidget(QLabel(f"{tag}: {affinity}"))