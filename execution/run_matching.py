import os
import sys
import django

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_api.settings')
django.setup()

from matcher.services import MatcherEngine

def main():
    print("--- Starting Matcher Engine ---")
    
    total_matches = MatcherEngine.run()

    print(f"Matched {total_matches} properties to suitable buyers.")
    print("--- Matcher Engine Complete ---")

if __name__ == '__main__':
    main()
