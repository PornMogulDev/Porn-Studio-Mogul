from collections import defaultdict
from typing import Dict, Any, Tuple, List

from data.game_state import Talent

def build_preferences_view_model(talent: Talent, tag_definitions: Dict[str, Any], policy_definitions: Dict[str, Any]) -> Tuple[List[Dict], List[str], List[str], List[str]]:
    """
    Processes a talent's raw data into a structured view model for the PreferencesWidget.

    Returns a tuple containing:
    - preferences_data: A list of dictionaries for the preferences tree.
    - limits: A sorted list of hard limits.
    - required_policies: A list of required policy names.
    - refused_policies: A list of refused policy names.
    """
    # --- Define thresholds for categorization and display ---
    LOVES_THRESHOLD = 1.4
    LIKES_THRESHOLD = 1.01  # Anything above 1.0 is a like
    DISLIKES_THRESHOLD = 0.99  # Anything below 1.0 is a dislike
    HATES_THRESHOLD = 0.60
    REFUSAL_THRESHOLD = 0.2  # Preference so low they might refuse the role
    NOTABLE_HIGH_THRESHOLD = 1.2
    NOTABLE_LOW_THRESHOLD = 0.8

    prefs_by_orientation = defaultdict(list)

    # 1. Group all preference scores by their orientation
    for tag, roles in talent.tag_preferences.items():
        tag_def = tag_definitions.get(tag)
        if not tag_def or not (orientation := tag_def.get('orientation')):
            continue
        for role, score in roles.items():
            prefs_by_orientation[orientation].append({'tag': tag, 'role': role, 'score': score})

    # 2. Process each orientation group to create the final data structure
    preferences_data = []
    for orientation, items in sorted(prefs_by_orientation.items()):
        if not items:
            continue

        scores = [item['score'] for item in items]
        avg_score = sum(scores) / len(scores)

        # Determine summary string based on the average score
        if avg_score >= LOVES_THRESHOLD:
            summary = "Loves"
        elif avg_score >= LIKES_THRESHOLD:
            summary = "Likes"
        elif avg_score > HATES_THRESHOLD:  # Covers the range from 0.60 to 0.99
            summary = "Dislikes"
        else:  # Anything 0.60 or below
            summary = "Hates"

        # Check for potential refusals
        has_refusals = any(item['score'] < REFUSAL_THRESHOLD for item in items)

        # Filter for notable items to display as children
        notable_items = []
        for item in items:
            if item['score'] > NOTABLE_HIGH_THRESHOLD or item['score'] < NOTABLE_LOW_THRESHOLD:
                notable_items.append({
                    'name': f"{item['tag']} ({item['role']})",
                    'score': item['score']
                })

        # Only add the orientation if there's something worth showing
        if notable_items or has_refusals:
            preferences_data.append({
                'orientation': orientation,
                'summary': summary,
                'average': avg_score,
                'has_refusals': has_refusals,
                'items': sorted(notable_items, key=lambda x: x['score'], reverse=True)
            })

    # --- Process Policies ---
    policy_names = {p['id']: p['name'] for p in policy_definitions.values()}
    required_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('requires', []))]
    refused_policies = [policy_names.get(pid, pid) for pid in sorted(talent.policy_requirements.get('refuses', []))]

    # --- Process Hard Limits ---
    limits = sorted(talent.hard_limits)

    # --- Process D/S Dynamics ---
    ds_data = []
    labels = ["Vanilla (0)", "Soft (1)", "Hard (2)", "Extreme (3)"]
    for level in range(4):
        score = talent.ds_dynamic_preferences.get(level, 1.0)
        status = "neutral"
        if score >= LOVES_THRESHOLD: status = "great"
        elif score >= LIKES_THRESHOLD: status = "good"
        elif score <= HATES_THRESHOLD: status = "bad"
        elif score < 1.0: status = "warning"
        
        ds_data.append({'label': labels[level], 'score': score, 'status': status})

    return preferences_data, limits, required_policies, refused_policies, ds_data