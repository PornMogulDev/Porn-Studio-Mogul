from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel

from data.game_state import Talent
from utils.formatters import format_orientation, format_physical_attribute

class DetailsWidget(QWidget):
    """A widget to display a talent's core details and skills."""
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        details_group = QGroupBox("Details")
        details_layout = QFormLayout(details_group)
        self.age_label = QLabel()
        self.ethnicity_label = QLabel()
        self.gender_label = QLabel()
        self.orientation_label = QLabel()
        self.popularity_label = QLabel()
        self.fatigue_label = QLabel()
        self.physical_attr_name_label = QLabel()
        self.physical_attr_value_label = QLabel()
        details_layout.addRow("<b>Age:</b>", self.age_label)
        details_layout.addRow("<b>Gender:</b>", self.gender_label)
        details_layout.addRow("<b>Orientation:</b>", self.orientation_label)
        details_layout.addRow("<b>Ethnicity:</b>", self.ethnicity_label)
        details_layout.addRow(self.physical_attr_name_label, self.physical_attr_value_label)
        details_layout.addRow("<b>Popularity:</b>", self.popularity_label)
        details_layout.addRow("<b>Fatigue:</b>", self.fatigue_label)
        main_layout.addWidget(details_group)

        skills_group = QGroupBox("Skills and Attributes")
        skills_layout = QFormLayout(skills_group)
        self.performance_label = QLabel()
        self.acting_label = QLabel()
        self.stamina_label = QLabel()
        self.dom_skill_label = QLabel()
        self.sub_skill_label = QLabel()
        self.experience_label = QLabel()
        skills_layout.addRow("<b>Performance:</b>", self.performance_label)
        skills_layout.addRow("<b>Acting:</b>", self.acting_label)
        skills_layout.addRow("<b>Dom Skill:</b>", self.dom_skill_label)
        skills_layout.addRow("<b>Sub Skill:</b>", self.sub_skill_label)
        skills_layout.addRow("<b>Stamina:</b>", self.stamina_label)
        skills_layout.addRow("<b>Experience:</b>", self.experience_label)
        main_layout.addWidget(skills_group)

        main_layout.addStretch()

    def display_basic_info(self, data: dict):
        self.age_label.setText(str(data['age']))
        self.gender_label.setText(data['gender'])
        self.orientation_label.setText(format_orientation(data['orientation'], data['gender']))
        self.ethnicity_label.setText(data['ethnicity'])
        self.popularity_label.setText(str(data['popularity']))
        self.fatigue_label.setText(data['fatigue'])

    def display_skills(self, data: dict):
        # The presenter now provides pre-formatted strings
        self.performance_label.setText(data['performance'])
        self.acting_label.setText(data['acting'])
        self.stamina_label.setText(data['stamina'])
        self.dom_skill_label.setText(data.get('dom_skill', 'N/A'))
        self.sub_skill_label.setText(data.get('sub_skill', 'N/A'))
        self.experience_label.setText(int(data['experience']))

    def populate_physical_label(self, talent: Talent):
        unit_system = self.settings_manager.get_setting("unit_system", "imperial")
        attr_name, attr_value = format_physical_attribute(talent, unit_system)
        
        if attr_name:
            self.physical_attr_name_label.setText(f"<b>{attr_name}:</b>")
            self.physical_attr_value_label.setText(attr_value)
            self.physical_attr_name_label.setVisible(True)
            self.physical_attr_value_label.setVisible(True)
        else:
            self.physical_attr_name_label.setVisible(False)
            self.physical_attr_value_label.setVisible(False)