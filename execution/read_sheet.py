import os.path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

def main():
    creds_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    SPREADSHEET_ID = '1CiGtsD7yBvw8S5VVt1YkNO9puwa0kEGdqTKG-fhPDSU'
    
    try:
        # Get spreadsheet metadata to see all sheets
        spreadsheet = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = spreadsheet.get('sheets', '')
        
        print(f"Found {len(sheets)} sheets.")
        
        for s in sheets:
            title = s.get('properties', {}).get('title', '')
            sheet_id = s.get('properties', {}).get('sheetId', '')
            range_name = f"'{title}'!A1:Z5" 
            
            print(f"\n--- Checking Sheet: {title} (ID: {sheet_id}) ---")
            result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
            values = result.get('values', [])

            if not values:
                print('No data found in rows 1-5.')
            else:
                for idx, row in enumerate(values):
                    # Filter out purely empty strings to make output cleaner
                    clean_row = [x for x in row if str(x).strip()]
                    if clean_row:
                        print(f"Row {idx+1}: {clean_row}")
                    
    except Exception as e:
        print(f"Error reading sheet: {e}")

if __name__ == '__main__':
    main()
