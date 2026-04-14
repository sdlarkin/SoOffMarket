import os
import sys
import django
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from buyers.models import Buyer, BuyBox

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def main():
    # Use relative pathing to support the runner environment
    creds_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = '10dTiFxc4_ImcYiV_VtyB7c9KeHdcGQA15yvragdKBlA'
    
    # Grab all sheets in the document
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets_metadata = spreadsheet.get('sheets', '')
    
    total_buyers_created = 0
    total_buyboxes_created = 0

    for s in sheets_metadata:
        title = s.get('properties', {}).get('title', '')
        range_name = f"'{title}'!A1:Z500"
        
        print(f"\nProcessing Sheet: {title}")
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            print("  -> Empty or headers only. Skipping.")
            continue
            
        headers = values[0]
        rows = values[1:]
        
        # Helper to find column index gracefully
        def get_idx(header_name):
            for i, h in enumerate(headers):
                if header_name.lower() in h.lower():
                    return i
            return -1

        idx_name = get_idx("Name")
        idx_company = get_idx("Company Name")
        idx_blinq = get_idx("Blinq")
        idx_phone = get_idx("Phone")
        idx_email = get_idx("Email")
        idx_location = get_idx("Where are you located")
        
        idx_states = get_idx("Which states are you actively buying in")
        idx_area = get_idx("prefer metro, suburban")
        idx_virtual = get_idx("virtual acquisitions")
        idx_prop_types = get_idx("What type of properties")
        idx_price = get_idx("ideal purchase price")
        idx_cash = get_idx("cash buyer")
        idx_deal_struct = get_idx("deal structures")
        idx_equity = get_idx("equity spread")
        idx_condition = get_idx("property condition")
        idx_cheat = get_idx("Cheat Codes")
        idx_notes = get_idx("Anything else")

        for r in rows:
            def safe_get(idx):
                if idx != -1 and idx < len(r):
                    return r[idx].strip()
                return ""
                
            email = safe_get(idx_email)
            if not email:
                continue # Cannot deduplicate or track without email
            
            # 1. Create or GET the Buyer
            buyer, created = Buyer.objects.get_or_create(
                email=email,
                defaults={
                    'name': safe_get(idx_name) or "Unknown",
                    'company_name': safe_get(idx_company),
                    'phone': safe_get(idx_phone),
                    'blinq_or_website': safe_get(idx_blinq)[:500],
                    'location': safe_get(idx_location),
                }
            )
            
            if created:
                total_buyers_created += 1
            
            # 2. Check if BuyBox already exists to avoid duplicates
            buybox, box_created = BuyBox.objects.get_or_create(
                buyer=buyer,
                asset_type=title,
                defaults={
                    'target_states': safe_get(idx_states),
                    'area_preference': safe_get(idx_area),
                    'virtual_acquisitions': safe_get(idx_virtual),
                    'property_types': safe_get(idx_prop_types),
                    'price_range': safe_get(idx_price),
                    'is_cash_buyer': safe_get(idx_cash),
                    'deal_structures': safe_get(idx_deal_struct),
                    'equity_arv_requirement': safe_get(idx_equity),
                    'property_condition': safe_get(idx_condition),
                    'cheat_codes': safe_get(idx_cheat)[:255],
                    'strategy_notes': safe_get(idx_notes),
                }
            )
            if box_created:
                total_buyboxes_created += 1

    print("\n--- IMPORT COMPLETE ---")
    print(f"Total Unique Buyers Created: {total_buyers_created}")
    print(f"Total BuyBoxes (Preferences) Created: {total_buyboxes_created}")

if __name__ == '__main__':
    main()
