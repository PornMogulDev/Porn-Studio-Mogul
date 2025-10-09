import json
from sqlalchemy import ( create_engine, Column, Integer, String, Float, Boolean,
ForeignKey, JSON, CheckConstraint, PrimaryKeyConstraint )
from sqlalchemy.orm import relationship, sessionmaker, declarative_base, ColumnProperty
from typing import Type, TypeVar, Any, Dict, List

from game_state import *

Base = declarative_base()
T = TypeVar('T')

class DataclassMapper:
    """A mixin to provide from_dataclass and to_dataclass methods."""  
    @classmethod
    def from_dataclass(cls: Type[T], data_obj: Any) -> T:
        """Creates a DB model instance from a dataclass instance."""
        db_instance = cls()
        for key, value in data_obj.__dict__.items():
            if hasattr(db_instance, key):
                prop = getattr(cls, key).property
                if isinstance(prop, ColumnProperty):
                    if isinstance(prop.columns[0].type, JSON):
                        if hasattr(value, 'to_dict'): 
                            setattr(db_instance, key, value.to_dict())
                        # For lists of dataclasses
                        elif isinstance(value, list) and value and hasattr(value[0], 'to_dict'):
                            setattr(db_instance, key, [item.to_dict() for item in value])
                        else:
                            setattr(db_instance, key, value)
                    else:
                        setattr(db_instance, key, value)
        return db_instance

    def to_dataclass(self, dataclass_type: Type[T]) -> T:
        """Creates a dataclass instance from a DB model instance."""
        data = {}
        for key in dataclass_type.__annotations__.keys():
            if hasattr(self, key):
                value = getattr(self, key)
                data[key] = value
        
        if dataclass_type == Scene:
            data['virtual_performers'] = [vp.to_dataclass(VirtualPerformer) for vp in self.virtual_performers]
            data['action_segments'] = [seg.to_dataclass(ActionSegment) for seg in self.action_segments]
            data['performer_contributions'] = [c.to_dataclass(ScenePerformerContribution) for c in self.performer_contributions_rel]
            
            # Re-create the dictionaries from the SceneCastDB relationship
            data['final_cast'] = {str(c.virtual_performer_id): c.talent_id for c in self.cast}
            data['pps_salaries'] = {str(c.talent_id): c.salary for c in self.cast}

        elif dataclass_type == Talent:
            # Re-create the popularity dictionary from the TalentPopularityDB relationship
            data['popularity'] = {p.market_group_name: p.score for p in self.popularity_scores}
            # Combine the two-way chemistry relationships into one dictionary
            chem_dict = {}
            for chem in self.chemistry_a:
                chem_dict[chem.talent_b_id] = chem.chemistry_score
            for chem in self.chemistry_b:
                chem_dict[chem.talent_a_id] = chem.chemistry_score
            data['chemistry'] = chem_dict
        
        elif dataclass_type == ActionSegment:
            data['slot_assignments'] = [sa.to_dataclass(SlotAssignment) for sa in self.slot_assignments]
        elif dataclass_type == ShootingBloc:
            data['scenes'] = [s.to_dataclass(Scene) for s in self.scenes]
        
        # Use from_dict for dataclasses_json compatibility
        return dataclass_type.from_dict(data)

class GameInfoDB(Base):
    """Stores simple key-value game state like week, year, money."""
    __tablename__ = 'game_info'
    key = Column(String, primary_key=True)
    value = Column(String)

class ShootingBlocDB(Base, DataclassMapper):
    __tablename__ = 'shooting_blocs'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    scheduled_week = Column(Integer)
    scheduled_year = Column(Integer)
    production_settings = Column(JSON, default=dict)
    production_cost = Column(Integer, default=0)
    on_set_policies = Column(JSON, default=list)
    scenes = relationship("SceneDB", back_populates="bloc", cascade="all, delete-orphan")

class TalentChemistryDB(Base):
    __tablename__ = 'talent_chemistry'
    talent_a_id = Column(Integer, ForeignKey('talents.id'), primary_key=True)
    talent_b_id = Column(Integer, ForeignKey('talents.id'), primary_key=True)
    chemistry_score = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        PrimaryKeyConstraint('talent_a_id', 'talent_b_id'),
        CheckConstraint('talent_a_id < talent_b_id', name='talent_order_check')
    )

    talent_a = relationship("TalentDB", foreign_keys=[talent_a_id], back_populates="chemistry_a")
    talent_b = relationship("TalentDB", foreign_keys=[talent_b_id], back_populates="chemistry_b")

class TalentDB(Base, DataclassMapper):
    __tablename__ = 'talents'
    id = Column(Integer, primary_key=True)
    alias = Column(String)
    age = Column(Integer)
    ethnicity = Column(String)
    gender = Column(String)
    performance = Column(Float)
    acting = Column(Float)
    stamina = Column(Float)
    dom_skill = Column(Float)
    sub_skill = Column(Float)
    ambition = Column(Integer)
    professionalism = Column(Integer, default=5, nullable=False)
    orientation_score = Column(Integer, default=0, nullable=False)
    disposition_score = Column(Integer, default=0, nullable=False)
    boob_cup = Column(String, nullable=True)
    dick_size = Column(Integer, nullable=True)
    tag_affinities = Column(JSON, default=dict)
    popularity_scores = relationship("TalentPopularityDB", back_populates="talent", cascade="all, delete-orphan")
    fatigue = Column(Integer, default=0)
    fatigue_end_week = Column(Integer, default=0)
    fatigue_end_year = Column(Integer, default=0)
    chemistry_a = relationship("TalentChemistryDB", foreign_keys=[TalentChemistryDB.talent_a_id], back_populates="talent_a", cascade="all, delete-orphan")
    chemistry_b = relationship("TalentChemistryDB", foreign_keys=[TalentChemistryDB.talent_b_id], back_populates="talent_b", cascade="all, delete-orphan")
    tag_preferences = Column(JSON, default=dict)
    hard_limits = Column(JSON, default=list)
    max_scene_partners = Column(Integer, default=10, nullable=False)
    concurrency_limits = Column(JSON, default=dict)
    policy_requirements = Column(JSON, default=dict)

class SceneCastDB(Base, DataclassMapper):
    __tablename__ = 'scene_cast'
    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    virtual_performer_id = Column(Integer, ForeignKey('virtual_performers.id'), nullable=False)
    talent_id = Column(Integer, ForeignKey('talents.id'), nullable=False)
    salary = Column(Integer, nullable=False)
    scene = relationship("SceneDB", back_populates="cast")
    virtual_performer = relationship("VirtualPerformerDB")
    talent = relationship("TalentDB")

class ScenePerformerContributionDB(Base, DataclassMapper):
    __tablename__ = 'scene_performer_contributions'
    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    talent_id = Column(Integer, ForeignKey('talents.id'), nullable=False)
    contribution_key = Column(String, nullable=False)
    quality_score = Column(Float, nullable=False)
    scene = relationship("SceneDB", back_populates="performer_contributions_rel")
    talent = relationship("TalentDB")

class SceneDB(Base, DataclassMapper):
    __tablename__ = 'scenes'
    id = Column(Integer, primary_key=True)
    bloc_id = Column(Integer, ForeignKey('shooting_blocs.id'), nullable=True)
    title = Column(String)
    status = Column(String)
    focus_target = Column(String)
    product_type = Column(String)
    scheduled_week = Column(Integer)
    scheduled_year = Column(Integer)
    dom_sub_dynamic_level = Column(Integer, default=0)
    scene_type = Column(String, nullable=True)
    is_locked = Column(Boolean, default=False)
    total_runtime_minutes = Column(Integer, default=10)
    global_tags = Column(JSON, default=list)
    assigned_tags = Column(JSON, default=dict)
    auto_tags = Column(JSON, default=list)
    weeks_remaining = Column(Integer, default=0)
    pic_set = Column(Boolean, default=False)
    tag_qualities = Column(JSON, default=dict)
    revenue = Column(Integer, default=0)
    viewer_group_interest = Column(JSON, default=dict)
    performer_stamina_costs = Column(JSON, default=dict)
    revenue_modifier_details = Column(JSON, default=dict)
    post_production_choices = Column(JSON, default=dict)

    bloc = relationship("ShootingBlocDB", back_populates="scenes")
    virtual_performers = relationship("VirtualPerformerDB", back_populates="scene", cascade="all, delete-orphan")
    cast = relationship("SceneCastDB", back_populates="scene", cascade="all, delete-orphan")
    action_segments = relationship("ActionSegmentDB", back_populates="scene", cascade="all, delete-orphan")
    performer_contributions_rel = relationship("ScenePerformerContributionDB", back_populates="scene", cascade="all, delete-orphan")

  

class VirtualPerformerDB(Base, DataclassMapper):
    __tablename__ = 'virtual_performers'
    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    name = Column(String)
    gender = Column(String)
    ethnicity = Column(String)
    disposition = Column(String, default="Switch")
    scene = relationship("SceneDB", back_populates="virtual_performers")

class ActionSegmentDB(Base, DataclassMapper):
    __tablename__ = 'action_segments'
    id = Column(Integer, primary_key=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=False)
    tag_name = Column(String)
    runtime_percentage = Column(Integer, default=10)
    parameters = Column(JSON, default=dict)
    scene = relationship("SceneDB", back_populates="action_segments")
    slot_assignments = relationship("SlotAssignmentDB", back_populates="segment", cascade="all, delete-orphan")

class SlotAssignmentDB(Base, DataclassMapper):
    __tablename__ = 'slot_assignments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    segment_id = Column(Integer, ForeignKey('action_segments.id'), nullable=False)
    slot_id = Column(String)
    virtual_performer_id = Column(Integer)
    segment = relationship("ActionSegmentDB", back_populates="slot_assignments")

class EmailMessageDB(Base, DataclassMapper):
    __tablename__ = 'emails'
    id = Column(Integer, primary_key=True)
    subject = Column(String)
    body = Column(String)
    week = Column(Integer)
    year = Column(Integer)
    is_read = Column(Boolean, default=False)

class MarketGroupStateDB(Base, DataclassMapper):
    __tablename__ = 'market_state'
    name = Column(String, primary_key=True)
    current_saturation = Column(Float)

class TalentPopularityDB(Base, DataclassMapper):
    __tablename__ = 'talent_popularity'
    id = Column(Integer, primary_key=True)
    talent_id = Column(Integer, ForeignKey('talents.id'), nullable=False)
    market_group_name = Column(String, ForeignKey('market_state.name'), nullable=False)
    score = Column(Float, default=0.0)
    talent = relationship("TalentDB", back_populates="popularity_scores")
    market_group = relationship("MarketGroupStateDB")

class GoToListDB(Base):
    __tablename__ = 'go_to_list'
    talent_id = Column(Integer, primary_key=True)