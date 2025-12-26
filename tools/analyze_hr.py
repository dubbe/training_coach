import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import sys

def parse_tcx_hr(file_path):
    namespaces = {'tcx': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    activity = root.find('tcx:Activities/tcx:Activity', namespaces)
    if not activity:
        return []

    points = []
    start_time = None

    for lap in activity.findall('tcx:Lap', namespaces):
        for track in lap.findall('tcx:Track', namespaces):
            for tp in track.findall('tcx:Trackpoint', namespaces):
                time_elem = tp.find('tcx:Time', namespaces)
                hr_elem = tp.find('tcx:HeartRateBpm/tcx:Value', namespaces)
                
                if time_elem is not None and hr_elem is not None:
                    t_str = time_elem.text
                    # Handle Z format
                    if t_str.endswith('Z'):
                        t_str = t_str[:-1]
                    # Simple parsing (assuming format is consistent YYYY-MM-DDTHH:MM:SS or .SSS)
                    # We'll just use datetime.fromisoformat if py3.7+ or strptime
                    try:
                        t = datetime.fromisoformat(t_str)
                    except ValueError:
                         # Fallback for milliseconds if simple isoformat fails
                         t = datetime.strptime(t_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")

                    if start_time is None:
                        start_time = t
                    
                    elapsed = (t - start_time).total_seconds()
                    hr = int(hr_elem.text)
                    points.append((elapsed, hr))
    return points

def analyze_intervals(points):
    # Intervals definitions (Start Min, End Min)
    intervals = [
        ("Warmup", 0, 10),
        ("Interval 1", 10, 14),
        ("Rest 1", 14, 16),
        ("Interval 2", 16, 20),
        ("Rest 2", 20, 22),
        ("Interval 3", 22, 26),
        ("Rest 3", 26, 28),
        ("Interval 4", 28, 32),
        ("Cooldown", 32, 100) # 32 to end
    ]
    
    print(f"{'Segment':<12} | {'Avg HR':<6} | {'Max HR':<6} | {'Min HR':<6} | {'Data Points'}")
    print("-" * 55)

    for name, start_min, end_min in intervals:
        start_sec = start_min * 60
        end_sec = end_min * 60
        
        segment_hrs = [hr for t, hr in points if start_sec <= t < end_sec]
        
        if segment_hrs:
            avg_hr = sum(segment_hrs) / len(segment_hrs)
            max_hr = max(segment_hrs)
            min_hr = min(segment_hrs)
            count = len(segment_hrs)
            print(f"{name:<12} | {avg_hr:<6.1f} | {max_hr:<6} | {min_hr:<6} | {count}")
        else:
            print(f"{name:<12} | N/A    | N/A    | N/A    | 0")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_hr.py <file.tcx>")
    else:
        pts = parse_tcx_hr(sys.argv[1])
        analyze_intervals(pts)
