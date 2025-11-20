import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from database.db_models import TalentDB, ContractDB, GameInfoDB
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

    def sign_contract(self, talent_id: int, terms: Dict[str, Any], calculated_salary: int) -> bool:
        """Creates a new exclusive contract for a talent."""
        with self.session_factory() as session:
            try:
                talent_db = session.query(TalentDB).get(talent_id)
                if not talent_db:
                    logger.error(f"Talent {talent_id} not found for contract signing.")
                    return False

                if talent_db.contract:
                    logger.warning(f"Talent {talent_id} already has a contract.")
                    return False
                
                week = int(session.query(GameInfoDB).filter_by(key='week').one().value)
                year = int(session.query(GameInfoDB).filter_by(key='year').one().value)

                contract = ContractDB(
                    talent_id=talent_id,
                    start_week=week,
                    start_year=year,
                    duration_weeks=terms['duration_weeks'],
                    weekly_salary=calculated_salary,
                    compliance=self.config.initial_compliance,
                    allowed_orientations=terms.get('allowed_orientations', []),
                    allowed_concepts=terms.get('allowed_concepts', []),
                    max_dynamic=terms.get('max_dynamic', 3),
                    disposition=terms.get('disposition'),
                    max_scenes_per_week=terms.get('max_scenes_per_week', 1)
                )
                
                session.add(contract)
                
                # Deduct first week's salary immediately? Or wait for weekly processing?
                # Usually signing bonus or first week is paid. Let's pay first week.
                # Create a signing bonus field later that affects initial compliance.
                money_info = session.query(GameInfoDB).filter_by(key='money').one()
                current_money = int(float(money_info.value))
                new_money = current_money - calculated_salary
                money_info.value = str(new_money)
                
                session.commit()
                
                self.signals.notification_posted.emit(f"Signed exclusive contract with {talent_db.alias}!")
                self.signals.money_changed.emit(new_money)
                self.signals.roster_changed.emit() # UI needs to update hiring widget
                return True
            except Exception as e:
                logger.error(f"Error signing contract for talent {talent_id}: {e}", exc_info=True)
                session.rollback()
                return False

    def process_weekly_contracts(self, session: Session) -> int:
        """
        Deducts salaries, updates duration, and handles expirations/cancellations.
        Called by TimeService within the main weekly transaction.
        Returns total salary cost paid.
        """
        active_contracts = session.query(ContractDB).all()
        total_cost = 0
        expirations = []
        breakups = []
        
        for contract in active_contracts:
            # 1. Pay Salary
            total_cost += contract.weekly_salary
            
            # 2. Decrement Duration
            contract.duration_weeks -= 1
            
            # 3. Check Expiration
            if contract.duration_weeks <= 0:
                expirations.append(contract)
                continue
                
            # 4. Check Compliance (Breakup threshold)
            if contract.compliance <= 0:
                breakups.append(contract)
                
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
            
        return total_cost

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