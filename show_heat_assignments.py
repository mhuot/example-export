#!/usr/bin/env python3
"""
Display heat, lane, and athlete assignments from cached API data
"""

import json
from pathlib import Path
from typing import Dict


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


def show_event_details():
    """Show heat and lane assignments for events"""
    cache_dir = Path("api_cache")
    athletes = load_athletes()

    print(f"\n{'='*100}")
    print(f"HEAT AND LANE ASSIGNMENTS")
    print(f"{'='*100}\n")

    # Find event detail files
    event_files = list(cache_dir.glob("*events_ID*.json"))

    if not event_files:
        print("No event detail files found in cache")
        return

    for event_file in sorted(event_files):
        try:
            with open(event_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            event_data = data.get("data", {})
            event_attrs = event_data.get("attributes", {})
            included = data.get("included", [])

            # Event header
            event_num = event_attrs.get("eventNumber", "?")
            event_label = event_attrs.get("label", "Unknown Event")
            event_type = event_attrs.get("eventType", "individual")

            print(f"\n{'─'*100}")
            print(f"EVENT #{event_num}: {event_label} ({event_type.upper()})")
            print(f"{'─'*100}")

            # Build lookup maps
            heats = {}
            event_records = {}
            relay_positions = {}

            for item in included:
                item_type = item.get("type")
                item_id = item.get("id")

                if item_type == "heat":
                    heats[item_id] = item.get("attributes", {})
                elif item_type == "eventRecord":
                    event_records[item_id] = item
                elif item_type == "relayPositionRecord":
                    relay_positions[item_id] = item

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

                print(f"\n  Heat {heat_num}:")
                print(f"  {'Lane':<6} {'Team':<15} {'Athlete(s)':<50} {'Seed Time':<12}")
                print(f"  {'-'*90}")

                for record in records:
                    attrs = record.get("attributes", {})
                    lane = attrs.get("laneNumber", "?")
                    team = attrs.get("teamAbbreviation", "?")
                    seed_time = attrs.get("seedTimeInt")

                    # Format seed time
                    if seed_time:
                        minutes = seed_time // 6000
                        seconds = (seed_time % 6000) / 100
                        time_str = f"{minutes}:{seconds:05.2f}" if minutes > 0 else f"{seconds:.2f}"
                    else:
                        time_str = "NT"

                    # Get athlete(s)
                    if event_type == "relay":
                        # Get relay team designation
                        relay_team = attrs.get("relayTeam", "")
                        team_name = attrs.get("relayTeamName", f"{team} {relay_team}")

                        # Get relay position records
                        relay_pos_data = record.get("relationships", {}).get("relayPositionRecords", {}).get("data", [])

                        swimmers = []
                        for relay_pos_ref in relay_pos_data:
                            pos_id = relay_pos_ref.get("id")
                            if pos_id in relay_positions:
                                pos_record = relay_positions[pos_id]
                                pos_num = pos_record.get("attributes", {}).get("relayPosition")
                                athlete_ref = pos_record.get("relationships", {}).get("athlete", {}).get("data")

                                if athlete_ref:
                                    athlete_id = athlete_ref.get("id")
                                    athlete_info = athletes.get(athlete_id, {})
                                    athlete_name = athlete_info.get("displayName", f"Athlete {athlete_id[:8]}")
                                    swimmers.append(f"{pos_num}:{athlete_name}")

                        swimmer_str = ", ".join(swimmers) if swimmers else "No swimmers assigned"
                        print(f"  {lane:<6} {team_name:<15} {swimmer_str:<50} {time_str:<12}")

                    else:  # individual
                        # Get athlete
                        athlete_ref = record.get("relationships", {}).get("athlete", {}).get("data")

                        if athlete_ref:
                            athlete_id = athlete_ref.get("id")
                            athlete_info = athletes.get(athlete_id, {})
                            athlete_name = athlete_info.get("displayName", f"Athlete {athlete_id[:8]}")
                        else:
                            athlete_name = "No athlete assigned"

                        print(f"  {lane:<6} {team:<15} {athlete_name:<50} {time_str:<12}")

        except (json.JSONDecodeError, Exception) as e:
            print(f"\nError processing {event_file}: {e}")
            continue

    print(f"\n{'='*100}\n")


def main():
    """Main entry point"""
    print("\n=== Heat and Lane Assignment Report ===")

    # Check cache exists
    cache_dir = Path("api_cache")
    if not cache_dir.exists():
        print("\n❌ api_cache/ directory not found")
        return

    show_event_details()


if __name__ == "__main__":
    main()
