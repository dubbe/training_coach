import requests
import os
import json
import argparse
import difflib
import re
from datetime import datetime

# Try to load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- CONFIGURATION ---
EXERCISE_DB_PATH = os.path.join(os.path.dirname(__file__), "hevy_exercises.json")
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "../historik")

class HevyClient:
    BASE_URL = "https://api.hevyapp.com/v1"

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, data):
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code >= 400:
            print(f"API Error Response: {response.text}")
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError:
            content = response.text.strip('"')
            if "exercise" in data:
                return {"exercise_template": {"id": content, "title": data["exercise"]["title"]}}
            return {"id": content}

    def get_workouts(self, page=1, page_size=10):
        return self._get("workouts", {"page": page, "pageSize": page_size})

    def get_exercise_templates(self, page=1, page_size=100):
        all_templates = []
        while True:
            try:
                data = self._get("exercise_templates", {"page": page, "pageSize": page_size})
                templates = data.get("exercise_templates", [])
                if not templates:
                    break
                all_templates.extend(templates)
                page += 1
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    break
                raise e
            if page > 50:
                break
        return all_templates

    def create_exercise_template(self, title, exercise_type="weight_reps", muscle_group="other", other_muscles=None, equipment="none"):
        payload = {
            "exercise": {
                "title": title,
                "exercise_type": exercise_type,
                "muscle_group": muscle_group,
                "equipment_category": equipment
            }
        }
        if other_muscles:
            payload["exercise"]["other_muscles"] = other_muscles
        return self._post("exercise_templates", payload)

    def create_routine(self, title, exercises, notes="", folder_id=None):
        payload = {
            "routine": {
                "title": title,
                "folder_id": folder_id,
                "notes": notes,
                "exercises": exercises
            }
        }
        return self._post("routines", payload)

class ExerciseDB:
    def __init__(self):
        self.exercises = []
        self.load()

    def load(self):
        if os.path.exists(EXERCISE_DB_PATH):
            with open(EXERCISE_DB_PATH, 'r') as f:
                self.exercises = json.load(f)

    def save(self, exercises):
        self.exercises = exercises
        with open(EXERCISE_DB_PATH, 'w') as f:
            json.dump(exercises, f, indent=2)

    def add_exercise(self, exercise):
        if any(ex['id'] == exercise['id'] for ex in self.exercises):
            return
        self.exercises.append(exercise)
        self.save(self.exercises)

    def find_by_name(self, name):
        for ex in self.exercises:
            if ex['title'].lower() == name.lower():
                return ex
        name_map = {ex['title'].lower(): ex for ex in self.exercises}
        matches = difflib.get_close_matches(name.lower(), name_map.keys(), n=1, cutoff=0.85)
        if matches:
            return name_map[matches[0]]
        return None

class MarkdownParser:
    @staticmethod
    def workout_to_markdown(workout):
        date_str = workout.get("start_time", "")[:10]
        title = workout.get("title", "Workout")
        desc = workout.get("description", "")
        start = datetime.fromisoformat(workout["start_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(workout["end_time"].replace("Z", "+00:00"))
        duration = end - start
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        md = f"# {title}\n\n"
        md += f"**Datum:** {date_str}\n"
        md += f"**Tid:** {start.strftime('%H:%M')} - {end.strftime('%H:%M')}\n"
        md += f"**Varaktighet:** {duration_str}\n\n"
        if desc: md += f"_{desc}_\n\n"
        md += "## Övningar\n\n"
        for exercise in workout.get("exercises", []):
            ex_title = exercise.get("title", "Unknown Exercise")
            md += f"### {ex_title}\n"
            for i, set_data in enumerate(exercise.get("sets", []), 1):
                weight = set_data.get("weight_kg")
                reps = set_data.get("reps")
                dist = set_data.get("distance_meters")
                dur = set_data.get("duration_seconds")
                line = f"* Set {i}:";
                if weight: line += f" {reps} reps @ {weight} kg"
                elif reps: line += f" {reps} reps"
                if dist: line += f" {dist}m"
                if dur: line += f" {dur}s"
                if set_data.get("indicator") == "personal_best": line += " (PR!)"
                md += f"{line}\n"
            md += "\n"
        return md, date_str, title

    @staticmethod
    def parse_plan_file(file_path, exercise_db, client):
        with open(file_path, 'r') as f:
            lines = f.readlines()

        detected_exercises = []
        current_exercise = None
        
        ex_pattern = re.compile(r"^\s*[\*\-]?\s*\*\*([^\*]+)\*\*|^\s*###\s*(.+)")
        # Updated regex to capture comment in parens or at end of line
        set_pattern = re.compile(r"Set\s+(\d+):\s*(?:(\d+)\s*reps)?\s*(?:@\s*(\d+(?:\.\d+)?)\s*kg)?\s*(?:(\d+)\s*(?:s|sek))?\s*(?:\(([^)]+)\)|(.*))?")
        # Regex to capture rest time: "**Vila:** 90s" or "**Rest:** 90s"
        rest_pattern = re.compile(r"^\s*\*\*(?:Vila|Rest):\*\*\s*(\d+)")

        print(f"Scanning {file_path} for exercises...")

        for line in lines:
            # Check for Rest time FIRST
            rest_match = rest_pattern.search(line)
            if rest_match:
                if current_exercise:
                    rest_seconds = int(rest_match.group(1))
                    current_exercise["rest_seconds"] = rest_seconds
                    print(f"    Rest set to {rest_seconds}s")
                continue # Skip looking for exercise name on this line

            match = ex_pattern.search(line)
            if match:
                raw_name = (match.group(1) or match.group(2)).split(":")[0].strip()
                if raw_name.lower() in ["datum", "tid", "varaktighet", "mål", "syfte", "pass", "fokus", "uppvärmning", "kondition", "styrka", "notes", "goalkeeper fitness"]:
                    continue

                hevy_ex = exercise_db.find_by_name(raw_name)
                
                if not hevy_ex:
                    print(f"  [!] Creating custom exercise: {raw_name}")
                    try:
                        ex_type = "weight_reps"
                        muscle = "other"
                        equipment = "none"
                        lower_name = raw_name.lower()
                        
                        if any(x in lower_name for x in ["drill", "quick feet", "snabba", "plank", "hold", "vila", "line"]):
                            ex_type = "duration"
                            muscle = "cardio" if "feet" in lower_name or "line" in lower_name else "abdominals"
                        elif any(x in lower_name for x in ["jump", "hopp", "step", "plyo", "bound"]):
                            ex_type = "reps_only"
                            muscle = "quadriceps" 
                        elif any(x in lower_name for x in ["run", "intervals"]):
                            ex_type = "distance_duration"; muscle = "cardio"
                        
                        resp = client.create_exercise_template(raw_name, exercise_type=ex_type, muscle_group=muscle, equipment=equipment)
                        if isinstance(resp, dict):
                            hevy_ex = resp.get("exercise_template") or resp
                            if "id" in hevy_ex:
                                exercise_db.add_exercise(hevy_ex)
                            elif "id" in resp: # Fallback if direct ID dict
                                hevy_ex = {"id": resp["id"], "title": raw_name}
                                exercise_db.add_exercise(hevy_ex)
                    except Exception as e:
                        print(f"      Failed to create exercise '{raw_name}': {e}")
                        continue

                if hevy_ex and isinstance(hevy_ex, dict) and "id" in hevy_ex:
                    current_exercise = {
                        "exercise_template_id": hevy_ex['id'],
                        "superset_id": None,
                        "rest_seconds": 90, # Default rest
                        "notes": "",
                        "sets": []
                    }
                    detected_exercises.append(current_exercise)
                    print(f"  Mapped: {raw_name} -> {hevy_ex['title']} ({hevy_ex['id']})")

            elif current_exercise and "Set" in line:
                set_match = set_pattern.search(line)
                if set_match:
                    set_num = set_match.group(1)
                    reps = int(set_match.group(2)) if set_match.group(2) else None
                    weight = float(set_match.group(3)) if set_match.group(3) else None
                    duration = int(set_match.group(4)) if set_match.group(4) else None
                    comment = (set_match.group(5) or set_match.group(6) or "").strip()
                    
                    if comment:
                         if current_exercise["notes"]:
                            current_exercise["notes"] += "\n"
                         current_exercise["notes"] += f"Set {set_num}: {comment}"
                    
                    current_exercise["sets"].append({
                        "type": "normal",
                        "weight_kg": weight,
                        "reps": reps,
                        "distance_meters": None,
                        "duration_seconds": duration,
                        "custom_metric": None
                    })

        # Add a default set if none were parsed
        for ex in detected_exercises:
            if not ex["sets"]:
                ex["sets"].append({"type": "normal", "weight_kg": None, "reps": 1, "distance_meters": None, "duration_seconds": None, "custom_metric": None})

        return detected_exercises

def main():
    parser = argparse.ArgumentParser(description="Hevy API Tool")
    parser.add_argument("--api-key", help="Hevy API Key")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("sync_exercises", help="Download all exercises")
    
    import_parser = subparsers.add_parser("import_workouts", help="Hevy -> MD")
    import_parser.add_argument("--limit", type=int, default=5)
    
    export_parser = subparsers.add_parser("export_routine", help="MD -> Hevy")
    export_parser.add_argument("file", help="Path to MD file")
    export_parser.add_argument("--title", help="Title", default=None)

    args = parser.parse_args()
    api_key = args.api_key or os.environ.get("HEVY_API_KEY")
    if not api_key:
        print("Error: HEVY_API_KEY not set.")
        return
    
    client = HevyClient(api_key)
    db = ExerciseDB()

    if args.command == "sync_exercises":
        print("Syncing exercises...")
        exercises = client.get_exercise_templates()
        db.save(exercises)
    
    elif args.command == "import_workouts":
        print(f"Importing last {args.limit} workouts...")
        workouts_data = client.get_workouts(page_size=args.limit)
        workouts = workouts_data.get("workouts", []) if isinstance(workouts_data, dict) else []
        for w in workouts:
            md, date_str, title = MarkdownParser.workout_to_markdown(w)
            safe_title = re.sub(r'_+', '_', re.sub(r'[^a-zA-Z0-9]', '_', title)).strip('_')
            filename = f"{date_str}_{safe_title}.md"
            path = os.path.join(HISTORY_DIR, filename)
            
            if any(f.startswith(date_str) and difflib.SequenceMatcher(None, safe_title.lower(), f[len(date_str)+1:-3].lower()).ratio() > 0.8 for f in os.listdir(HISTORY_DIR)):
                print(f"Skipped duplicate: {filename}")
                continue
            
            with open(path, 'w') as f:
                f.write(md)
            print(f"Saved: {filename}")
            
    elif args.command == "export_routine":
        exercises = MarkdownParser.parse_plan_file(args.file, db, client)
        
        # Use filename as title if none provided
        title = args.title
        if not title:
            base_name = os.path.basename(args.file).replace(".md", "").replace("_", " ")
            title = f"{datetime.now().strftime('%Y-%m-%d')}: {base_name}"

        if exercises:
            print(f"Exporting routine '{title}'...")
            try:
                resp = client.create_routine(title, exercises, notes=f"Imported from {args.file}")
                
                routine_id = "Unknown"
                if isinstance(resp, dict):
                    routine = resp.get("routine", resp)
                    if isinstance(routine, dict):
                        routine_id = routine.get("id", "Unknown")
                elif isinstance(resp, str):
                    routine_id = resp
                
                print(f"Routine created successfully! ID: {routine_id}")
            except Exception as e:
                print(f"Error creating routine: {e}")

if __name__ == "__main__":
    main()
