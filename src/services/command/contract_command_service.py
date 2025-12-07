import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from database.db_models import TalentDB, ContractDB, GameInfoDB, StudioStateDB
from core.game_signals import GameSignals
from services.query.game_query_service import GameQueryService
from services.models.configs import ContractConfig

logger = logging.getLogger(__name__)

class ContractCommandService:
    """
    Manages the lifecycle of exclusive talent contracts, including creation,
    weekly processing (payments/compliance), and termination.
    """
    def __init__(self, session_factory, signals: GameSignals, query_service: GameQueryService, config: ContractConfig):
        self.session_factory = session_factory
        self.signals = signals
        self.query_service = query_service
        self.config = config

    def sign_contract(self, talent_id: int, terms: dict, calculated_salary: int) -> bool:
        """
        Creates a new exclusive contract for the talent.
        """
        session = self.session_factory()
        try:
            # 1. Validation (or simple override if existing?)
            # For now, we assume the UI handled confirmation of overwriting old contracts.
            
            # Remove existing contract if any
            existing = session.query(ContractDB).filter_by(talent_id=talent_id).first()
            if existing:
                session.delete(existing)
                
            # 2. Create new Contract
            abs_week_info = session.query(GameInfoDB).filter_by(key='absolute_week').one()
            current_week = int(abs_week_info.value)
            
            new_contract = ContractDB(
                talent_id=talent_id,
                start_absolute_week=current_week,
                duration_weeks=terms.get('duration_weeks', 52),
                weekly_salary=calculated_salary,
                max_scenes_per_month=terms.get('max_scenes_per_month', 4),
                max_dynamic=terms.get('max_dynamic', 3),
                disposition=terms.get('disposition'),
                allowed_concepts=terms.get('allowed_concepts', []),
                allowed_orientations=terms.get('allowed_orientations', [])
            )
            session.add(new_contract)
            session.commit()
            
            self.signals.roster_changed.emit()
            
            # Fetch alias for notification
            talent = self.query_service.get_talent_by_id(talent_id)
            if talent:
                self.signals.notification_posted.emit(f"Signed exclusive contract with {talent.alias}.")
            
            return True
        except Exception as e:
            logger.error(f"Error signing contract for talent {talent_id}: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def process_weekly_contracts(self, session: Session, current_absolute_week: int):
        """
        Deducts salaries, updates duration, and handles expirations/cancellations.
        Called by TimeService within the main weekly transaction.
        """
        active_contracts = session.query(ContractDB).all()
        total_cost = 0
        expirations = []
        breakups = []
        
        for contract in active_contracts:
            # 1. Pay Salary
            total_cost += contract.weekly_salary
            
            # 2. Decrement Duration (simplistic, could be based on end_date)
            contract.duration_weeks -= 1
            
            # 3. Check Expiration
            if contract.duration_weeks <= 0:
                expirations.append(contract)
                continue
                
            # 4. Check Compliance (Breakup threshold)
            if contract.compliance <= 0:
                breakups.append(contract)
        
        if total_cost > 0:
            studio_state = session.query(StudioStateDB).get(1)
            current_money = studio_state.money
            new_money = current_money - total_cost
            studio_state.money = new_money
            self.signals.money_changed.emit(new_money)
            
        # Handle Expirations
        for contract in expirations:
            talent_name = contract.talent.alias
            session.delete(contract)
            self.signals.notification_posted.emit(f"Contract with {talent_name} has expired.")
            
        # Handle Breakups (Low Compliance)
        for contract in breakups:
            talent_name = contract.talent.alias
            session.delete(contract)
            self.signals.notification_posted.emit(f"{talent_name} terminated their contract due to poor compliance!")

    def update_compliance(self, session: Session, talent_id: int, role_preference_score: float):
        """
        Updates the compliance meter based on the specific role assigned.
        High preference work increases compliance, low preference decreases it.
        """
        contract = session.query(ContractDB).filter_by(talent_id=talent_id).first()
        if not contract: return
        
        change = 0
        if role_preference_score >= self.config.compliance_high_pref_threshold:
            change = self.config.compliance_bonus # Bonus for great roles
        elif role_preference_score <= self.config.compliance_low_pref_threshold:
            change = self.config.compliance_penalty # Heavy penalty for hated roles
        
        if change != 0:
            contract.compliance = max(0, min(self.config.compliance_max, contract.compliance + change))

    def terminate_contract(self, talent_id: int):
        """Manually terminates a contract (Player Action)."""
        with self.session_factory() as session:
            contract = session.query(ContractDB).filter_by(talent_id=talent_id).first()
            if contract:
                session.delete(contract)
                session.commit()
                self.signals.notification_posted.emit(f"Terminated contract with {contract.talent.alias}.")
                self.signals.roster_changed.emit()