import logging
from sqlalchemy import func
from typing import List, Dict

from data.game_state import Talent
from database.db_models import GoToListCategoryDB, GoToListAssignmentDB, TalentDB
from core.interfaces import GameSignals

logger = logging.getLogger(__name__)

class GoToListService:
    def __init__(self, db_session, signals: GameSignals):
        self.session = db_session
        self.signals = signals

    def get_all_categories(self) -> List[Dict]:
        """Returns a list of all Go-To List categories for UI display."""
        categories_db = self.session.query(GoToListCategoryDB).order_by(GoToListCategoryDB.name).all()
        return [{'id': c.id, 'name': c.name, 'is_deletable': c.is_deletable} for c in categories_db]

    def get_talents_in_category(self, category_id: int) -> List[Talent]:
        """Gets all talents within a specific Go-To List category."""
        talents_db = self.session.query(TalentDB)\
            .join(GoToListAssignmentDB)\
            .filter(GoToListAssignmentDB.category_id == category_id)\
            .order_by(TalentDB.alias)\
            .all()
        return [t.to_dataclass(Talent) for t in talents_db]
    
    def get_talent_categories(self, talent_id: int) -> List[Dict]:
        """Returns a list of all Go-To List categories a specific talent belongs to."""
        assignments = self.session.query(GoToListCategoryDB).\
            join(GoToListAssignmentDB).\
            filter(GoToListAssignmentDB.talent_id == talent_id).\
            order_by(GoToListCategoryDB.name).all()
            
        return [{'id': c.id, 'name': c.name, 'is_deletable': c.is_deletable} for c in assignments]
    
    def create_category(self, name: str) -> bool:
        """Creates a new Go-To List category. Returns True on success."""
        clean_name = name.strip()
        if not clean_name:
            self.signals.notification_posted.emit("Category name cannot be empty.")
            return False

        exists = self.session.query(GoToListCategoryDB).filter(func.lower(GoToListCategoryDB.name) == func.lower(clean_name)).first()
        if exists:
            self.signals.notification_posted.emit(f"A category named '{clean_name}' already exists.")
            return False
            
        try:
            new_category = GoToListCategoryDB(name=clean_name)
            self.session.add(new_category)
            self.session.commit()
            self.signals.notification_posted.emit(f"Category '{clean_name}' created.")
            self.signals.go_to_categories_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error creating category '{clean_name}': {e}")
            self.session.rollback()
            return False

    def rename_category(self, category_id: int, new_name: str) -> bool:
        """Renames an existing Go-To List category. Returns True on success."""
        clean_name = new_name.strip()
        if not clean_name:
            self.signals.notification_posted.emit("Category name cannot be empty.")
            return False

        category = self.session.query(GoToListCategoryDB).get(category_id)
        if not category:
            self.signals.notification_posted.emit("Error: Category not found.")
            return False
            
        exists = self.session.query(GoToListCategoryDB).filter(
            func.lower(GoToListCategoryDB.name) == func.lower(clean_name),
            GoToListCategoryDB.id != category_id
        ).first()
        if exists:
            self.signals.notification_posted.emit(f"A category named '{clean_name}' already exists.")
            return False
            
        try:
            original_name = category.name
            category.name = clean_name
            self.session.commit()
            self.signals.notification_posted.emit(f"Category '{original_name}' renamed to '{clean_name}'.")
            self.signals.go_to_categories_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error renaming category ID {category_id}: {e}")
            self.session.rollback()
            return False

    def delete_category(self, category_id: int) -> bool:
        """Deletes a Go-To List category and all its assignments. Returns True on success."""
        category = self.session.query(GoToListCategoryDB).get(category_id)
        if not category:
            self.signals.notification_posted.emit("Error: Category not found.")
            return False
        if not category.is_deletable:
            self.signals.notification_posted.emit(f"Category '{category.name}' cannot be deleted.")
            return False
            
        try:
            category_name = category.name
            self.session.delete(category)
            self.session.commit()
            self.signals.notification_posted.emit(f"Category '{category_name}' deleted.")
            self.signals.go_to_categories_changed.emit()
            self.signals.go_to_list_changed.emit() # Deleting a category affects assignments
            return True
        except Exception as e:
            logger.error(f"Error deleting category ID {category_id}: {e}")
            self.session.rollback()
            return False

    def add_talents_to_category(self, talent_ids: List[int], category_id: int) -> int:
        """Assigns a list of talents to a specific category. Returns the number of new assignments."""
        if not talent_ids:
            return 0
        
        # Find which of the given talents are already in the category
        existing_assignments_query = self.session.query(GoToListAssignmentDB.talent_id).filter(
            GoToListAssignmentDB.category_id == category_id,
            GoToListAssignmentDB.talent_id.in_(talent_ids)
        )
        existing_talent_ids = {t_id for t_id, in existing_assignments_query.all()}
        
        # Determine which talents need to be added
        talent_ids_to_add = set(talent_ids) - existing_talent_ids
        
        if not talent_ids_to_add:
            self.signals.notification_posted.emit("All selected talents are already in that category.")
            return 0
            
        try:
            for talent_id in talent_ids_to_add:
                new_assignment = GoToListAssignmentDB(talent_id=talent_id, category_id=category_id)
                self.session.add(new_assignment)
            self.session.commit()

            category_db = self.session.query(GoToListCategoryDB).get(category_id)
            if category_db:
                self.signals.notification_posted.emit(f"Added {len(talent_ids_to_add)} talent(s) to category '{category_db.name}'.")
            self.signals.go_to_list_changed.emit()
            return len(talent_ids_to_add)
        except Exception as e:
            logger.error(f"Error adding talents to category {category_id}: {e}")
            self.session.rollback()
            return 0

    def remove_talents_from_category(self, talent_ids: List[int], category_id: int) -> int:
        """Removes a list of talents from a specific category. Returns the number of talents removed."""
        if not talent_ids:
            return 0

        try:
            num_deleted = self.session.query(GoToListAssignmentDB).filter(
                GoToListAssignmentDB.category_id == category_id,
                GoToListAssignmentDB.talent_id.in_(talent_ids)
            ).delete(synchronize_session=False)

            if num_deleted > 0:
                self.session.commit()
                category_db = self.session.query(GoToListCategoryDB).get(category_id)
                if category_db:
                    self.signals.notification_posted.emit(f"Removed {num_deleted} talent(s) from category '{category_db.name}'.")
                self.signals.go_to_list_changed.emit()
            
            return num_deleted
        except Exception as e:
            logger.error(f"Error removing talents from category {category_id}: {e}")
            self.session.rollback()
            return 0