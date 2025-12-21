import os
import re
import csv
from datetime import datetime

# Configuration
SOURCE_DIR = 'historik'
OUTPUT_FILE = 'strong_export.csv'

# Strong CSV Headers (Matched to example file)
HEADERS = [
    'Date', 'Workout Name', 'Duration', 'Exercise Name', 'Set Order', 
    'Weight', 'Reps', 'Distance', 'Seconds', 'Notes', 'Workout Notes', 'RPE'
]

def parse_time_to_seconds(time_str):
    """Converts HH:MM:SS or MM:SS to seconds."""
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0

def clean_exercise_name(name):
    """Removes markdown bolding etc. and tries to match Strong naming conventions if possible."""
    name = name.replace('*', '').strip()
    
    # Simple mapping to match Strong's naming style (Barbell) etc.
    if "Knäböj" in name or "Squat" in name:
        if "Split" not in name: return "Squat (Barbell)"
    if "Bänkpress" in name or "Bench Press" in name:
        return "Bench Press (Barbell)"
    if "Militärpress" in name or "Overhead Press" in name:
        return "Overhead Press (Barbell)"
    if "Marklyft" in name or "Deadlift" in name:
        return "Deadlift (Barbell)"
    if "Stångrodd" in name or "Barbell Row" in name:
        return "Pendlay Row (Barbell)" # Strong often uses Pendlay or Barbell Row
        
    return name

def main():
    rows = []
    
    files = sorted([f for f in os.listdir(SOURCE_DIR) if f.endswith('.md')])
    
    print(f"Hittade {len(files)} filer. Börjar konvertera...")

    for filename in files:
        # Skip Running and Football files based on filename
        if '_Löpning' in filename or '_Fotboll' in filename:
            continue

        filepath = os.path.join(SOURCE_DIR, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.readlines()

        # Extract Date from filename (YYYY-MM-DD)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if not date_match:
            continue
        
        # Format date as YYYY-MM-DD HH:MM:SS (Defaulting to noon)
        date_str = date_match.group(1) + " 12:00:00"

        workout_name = "Styrkepass"
        current_exercise = None
        set_order = 1
        workout_notes = "" # Aggregated workout notes if found

        # First pass to find title
        if content and content[0].startswith('# '):
            raw_title = content[0].replace('# ', '').strip()
            workout_name = re.sub(r'\s*\(\d{4}-\d{2}-\d{2}\)', '', raw_title)

        if "Löppass" in workout_name or "Fotboll" in workout_name:
            continue

        for line in content:
            line = line.strip()

            # Exercise Header
            if line.startswith('## '):
                current_exercise = clean_exercise_name(line.replace('## ', ''))
                set_order = 1
            
            # Sub-header
            elif line.startswith('### ') and not "Sammanfattning" in line:
                current_exercise = clean_exercise_name(line.replace('### ', ''))
                set_order = 1

            # Sets
            elif line.startswith('*') and (line.startswith('*   Set') or line.startswith('* Set')):
                if not current_exercise:
                    continue

                weight = 0.0
                reps = 0
                seconds = 0.0
                distance = 0
                notes = ""

                # Extract Weight (kg)
                weight_match = re.search(r'(\d+(?:\.\d+)?)\s*kg', line)
                if weight_match:
                    weight = float(weight_match.group(1))

                # Extract Reps
                reps_match = re.search(r'(\d+)\s*reps', line)
                if reps_match:
                    reps = int(reps_match.group(1))

                # Extract Time for plank etc
                time_match = re.search(r'(\d{2}:\d{2}(?:\d{2})?)', line)
                if time_match and not reps: 
                    seconds = float(parse_time_to_seconds(time_match.group(1)))

                # Special case: Box jumps notes
                if "box" in line.lower() and "(" in line:
                     note_match = re.search(r'\((.*?)\)', line)
                     if note_match:
                         notes = note_match.group(1)

                # Write Row
                rows.append({
                    'Date': date_str,
                    'Workout Name': workout_name,
                    'Duration': "1h", # Default duration per workout as placeholder
                    'Exercise Name': current_exercise,
                    'Set Order': set_order,
                    'Weight': weight if weight > 0 else "", # Empty if 0
                    'Reps': reps if reps > 0 else "",       # Empty if 0
                    'Distance': distance,
                    'Seconds': seconds if seconds > 0 else 0.0, # 0.0 for normal lifts
                    'Notes': notes,
                    'Workout Notes': workout_notes,
                    'RPE': ""
                })
                set_order += 1

    # Write to CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Klar! Konverterade {len(rows)} set till {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
