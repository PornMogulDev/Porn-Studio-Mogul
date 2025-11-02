import logging
from sqlalchemy import func
from typing import List, Dict

from data.game_state import Talent
from database.db_models import GoToListCategoryDB, GoToListAssignmentDB, TalentDB
from core.game_signals import GameSignals

logger = logging.getLogger(__name__)

class GoToListService:
    def __init__(self, session_factory, signals: GameSignals):
        self.session_factory = session_factory
        self.signals = signals
    
    def create_category(self, name: str) -> bool:
        """Creates a new Go-To List category. Returns True on success."""
        session = self.session_factory()
        try:
            clean_name = name.strip()
            if not clean_name:
                self.signals.notification_posted.emit("Category name cannot be empty.")
                return False

            exists = session.query(GoToListCategoryDB).filter(func.lower(GoToListCategoryDB.name) == func.lower(clean_name)).first()
            if exists:
                self.signals.notification_posted.emit(f"A category named '{clean_name}' already exists.")
                return False
                
            new_category = GoToListCategoryDB(name=clean_name)
            session.add(new_category)
            session.commit()
            self.signals.notification_posted.emit(f"Category '{clean_name}' created.")
            self.signals.go_to_categories_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error creating category '{clean_name}': {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def rename_category(self, category_id: int, new_name: str) -> bool:
        """Renames an existing Go-To List category. Returns True on success."""
        session = self.session_factory()
        try:
            clean_name = new_name.strip()
            if not clean_name:
                self.signals.notification_posted.emit("Category name cannot be empty.")
                return False

            category = session.query(GoToListCategoryDB).get(category_id)
            if not category:
                self.signals.notification_posted.emit("Error: Category not found.")
                return False
                
            exists = session.query(GoToListCategoryDB).filter(
                func.lower(GoToListCategoryDB.name) == func.lower(clean_name),
                GoToListCategoryDB.id != category_id
            ).first()
            if exists:
                self.signals.notification_posted.emit(f"A category named '{clean_name}' already exists.")
                return False
            
            original_name = category.name
            category.name = clean_name
            session.commit()
            self.signals.notification_posted.emit(f"Category '{original_name}' renamed to '{clean_name}'.")
            self.signals.go_to_categories_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error renaming category ID {category_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def delete_category(self, category_id: int) -> bool:
        """Deletes a Go-To List category and all its assignments. Returns True on success."""
        session = self.session_factory()
        try:
            category = session.query(GoToListCategoryDB).get(category_id)
            if not category:
                self.signals.notification_posted.emit("Error: Category not found.")
                return False
            if not category.is_deletable:
                self.signals.notification_posted.emit(f"Category '{category.name}' cannot be deleted.")
                return False
            
            category_name = category.name
            session.delete(category)
            session.commit()
            self.signals.notification_posted.emit(f"Category '{category_name}' deleted.")
            self.signals.go_to_categories_changed.emit()
            self.signals.go_to_list_changed.emit() # Deleting a category affects assignments
            return True
        except Exception as e:
            logger.error(f"Error deleting category ID {category_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def add_talents_to_category(self, talent_ids: List[int], category_id: int) -> int:
        """Assigns a list of talents to a specific category. Returns the number of new assignments."""
        session = self.session_factory()
        try:
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
            
            for talent_id in talent_ids_to_add:
                new_assignment = GoToListAssignmentDB(talent_id=talent_id, category_id=category_id)
                session.add(new_assignment)
            session.commit()

            category_db = session.query(GoToListCategoryDB).get(category_id)
            if category_db:
                self.signals.notification_posted.emit(f"Added {len(talent_ids_to_add)} talent(s) to category '{category_db.name}'.")
            self.signals.go_to_list_changed.emit()
            return len(talent_ids_to_add)
        except Exception as e:
            logger.error(f"Error adding talents to category {category_id}: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    def remove_talents_from_category(self, talent_ids: List[int], category_id: int) -> int:
        """Removes a list of talents from a specific category. Returns the number of talents removed."""
        session = self.session_factory
        try:
            if not talent_ids:
                return 0

            num_deleted = session.query(GoToListAssignmentDB).filter(
                GoToListAssignmentDB.category_id == category_id,
                GoToListAssignmentDB.talent_id.in_(talent_ids)
            ).delete(synchronize_session=False)

            if num_deleted > 0:
                session.commit()
                category_db = session.query(GoToListCategoryDB).get(category_id)
                if category_db:
                    self.signals.notification_posted.emit(f"Removed {num_deleted} talent(s) from category '{category_db.name}'.")
                self.signals.go_to_list_changed.emit()
            
            return num_deleted
        except Exception as e:
            logger.error(f"Error removing talents from category {category_id}: {e}")
            session.rollback()
            return 0
        finally:
            session.close()
    
    def remove_talents_from_all_categories(self, talent_ids: List[int]) -> bool:
        """Removes talents from ALL Go-To List categories. Returns True if any were removed."""
        session = self.session_factory
        try:
            if not talent_ids:
                return False
            
            num_deleted = session.query(GoToListAssignmentDB).filter(
                GoToListAssignmentDB.talent_id.in_(talent_ids)
            ).delete(synchronize_session=False)
            
            if num_deleted > 0:
                session.commit()
                self.signals.notification_posted.emit(f"Removed {num_deleted} talent assignment(s) from all Go-To categories.")
                self.signals.go_to_list_changed.emit()
            return num_deleted > 0
        except Exception as e:
            logger.error(f"Error removing talents from all Go-To categories: {e}")
            session.rollback()
            return False
        finally:
            session.close()