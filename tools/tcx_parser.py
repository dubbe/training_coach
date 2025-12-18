import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def parse_tcx(file_path):
    try:
        # Register namespace to handle the default Garmin namespace
        namespaces = {'tcx': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
        
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        activity = root.find('tcx:Activities/tcx:Activity', namespaces)
        if activity is None:
            print("Kunde inte hitta någon aktivitet i filen.")
            return

        sport = activity.get('Sport', 'Okänd')
        lap = activity.find('tcx:Lap', namespaces)
        if lap is None:
            print("Kunde inte hitta någon varvdata i aktiviteten.")
            return

        # Extract summary data
        start_time_str = lap.get('StartTime', 'N/A')
        total_time_sec = lap.findtext('tcx:TotalTimeSeconds', '0', namespaces)
        calories = lap.findtext('tcx:Calories', '0', namespaces)
        avg_hr = lap.findtext('tcx:AverageHeartRateBpm/tcx:Value', '0', namespaces)
        max_hr = lap.findtext('tcx:MaximumHeartRateBpm/tcx:Value', '0', namespaces)
        distance = lap.findtext('tcx:DistanceMeters', None, namespaces) # Check for distance

        # --- Presentation ---
        print("Här är en sammanfattning av passet från TCX-filen:\n")
        
        # Format duration
        duration_td = timedelta(seconds=float(total_time_sec))
        
        print(f"| Metric          | Value               |")
        print(f"|-----------------|---------------------|")
        print(f"| Typ av aktivitet| {sport}               |")
        print(f"| Starttid (UTC)  | {start_time_str}      |")
        print(f"| Varaktighet     | {str(duration_td)}          |")
        print(f"| Kalorier        | {calories} kcal            |")
        print(f"| Medelpuls       | {avg_hr} bpm             |")
        print(f"| Maxpuls         | {max_hr} bpm             |")

        if distance:
            print(f"| Distans         | {float(distance) / 1000:.2f} km        |")
        else:
            print("\nNotera: Filen innehåller ingen data om distans, så jag kan inte räkna ut tempo eller hastighet.")


    except ET.ParseError:
        print("Kunde inte tolka filen. Den verkar inte vara en giltig XML/TCX-fil.")
    except Exception as e:
        print(f"Ett oväntat fel uppstod: {e}")

if __name__ == "__main__":
    parse_tcx('Zepp20251215183211.tcx')
