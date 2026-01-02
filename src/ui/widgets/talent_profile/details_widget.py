from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QListWidget, QListWidgetItem, QHBoxLayout
)
from PyQt6.QtCore import QSize

from data.game_state import Talent
from utils.formatters import format_orientation, format_physical_attribute

class DetailsWidget(QWidget):
    """A widget to display a talent's core details and skills."""
    def __init__(self, settings_manager, icon_manager, use_horizontal_layout=False, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.icon_manager = icon_manager
        self.use_horizontal_layout = use_horizontal_layout
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Container for Details and Skills
        top_container = QWidget()
        if self.use_horizontal_layout:
            top_layout = QHBoxLayout(top_container)
        else:
            top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)

        details_group = QGroupBox("Details")
        details_layout = QFormLayout(details_group)
        self.age_label = QLabel()
        self.ethnicity_label = QLabel()
        self.gender_label = QLabel()
        self.nationality_label = QLabel()
        self.location_label = QLabel()
        self.orientation_label = QLabel()
        self.popularity_label = QLabel()
        self.fatigue_label = QLabel()
        self.physical_attr_name_label = QLabel()
        self.physical_attr_value_label = QLabel()
        # Nationality Row with Icon
        self.nationality_container = QWidget()
        self.nationality_layout = QHBoxLayout(self.nationality_container)
        self.nationality_layout.setContentsMargins(0, 0, 0, 0)
        self.nationality_layout.setSpacing(5)
        
        self.nationality_icon_label = QLabel()
        self.nationality_icon_label.setFixedSize(24, 16) # Standard flag aspect ratio roughly
        self.nationality_icon_label.setScaledContents(True)
        self.nationality_layout.addWidget(self.nationality_icon_label)
        self.nationality_layout.addWidget(self.nationality_label)
        self.nationality_layout.addStretch()

        details_layout.addRow("<b>Age:</b>", self.age_label)
        details_layout.addRow("<b>Gender:</b>", self.gender_label)
        details_layout.addRow("<b>Orientation:</b>", self.orientation_label)
        details_layout.addRow("<b>Ethnicity:</b>", self.ethnicity_label)
        details_layout.addRow("<b>Nationality:</b>", self.nationality_container)
        details_layout.addRow("<b>Location:</b>", self.location_label)
        details_layout.addRow(self.physical_attr_name_label, self.physical_attr_value_label)
        details_layout.addRow("<b>Popularity:</b>", self.popularity_label)
        details_layout.addRow("<b>Fatigue:</b>", self.fatigue_label)
        top_layout.addWidget(details_group)

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
        top_layout.addWidget(skills_group)

        # Add the top container to the main layout
        main_layout.addWidget(top_container)

        # Traits Section
        main_layout.addWidget(QLabel("<b>Traits:</b>"))
        self.traits_list = QListWidget()
        self.traits_list.setMaximumHeight(150) # Keep it compact
        main_layout.addWidget(self.traits_list)

        main_layout.addStretch()

    def display_basic_info(self, data: dict):
        self.age_label.setText(str(data['age']))
        self.gender_label.setText(data['gender'])
        self.orientation_label.setText(format_orientation(data['orientation'], data['gender']))
        self.ethnicity_label.setText(data['ethnicity'])
        self.nationality_label.setText(data['nationality'])
        flag_icon = self.icon_manager.get_flag_icon(data['nationality'])
        
        if not flag_icon.isNull():
             target_height = int(self.icon_manager.get_target_size().height() * 0.75) # Slightly smaller than full button icon
             
             # Get actual available size for the pixmap
             # Generate a pixmap at requested height, width=0 allows auto-calc
             pixmap = flag_icon.pixmap(QSize(100, target_height)) 
             
             # Reset fixed size to allow label to adapt to content
             self.nationality_icon_label.setFixedSize(pixmap.size())
             self.nationality_icon_label.setPixmap(pixmap)
             self.nationality_icon_label.setVisible(True)
        else:
             self.nationality_icon_label.setVisible(False)
        if data['current_location'] == data['base_location']:
            self.location_label.setText(data['current_location'])
        else:
            self.location_label.setText(f"{data['current_location']} (on tour from {data['base_location']})")
        self.popularity_label.setText(str(data['popularity']))
        self.fatigue_label.setText(data['fatigue'])

        self.traits_list.clear()
        if traits := data.get('traits_data', []):
            for trait in traits:
                item = QListWidgetItem(trait['name'])
                item.setToolTip(trait['description'])
                self.traits_list.addItem(item)
        else:
            self.traits_list.addItem("No notable traits.")

    def display_skills(self, data: dict):
        # The presenter now provides pre-formatted strings
        self.performance_label.setText(data['performance'])
        self.acting_label.setText(data['acting'])
        self.stamina_label.setText(data['stamina'])
        self.dom_skill_label.setText(data.get('dom_skill', 'N/A'))
        self.sub_skill_label.setText(data.get('sub_skill', 'N/A'))
        self.experience_label.setText(str(data['experience']))

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