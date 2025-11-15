#!/usr/bin/env python3
"""
Generate static HTML scoreboard from cached Swimtopia API data
Similar to wahoo-results but using Swimtopia data
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def load_athletes() -> Dict[str, Dict]:
    """Load athlete data and create ID -> athlete mapping"""
    athletes = {}
    cache_dir = Path("api_cache")

    for athlete_file in cache_dir.glob("*athletes*.json"):
        try:
            with open(athlete_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            athlete_list = data.get("data", [])
            for athlete in athlete_list:
                athlete_id = athlete.get("id")
                attrs = athlete.get("attributes", {})
                athletes[athlete_id] = {
                    "firstName": attrs.get("firstName"),
                    "lastName": attrs.get("lastName"),
                    "displayName": f"{attrs.get('displayFirstName', attrs.get('firstName', ''))} {attrs.get('lastName', '')}".strip(),
                }
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Error loading {athlete_file}: {e}")

    return athletes


def format_time(time_int):
    """Format time integer to MM:SS.ss"""
    if not time_int:
        return "NT"
    minutes = time_int // 6000
    seconds = (time_int % 6000) / 100
    if minutes > 0:
        return f"{minutes}:{seconds:05.2f}"
    return f"{seconds:.2f}"


def load_all_events() -> List[Dict]:
    """Load all events from events list files and event-nodes files"""
    cache_dir = Path("api_cache")
    all_events = []

    # Load events list files
    events_list_files = list(cache_dir.glob("*events_2*.json"))
    event_nodes_files = list(cache_dir.glob("*event-nodes*.json"))

    for events_file in events_list_files:
        # Skip event detail files (they have ID in name)
        if "events_ID" in events_file.name:
            continue

        try:
            with open(events_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                events_data = data.get("data", [])
                all_events.extend(events_data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Error loading {events_file}: {e}")

    # Also load from event-nodes files (which have more complete event list)
    for nodes_file in event_nodes_files:
        try:
            with open(nodes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                nodes_data = data.get("data", [])

                # Convert eventNode to event format
                for node in nodes_data:
                    if node.get("type") == "eventNode":
                        # Extract event reference
                        event_ref = node.get("relationships", {}).get("event", {}).get("data", {})
                        if event_ref:
                            event_id = event_ref.get("id")
                            # Create event object from node attributes
                            event = {
                                "id": event_id,
                                "type": "event",
                                "attributes": node.get("attributes", {})
                            }
                            all_events.append(event)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Error loading {nodes_file}: {e}")

    # Deduplicate by event ID (prefer non-node data if available)
    events_by_id = {}
    for event in all_events:
        event_id = event.get("id")
        # Prefer events with more complete data (from events endpoint vs nodes)
        if event_id not in events_by_id:
            events_by_id[event_id] = event

    unique_events = list(events_by_id.values())

    # Sort by event number
    unique_events.sort(key=lambda e: int(e.get("attributes", {}).get("eventNumber", "999")))

    return unique_events


def load_event_details(event_id: str) -> Dict:
    """Load detailed event data including heats and records"""
    cache_dir = Path("api_cache")

    # Look for event detail files
    event_detail_files = list(cache_dir.glob(f"*events_ID_*.json"))

    for detail_file in event_detail_files:
        try:
            with open(detail_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                event_data = data.get("data", {})

                if event_data.get("id") == event_id:
                    # Add included data
                    event_data["included"] = data.get("included", [])
                    return event_data
        except (json.JSONDecodeError, Exception):
            continue

    return {}


def generate_scoreboard_html(all_events: List[Dict], athletes: Dict) -> str:
    """Generate HTML scoreboard from events data"""

    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Swim Meet Scoreboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Arial', 'Helvetica Neue', sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 20px;
            min-height: 100vh;
        }

        .scoreboard {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            padding: 30px 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
        }

        .header .timestamp {
            font-size: 1.2em;
            opacity: 0.8;
        }

        .event-container {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 40px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
        }

        .event-container.no-details {
            opacity: 0.6;
            padding: 20px;
        }

        .event-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px 30px;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        }

        .event-header h2 {
            font-size: 2.5em;
            margin-bottom: 5px;
        }

        .event-header .event-details {
            font-size: 1.3em;
            opacity: 0.9;
        }

        .heat-header {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px 25px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 1.8em;
            font-weight: bold;
            text-align: center;
            border-left: 5px solid #ffd700;
        }

        .lane-results {
            display: grid;
            gap: 15px;
        }

        .lane {
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.15) 0%, rgba(255, 255, 255, 0.05) 100%);
            border-radius: 10px;
            padding: 20px 25px;
            display: grid;
            grid-template-columns: 80px 200px 1fr 150px 120px 100px;
            align-items: center;
            gap: 20px;
            transition: all 0.3s ease;
            border-left: 5px solid transparent;
        }

        .lane:hover {
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.25) 0%, rgba(255, 255, 255, 0.15) 100%);
            transform: translateX(5px);
        }

        .lane.place-1 {
            border-left-color: #ffd700;
            background: linear-gradient(90deg, rgba(255, 215, 0, 0.2) 0%, rgba(255, 255, 255, 0.05) 100%);
        }

        .lane.place-2 {
            border-left-color: #c0c0c0;
            background: linear-gradient(90deg, rgba(192, 192, 192, 0.2) 0%, rgba(255, 255, 255, 0.05) 100%);
        }

        .lane.place-3 {
            border-left-color: #cd7f32;
            background: linear-gradient(90deg, rgba(205, 127, 50, 0.2) 0%, rgba(255, 255, 255, 0.05) 100%);
        }

        .lane-number {
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
            color: #ffd700;
        }

        .team-name {
            font-size: 1.3em;
            font-weight: bold;
            color: #ffeb3b;
        }

        .athlete-names {
            font-size: 1.3em;
        }

        .relay-swimmers {
            font-size: 1.1em;
            opacity: 0.9;
            margin-top: 5px;
        }

        .relay-swimmer {
            display: block;
            padding: 2px 0;
        }

        .splits {
            font-size: 0.9em;
            opacity: 0.7;
            margin-top: 8px;
            padding: 8px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
        }

        .split-time {
            display: inline-block;
            margin-right: 12px;
            padding: 2px 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }

        .seed-time {
            font-size: 1.4em;
            text-align: right;
            opacity: 0.7;
        }

        .result-time {
            font-size: 2em;
            font-weight: bold;
            text-align: right;
            color: #4cff4c;
        }

        .result-time.nt {
            color: #ff6b6b;
            font-size: 1.5em;
        }

        .place {
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
        }

        .place.first {
            color: #ffd700;
        }

        .place.second {
            color: #c0c0c0;
        }

        .place.third {
            color: #cd7f32;
        }

        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-left: 15px;
        }

        .status-badge.seeded {
            background: rgba(255, 193, 7, 0.3);
            color: #ffc107;
            border: 2px solid #ffc107;
        }

        .status-badge.completed {
            background: rgba(76, 175, 80, 0.3);
            color: #4caf50;
            border: 2px solid #4caf50;
        }

        .status-badge.no-details {
            background: rgba(158, 158, 158, 0.3);
            color: #9e9e9e;
            border: 2px solid #9e9e9e;
        }

        .no-details-message {
            text-align: center;
            font-size: 1.2em;
            opacity: 0.6;
            padding: 20px;
        }

        @media (max-width: 1200px) {
            .lane {
                grid-template-columns: 60px 150px 1fr 120px 100px 80px;
                padding: 15px 20px;
                font-size: 0.9em;
            }
        }

        @media (max-width: 768px) {
            .lane {
                grid-template-columns: 1fr;
                gap: 10px;
                text-align: center;
            }

            .lane-number, .team-name, .seed-time, .result-time, .place {
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="scoreboard">
        <div class="header">
            <h1>SWIM MEET SCOREBOARD</h1>
            <div class="timestamp">Generated: """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """</div>
        </div>
"""

    for event in all_events:
        event_attrs = event.get("attributes", {})
        event_id = event.get("id")
        event_num = event_attrs.get("eventNumber", "?")
        event_label = event_attrs.get("label", "Unknown Event")
        event_type = event_attrs.get("eventType", "individual")
        state = event_attrs.get("state", "seeded")

        # Try to load detailed event data
        event_details = load_event_details(event_id)
        has_details = bool(event_details)

        # Determine status badge
        if state == "scored":
            status_text = "SCORED (No Details)" if not has_details else "SCORED"
            status_class = "completed"
        elif state == "partial":
            status_text = "PARTIAL (No Details)" if not has_details else "PARTIAL"
            status_class = "seeded"
        elif state == "unseeded":
            status_text = "UNSEEDED (No Details)" if not has_details else "UNSEEDED"
            status_class = "no-details"
        elif has_details:
            status_text = state.upper()
            status_class = "seeded"
        else:
            status_text = f"{state.upper()} (No Details)"
            status_class = "no-details"

        container_class = "no-details" if not has_details else ""

        html += f"""
        <div class="event-container {container_class}">
            <div class="event-header">
                <h2>Event #{event_num}</h2>
                <div class="event-details">
                    {event_label}
                    <span class="status-badge {status_class}">{status_text}</span>
                </div>
            </div>
"""

        if not has_details:
            html += """
            <div class="no-details-message">Heat and lane details not available in cache</div>
"""
        else:
            # Process heats from detailed data
            included = event_details.get("included", [])

            # Build lookup maps
            heats = {}
            event_records = {}
            relay_positions = {}
            splits_data = {}

            for item in included:
                item_type = item.get("type")
                item_id = item.get("id")

                if item_type == "heat":
                    heats[item_id] = item.get("attributes", {})
                elif item_type == "eventRecord":
                    event_records[item_id] = item
                elif item_type == "relayPositionRecord":
                    relay_positions[item_id] = item
                elif item_type == "split":
                    splits_data[item_id] = item

            # Group records by heat
            records_by_heat = {}
            for record_id, record in event_records.items():
                heat_number = record.get("attributes", {}).get("heatNumber")
                if heat_number not in records_by_heat:
                    records_by_heat[heat_number] = []
                records_by_heat[heat_number].append(record)

            # Display each heat
            for heat_num in sorted(records_by_heat.keys()):
                records = sorted(
                    records_by_heat[heat_num],
                    key=lambda r: r.get("attributes", {}).get("laneNumber", 0)
                )

                html += f"""
            <div class="heat-header">HEAT {heat_num}</div>
            <div class="lane-results">
"""

                for record in records:
                    attrs = record.get("attributes", {})
                    lane = attrs.get("laneNumber", "?")
                    team = attrs.get("teamAbbreviation", "?")
                    seed_time = format_time(attrs.get("seedTimeInt"))
                    result_time = format_time(attrs.get("officialTimeInt") or attrs.get("resultTimeInt"))
                    place = attrs.get("overallPlace") or attrs.get("heatPlace")

                    # Check for splits
                    splits_refs = record.get("relationships", {}).get("splits", {}).get("data", [])
                    split_times_html = ""
                    if splits_refs:
                        split_times = []
                        for split_ref in splits_refs:
                            split_id = split_ref.get("id")
                            if split_id in splits_data:
                                split_item = splits_data[split_id]
                                split_attrs = split_item.get("attributes", {})
                                split_distance = split_attrs.get("distance", "?")
                                split_time = format_time(split_attrs.get("splitTimeInt"))
                                split_times.append(f'<span class="split-time">{split_distance}y: {split_time}</span>')
                        if split_times:
                            split_times_html = '<div class="splits">Splits: ' + " ".join(split_times) + '</div>'

                    # Determine place class
                    place_class = ""
                    place_display = ""
                    if place == 1:
                        place_class = "place-1"
                        place_display = '<span class="place first">1st</span>'
                    elif place == 2:
                        place_class = "place-2"
                        place_display = '<span class="place second">2nd</span>'
                    elif place == 3:
                        place_class = "place-3"
                        place_display = '<span class="place third">3rd</span>'
                    elif place:
                        place_display = f'<span class="place">{place}</span>'
                    else:
                        place_display = '<span class="place">-</span>'

                    # Build athlete display
                    if event_type == "relay":
                        relay_team_name = attrs.get("relayTeamName", f"{team}")
                        relay_pos_data = record.get("relationships", {}).get("relayPositionRecords", {}).get("data", [])

                        swimmers_html = []
                        for relay_pos_ref in sorted(relay_pos_data, key=lambda x: relay_positions.get(x.get("id"), {}).get("attributes", {}).get("relayPosition", 99)):
                            pos_id = relay_pos_ref.get("id")
                            if pos_id in relay_positions:
                                pos_record = relay_positions[pos_id]
                                pos_num = pos_record.get("attributes", {}).get("relayPosition")
                                athlete_ref = pos_record.get("relationships", {}).get("athlete", {}).get("data")

                                if athlete_ref:
                                    athlete_id = athlete_ref.get("id")
                                    athlete_info = athletes.get(athlete_id, {})
                                    athlete_name = athlete_info.get("displayName", "Unknown")
                                    swimmers_html.append(f'<span class="relay-swimmer">{pos_num}. {athlete_name}</span>')

                        swimmers_str = "\n".join(swimmers_html) if swimmers_html else "No swimmers"
                        athlete_display = f'<div class="team-name">{relay_team_name}</div><div class="relay-swimmers">{swimmers_str}</div>'
                    else:
                        athlete_ref = record.get("relationships", {}).get("athlete", {}).get("data")
                        if athlete_ref:
                            athlete_id = athlete_ref.get("id")
                            athlete_info = athletes.get(athlete_id, {})
                            athlete_name = athlete_info.get("displayName", "Unknown")
                        else:
                            athlete_name = "No athlete"
                        athlete_display = f'<div class="team-name">{team}</div><div>{athlete_name}</div>{split_times_html}'

                    result_class = "nt" if result_time == "NT" else ""

                    html += f"""
                <div class="lane {place_class}">
                    <div class="lane-number">{lane}</div>
                    <div class="athlete-names">{athlete_display}</div>
                    <div></div>
                    <div class="seed-time">Seed: {seed_time}</div>
                    <div class="result-time {result_class}">{result_time}</div>
                    {place_display}
                </div>
"""

                html += """
            </div>
"""

        html += """
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    return html


def main():
    """Main entry point"""
    print("=== Generating Swim Meet Scoreboard ===\n")

    cache_dir = Path("api_cache")
    if not cache_dir.exists():
        print("❌ api_cache/ directory not found")
        return

    # Load athletes
    print("Loading athlete data...")
    athletes = load_athletes()
    print(f"  Loaded {len(athletes)} athletes")

    # Load all events
    print("\nLoading all events...")
    all_events = load_all_events()
    print(f"  Found {len(all_events)} events")

    # Generate HTML
    print("\nGenerating scoreboard HTML...")
    html = generate_scoreboard_html(all_events, athletes)

    # Write to file
    output_file = Path("scoreboard.html")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Scoreboard generated: {output_file.absolute()}")
    print("\n   Open scoreboard.html in your browser to view!")


if __name__ == "__main__":
    main()
