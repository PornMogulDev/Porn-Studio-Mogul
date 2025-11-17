import logging
from typing import Dict, Optional
from core.interfaces import IGameController

logger = logging.getLogger(__name__)

def prepare_role_details_data(scene_id: int, vp_id: int, controller: IGameController) -> Optional[Dict]:
    """
    Fetches raw role details from the controller. This is the data-gathering step.
    Returns a structured dictionary or None if not found.
    """
    if not scene_id or not vp_id:
        return None
    
    role_details = controller.get_role_details_for_ui(scene_id, vp_id)
    if not role_details:
        logger.warning(f"Could not fetch role details for scene {scene_id}, vp {vp_id}")
        return None
        
    return role_details

def format_role_details_html(details_data: Optional[Dict]) -> str:
    """
    Takes a dictionary of role details and formats it into an HTML string for display.
    This is the presentation step.
    """
    if not details_data:
        return ""
        
    html = "<ul>"
    html += f"<li><b>Gender:</b> {details_data.get('gender', 'N/A')}</li>"
    html += f"<li><b>Ethnicity:</b> {details_data.get('ethnicity', 'N/A')}</li>"
    
    if details_data.get('is_protagonist'):
        html += "<li><b>Protagonist Role</b></li>"
        
    if details_data.get('disposition') != 'Switch':
        html += f"<li><b>Disposition:</b> {details_data.get('disposition', 'N/A')}</li>"
        
    if physical_tags := details_data.get('physical_tags'):
        html += f"<br><li><b>Physical Tags:</b><br>{', '.join(physical_tags)}</li>"
        
    if action_roles := details_data.get('action_roles'):
        html += f"<br><li><b>Action Roles:</b><br>{', '.join(action_roles)}</li>"
        
    html += "</ul>"
    return html