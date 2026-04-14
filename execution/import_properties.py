import os
import sys
import django
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Setup Django Environment
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from properties.models import Property, Contact

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def main():
    creds_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = '1CiGtsD7yBvw8S5VVt1YkNO9puwa0kEGdqTKG-fhPDSU'
    
    spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets_metadata = spreadsheet.get('sheets', '')
    
    total_properties_created = 0
    total_contacts_created = 0

    for s in sheets_metadata:
        title = s.get('properties', {}).get('title', '')
        range_name = f"'{title}'!A1:Z5000" # Use large range in case of big list
        
        print(f"\nProcessing Sheet: {title}")
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            print("  -> Empty or headers only. Skipping.")
            continue
            
        headers = values[0]
        rows = values[1:]
        
        def get_idx(header_name):
            for i, h in enumerate(headers):
                if header_name.lower() in h.lower():
                    return i
            return -1

        idx_company = get_idx("Company")
        idx_address = get_idx("Address")
        idx_city = get_idx("City")
        idx_state = get_idx("State")
        idx_zip = get_idx("Zip")
        idx_county = get_idx("County")
        idx_phone = get_idx("Phone") # Careful, there's Phone and Direct Phone
        
        # We need exact index match for 'Phone' vs 'Direct Phone'
        idx_main_phone = -1
        idx_direct_phone = -1
        for i, h in enumerate(headers):
            if h.strip() == "Phone":
                idx_main_phone = i
            elif "Direct Phone" in h:
                idx_direct_phone = i

        idx_first = get_idx("Contact First")
        idx_last = get_idx("Contact Last")
        idx_title = get_idx("Title")
        idx_email = get_idx("Email")
        idx_website = get_idx("Website")
        idx_emp_range = get_idx("Employee Range")
        idx_annual_sales = get_idx("Annual Sales")
        idx_sic = get_idx("SIC Code")
        idx_industry = get_idx("Industry")

        for r in rows:
            def safe_get(idx):
                if idx != -1 and idx < len(r):
                    return r[idx].strip()
                return ""
                
            address = safe_get(idx_address)
            zip_code = safe_get(idx_zip)
            
            # Require minimal address info to create a property
            if not address or not zip_code:
                continue 
            
            company = safe_get(idx_company)
            
            # 1. Create or GET the Property
            prop, prop_created = Property.objects.get_or_create(
                address=address,
                zip_code=zip_code,
                defaults={
                    'city': safe_get(idx_city),
                    'state': safe_get(idx_state),
                    'county': safe_get(idx_county),
                    'company_name': company or "Unknown Property",
                    'main_phone': safe_get(idx_main_phone),
                    'website': safe_get(idx_website)[:500],
                    'employee_range': safe_get(idx_emp_range),
                    'annual_sales': safe_get(idx_annual_sales),
                    'sic_code': safe_get(idx_sic),
                    'industry': safe_get(idx_industry),
                }
            )
            
            if prop_created:
                total_properties_created += 1
            
            # 2. Check and Create Contact
            first_name = safe_get(idx_first)
            last_name = safe_get(idx_last)
            email = safe_get(idx_email)
            
            # To deduplicate same contact in case sheet has multiple rows with same person
            # We match on property + first + last (or email if we want to be stricter)
            if first_name or last_name or email:
                contact, contact_created = Contact.objects.get_or_create(
                    property=prop,
                    first_name=first_name,
                    last_name=last_name,
                    defaults={
                        'title': safe_get(idx_title),
                        'email': email,
                        'direct_phone': safe_get(idx_direct_phone),
                    }
                )
                if contact_created:
                    total_contacts_created += 1

    print("\n--- IMPORT COMPLETE ---")
    print(f"Total Unique Properties Created: {total_properties_created}")
    print(f"Total Contact Employees Created: {total_contacts_created}")

if __name__ == '__main__':
    main()
