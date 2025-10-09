from sqlalchemy import func
from typing import List, Dict

from game_state import Talent
from database.db_models import GoToListCategoryDB, GoToListAssignmentDB, TalentDB
from interfaces import GameSignals

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
        talent_ids_tuples = self.session.query(GoToListAssignmentDB.talent_id).filter_by(category_id=category_id).all()
        if not talent_ids_tuples: return []
        
        talent_ids = [item[0] for item in talent_ids_tuples]
        talents_db = self.session.query(TalentDB).filter(TalentDB.id.in_(talent_ids)).order_by(TalentDB.alias).all()
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
            
        new_category = GoToListCategoryDB(name=clean_name)
        self.session.add(new_category)
        self.signals.notification_posted.emit(f"Category '{clean_name}' created.")
        return True

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
            
        original_name = category.name
        category.name = clean_name
        self.signals.notification_posted.emit(f"Category '{original_name}' renamed to '{clean_name}'.")
        return True

    def delete_category(self, category_id: int) -> bool:
        """Deletes a Go-To List category and all its assignments. Returns True on success."""
        category = self.session.query(GoToListCategoryDB).get(category_id)
        if not category:
            self.signals.notification_posted.emit("Error: Category not found.")
            return False
        if not category.is_deletable:
            self.signals.notification_posted.emit(f"Category '{category.name}' cannot be deleted.")
            return False
            
        category_name = category.name
        self.session.delete(category)
        self.signals.notification_posted.emit(f"Category '{category_name}' deleted.")
        return True

    def add_talent_to_category(self, talent_id: int, category_id: int) -> bool:
        """Assigns a talent to a specific Go-To List category. Returns True on success."""
        exists = self.session.query(GoToListAssignmentDB).filter_by(
            talent_id=talent_id, category_id=category_id
        ).first()
        
        if not exists:
            new_assignment = GoToListAssignmentDB(talent_id=talent_id, category_id=category_id)
            self.session.add(new_assignment)
            
            talent_db = self.session.query(TalentDB).get(talent_id)
            category_db = self.session.query(GoToListCategoryDB).get(category_id)
            
            if talent_db and category_db:
                self.signals.notification_posted.emit(f"Added {talent_db.alias} to category '{category_db.name}'.")
            return True
        else:
            self.signals.notification_posted.emit("Talent is already in that category.")
            return False

    # --- NEW METHOD ---
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
            
        for talent_id in talent_ids_to_add:
            new_assignment = GoToListAssignmentDB(talent_id=talent_id, category_id=category_id)
            self.session.add(new_assignment)
        
        category_db = self.session.query(GoToListCategoryDB).get(category_id)
        if category_db:
            self.signals.notification_posted.emit(f"Added {len(talent_ids_to_add)} talent(s) to category '{category_db.name}'.")
        
        return len(talent_ids_to_add)

    def remove_talent_from_category(self, talent_id: int, category_id: int) -> bool:
        """Removes a talent from a specific Go-To List category. Returns True on success."""
        assignment = self.session.query(GoToListAssignmentDB).filter_by(
            talent_id=talent_id, category_id=category_id
        ).first()
        
        if assignment:
            self.session.delete(assignment)
            talent_db = self.session.query(TalentDB).get(talent_id)
            category_db = self.session.query(GoToListCategoryDB).get(category_id)
            if talent_db and category_db:
                self.signals.notification_posted.emit(f"Removed {talent_db.alias} from category '{category_db.name}'.")
            return True
        return False

    def remove_talents_from_category(self, talent_ids: List[int], category_id: int) -> int:
        """Removes a list of talents from a specific category. Returns the number of talents removed."""
        if not talent_ids:
            return 0

        num_deleted = self.session.query(GoToListAssignmentDB).filter(
            GoToListAssignmentDB.category_id == category_id,
            GoToListAssignmentDB.talent_id.in_(talent_ids)
        ).delete(synchronize_session=False)

        if num_deleted > 0:
            category_db = self.session.query(GoToListCategoryDB).get(category_id)
            if category_db:
                self.signals.notification_posted.emit(f"Removed {num_deleted} talent(s) from category '{category_db.name}'.")
        return num_deleted