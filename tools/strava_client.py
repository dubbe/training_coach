import requests
import os
import json
import argparse
import re
import difflib
from datetime import datetime

# Try to load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- CONFIGURATION ---
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "../historik")

class StravaClient:
    BASE_URL = "https://www.strava.com/api/v3"

    def __init__(self, client_id=None, client_secret=None, refresh_token=None, access_token=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

    def _refresh_access_token(self):
        """Refreshes the access token using the refresh token."""
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise Exception("Missing Client ID, Secret or Refresh Token for refresh.")
        
        print("Refreshing Strava Access Token...")
        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token"
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"] # Can also change
        self.headers["Authorization"] = f"Bearer {self.access_token}"
        
        print("Token refreshed successfully.")
        return data

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 401: # Unauthorized, likely expired
            if self.refresh_token:
                self._refresh_access_token()
                # Retry once
                response = requests.get(url, headers=self.headers, params=params)
            else:
                print("Access token expired and no refresh token available.")
        
        if response.status_code >= 400:
            print(f"Strava API Error: {response.text}")
        response.raise_for_status()
        return response.json()

    def get_activities(self, limit=5):
        """Fetch latest athlete activities."""
        return self._get("athlete/activities", params={"per_page": limit})

class MarkdownFormatter:
    @staticmethod
    def activity_to_markdown(activity):
        """Converts Strava activity JSON to Markdown."""
        name = activity.get("name", "Running")
        start_date_raw = activity.get("start_date_local", "")
        start_date = start_date_raw[:10]
        start_time = start_date_raw[11:16]
        
        distance_km = activity.get("distance", 0) / 1000
        duration_sec = activity.get("moving_time", 0)
        
        if distance_km > 0:
            pace_sec_km = duration_sec / distance_km
            pace_min = int(pace_sec_km // 60)
            pace_sec = int(pace_sec_km % 60)
            pace_str = f"{pace_min}:{pace_sec:02d} min/km"
        else:
            pace_str = "N/A"

        hours, remainder = divmod(duration_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m {seconds}s"

        avg_hr = activity.get("average_heartrate", "N/A")
        max_hr = activity.get("max_heartrate", "N/A")

        md = f"# Strava: {name}\n\n"
        md += f"**Datum:** {start_date}\n"
        md += f"**Tid:** {start_time}\n"
        md += f"**Varaktighet:** {duration_str}\n\n"
        
        md += "## Statistik\n\n"
        md += f"| Metric          | Value               |\n"
        md += f"|-----------------|---------------------|\n"
        md += f"| Distans         | {distance_km:.2f} km        |\n"
        md += f"| Medeltempo      | {pace_str}        |\n"
        md += f"| Medelpuls       | {avg_hr} bpm             |\n"
        md += f"| Maxpuls         | {max_hr} bpm             |\n"
        md += f"| Höjdvinst       | {activity.get('total_elevation_gain', 0)} m            |\n"
        md += f"| Typ             | {activity.get('type', 'Run')}            |\n"
        
        return md, start_date, name

def main():
    parser = argparse.ArgumentParser(description="Strava API Tool")
    subparsers = parser.add_subparsers(dest="command")
    
    import_parser = subparsers.add_parser("import_activities", help="Strava -> MD")
    import_parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    access_token = os.environ.get("STRAVA_TOKEN")
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN") or access_token
    
    if not refresh_token and not access_token:
        print("Error: STRAVA_TOKEN or STRAVA_REFRESH_TOKEN not set.")
        return
    
    client = StravaClient(
        client_id=client_id, 
        client_secret=client_secret, 
        refresh_token=refresh_token, 
        access_token=access_token or "dummy" # Will force a refresh if invalid
    )

    if args.command == "import_activities":
        print(f"Importing last {args.limit} activities from Strava...")
        try:
            activities = client.get_activities(limit=args.limit)
            
            if not os.path.exists(HISTORY_DIR):
                os.makedirs(HISTORY_DIR)

            for act in activities:
                md, date_str, name = MarkdownFormatter.activity_to_markdown(act)
                safe_title = re.sub(r'[^a-zA-Z0-9]', '_', name)
                safe_title = re.sub(r'_+', '_', safe_title).strip('_')
                filename = f"{date_str}_Strava_{safe_title}.md"
                path = os.path.join(HISTORY_DIR, filename)

                existing_files_for_date = [f for f in os.listdir(HISTORY_DIR) if f.startswith(date_str)]
                is_duplicate = False
                for existing_file in existing_files_for_date:
                    existing_title_part = existing_file[len(date_str)+1:-3]
                    ratio = difflib.SequenceMatcher(None, safe_title.lower(), existing_title_part.lower()).ratio()
                    if ratio > 0.8:
                        print(f"Skipped duplicate: {filename}")
                        is_duplicate = True
                        break
                
                if is_duplicate: continue

                with open(path, 'w') as f:
                    f.write(md)
                print(f"Saved: {filename}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()