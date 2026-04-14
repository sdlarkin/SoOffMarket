# backend/matcher/services.py
from properties.models import Property
from buyers.models import BuyBox
from matcher.models import PropertyMatch

STATE_MAPPINGS = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

from django.db import transaction

class MatcherEngine:
    
    @staticmethod
    @transaction.atomic
    def run():
        PropertyMatch.objects.all().delete()
        properties = Property.objects.all()
        buyboxes = BuyBox.objects.all()
        
        total_matches = 0

        # We will bulk create to prevent SQLite from locking out reads
        matches_to_create = []

        for prop in properties:
            for box in buyboxes:
                if MatcherEngine.evaluate_match(prop, box):
                    matches_to_create.append(
                        PropertyMatch(
                            property=prop,
                            buybox=box,
                            match_score=100.0,
                            match_reason=f"Matched Asset Type and Location ({prop.state})"
                        )
                    )
                    total_matches += 1
        
        PropertyMatch.objects.bulk_create(matches_to_create)
        return total_matches

    @staticmethod
    def evaluate_match(prop, box):
        # 1. Filter by Asset Type logic
        asset_text = (box.asset_type + " " + box.property_types).lower()
        is_rv_buyer = "rv " in asset_text or "rvs" in asset_text or "campground" in asset_text or "mobile home" in asset_text
        
        if not is_rv_buyer:
            return False
            
        # 2. Filter by Location (CURRENTLY BUGGY)
        target_states = box.target_states.lower()
        prop_state_abbr = prop.state.strip().upper()
        prop_state_full = STATE_MAPPINGS.get(prop_state_abbr, "").lower()
        
        is_nationwide = "nationwide" in target_states or "any" in target_states or target_states.strip() == ""
        
        if is_nationwide:
            return True
            
        import re
        
        # Strict boundary check for abbreviation (e.g. \bor\b doesn't match florida)
        abbr_pattern = r'\b' + re.escape(prop_state_abbr.lower()) + r'\b'
        if re.search(abbr_pattern, target_states):
            return True
            
        # Strict boundary check for full name
        if prop_state_full:
            full_pattern = r'\b' + re.escape(prop_state_full) + r'\b'
            if re.search(full_pattern, target_states):
                return True
                
        return False
