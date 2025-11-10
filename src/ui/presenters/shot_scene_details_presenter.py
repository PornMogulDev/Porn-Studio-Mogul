from typing import Optional
from PyQt6.QtCore import QObject
from PyQt6 import sip

from data.game_state import Scene
from core.interfaces import IGameController
from ui.view_models import FinancialViewModel, EditingOptionViewModel, PostProductionViewModel
from utils.scene_summary_builder import prepare_summary_data

class ShotSceneDetailsPresenter(QObject):
    def __init__(self, scene_id: int, controller: IGameController, view, initial_tab: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.scene_id = scene_id
        self.controller = controller
        self.view = view
        self.scene: Optional[Scene] = None
        self.initial_tab = initial_tab
        
        self.controller.signals.scenes_changed.connect(self._on_scene_changed)

    def disconnect_signals(self):
        """Disconnects from all global signals to prevent memory leaks and errors."""
        try:
            self.controller.signals.scenes_changed.disconnect(self._on_scene_changed)
        except TypeError: # This can happen if the signal is already disconnected
            pass

    def load_initial_data(self):
        """Fetches the initial scene data and tells the view to populate."""
        self.scene = self.controller.get_scene_for_planner(self.scene_id)
        if self.scene:
            self.view.populate_data()
            if self.initial_tab:
                self.view.set_active_tab(self.initial_tab)
        else:
            self.view.reject() # Scene not found, close dialog

    def get_scene_title(self) -> str:
        return self.scene.title if self.scene else "Details"

    def get_financial_view_model(self) -> FinancialViewModel:
        """Calculates and formats all financial data."""
        theme = self.controller.get_current_theme()
        
        salary_expenses = sum(self.scene.pps_salaries.values())
        bloc_cost_share = 0
        editing_cost = 0

        if self.scene.bloc_id:
            bloc = self.controller.get_bloc_by_id(self.scene.bloc_id)
            if bloc and len(bloc.scenes) > 0:
                bloc_cost_share = bloc.production_cost / len(bloc.scenes)

        if editing_tier_id := (self.scene.post_production_choices or {}).get('editing_tier'):
            editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
            tier_data = next((t for t in editing_tiers if t['id'] == editing_tier_id), None)
            if tier_data:
                editing_cost = tier_data.get('cost', 0)
        
        total_expenses = int(salary_expenses + bloc_cost_share + editing_cost)
        
        # Build Expenses HTML
        expenses_html = "<h4>Expenses</h4>"
        if bloc_cost_share > 0:
            expenses_html += f"Bloc Production Share: <font color='{theme.color_bad}'>-${int(bloc_cost_share):,}</font><br>"
        if editing_cost > 0:
            expenses_html += f"Post-Production: <font color='{theme.color_bad}'>-${editing_cost:,}</font><br>"
        
        expenses_html += "Talent Salaries:<br>"
        for talent_id_str, salary in self.scene.pps_salaries.items():
            talent = self.controller.get_talent_by_id(int(talent_id_str))
            if talent:
                expenses_html += f"&nbsp;&nbsp;• {talent.alias}: <font color='{theme.color_bad}'>-${salary:,}</font><br>"
        
        expenses_html += f"<br><b>Total Expenses: <font color='{theme.color_bad}'>-${total_expenses:,}</font></b>"
        
        # Build Revenue & Profit HTML
        revenue_html = "<h4>Revenue</h4>"
        if self.scene.status == 'released':
            revenue = self.scene.revenue
            profit = revenue - total_expenses
            
            for group in sorted(self.scene.viewer_group_interest.keys()):
                group_revenue = self._calculate_revenue_for_group(group)
                revenue_html += f"&nbsp;&nbsp;• {group}: <font color='{theme.color_good}'>+${group_revenue:,}</font><br>"

            revenue_html += f"<br><b>Total Revenue: <font color='{theme.color_good}'>+${revenue:,}</font></b>"
            
            profit_color = theme.color_good if profit >= 0 else theme.color_bad
            profit_text = f"<b>Profit: <font color='{profit_color}'>${profit:,}</font></b>"
        else:
            revenue_html += "<i>Scene not yet released.</i>"
            profit_text = f"<b>Profit: <font color='{theme.color_bad}'>(${-total_expenses:,})</font></b>"
            
        # Market Interest
        market_interest_lines = []
        for group, interest in sorted(self.scene.viewer_group_interest.items()):
            color = theme.color_good if interest > 1.0 else theme.color_bad if interest < 1.0 else theme.text
            line = f"{group}: <font color='{color}'>{interest:.2f}</font>"
            market_interest_lines.append(line)
        
        focus_target_html = f"<b>Focus Target:</b> {self.scene.focus_target}"
        market_details_html = "<br>".join(market_interest_lines) or "N/A"
        market_interest_html = f"{focus_target_html}<br><br>{market_details_html}"

        return FinancialViewModel(
            expenses_html=expenses_html,
            revenue_html=revenue_html,
            profit_html=profit_text,
            market_interest_html=market_interest_html
        )
        
    def get_summary_data(self) -> dict:
        """Prepares data for the SceneSummaryWidget."""
        return prepare_summary_data(self.scene, self.controller)

    def get_post_production_view_model(self) -> PostProductionViewModel:
        """Prepares all data needed for the post-production tab."""
        if self.scene.status != 'shot':
            return PostProductionViewModel(is_visible=False)

        theme = self.controller.get_current_theme()
        editing_tiers = self.controller.data_manager.post_production_data.get('editing_tiers', [])
        camera_setup_tier = "1"
        if self.scene.bloc_id and (bloc := self.controller.get_bloc_by_id(self.scene.bloc_id)):
            camera_setup_tier = bloc.production_settings.get('Camera Setup', '1')

        options = []
        for i, tier in enumerate(editing_tiers):
            base_mod = tier.get('base_quality_modifier', 1.0)
            synergy_mod = tier.get('synergy_mods', {}).get(camera_setup_tier, 0.0)
            final_mod = base_mod + synergy_mod

            info_text = (f"Cost: <font color='{theme.color_bad}'>${tier['cost']:,}</font> | "
                         f"Time: {tier['weeks']}w | "
                         f"Quality Mod: <b>{final_mod:.2f}x</b>")
            
            options.append(EditingOptionViewModel(
                tier_id=tier['id'],
                name=tier['name'],
                tooltip=tier['description'],
                info_text=info_text,
                is_checked=(i == 0) # Check the first option by default
            ))
            
        return PostProductionViewModel(is_visible=True, options=options)

    def start_editing(self, tier_id: str):
        """Delegates the start editing action to the controller."""
        self.controller.start_editing_scene(self.scene.id, tier_id)

    def _calculate_revenue_for_group(self, group_name: str) -> int:
        """A simplified estimate of a single group's revenue contribution."""
        if not self.scene.revenue or not self.scene.viewer_group_interest:
            return 0
        
        total_interest_score = sum(self.scene.viewer_group_interest.values())
        group_interest_score = self.scene.viewer_group_interest.get(group_name, 0)
        
        if total_interest_score == 0: return 0
            
        return int(self.scene.revenue * (group_interest_score / total_interest_score))
        
    def _on_scene_changed(self):
        """Slot to refresh data when a scene changes globally."""
        # Guard against accessing a deleted view (zombie presenter issue)
        if not self.view or sip.isdeleted(self.view):
            # View has been destroyed, disconnect to prevent future calls
            self.disconnect_signals()
            return
            
        fresh_scene = self.controller.get_scene_for_planner(self.scene_id)
        if fresh_scene:
            self.scene = fresh_scene
            try:
                self.view.populate_data()
            except RuntimeError:
                # View was deleted between the check and the call
                self.disconnect_signals()
        else:
            try:
                self.view.reject()
            except RuntimeError:
                # View was deleted, just disconnect
                self.disconnect_signals()