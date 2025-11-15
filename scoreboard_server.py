#!/usr/bin/env python3
"""
Live scoreboard web server for Swimtopia meets
Displays heat sheets and results with auto-refresh
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, render_template_string
from swimtopia_export import SwimtopiaExporter, load_config


app = Flask(__name__)

# Global configuration
MODE = "cache"
MEET_ID = None
API_CLIENT = None


def load_athletes_from_cache() -> Dict[str, Dict]:
    """Load athlete data from cache"""
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


def load_athletes_from_api(meet_id: str) -> Dict[str, Dict]:
    """Load athlete data from live API"""
    if not API_CLIENT:
        raise Exception("API client not initialized")

    athletes = {}
    url = f"{API_CLIENT.base_url}/v3/meets/{meet_id}/athletes"

    try:
        response = API_CLIENT.session.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        athlete_list = data.get("data", [])

        for athlete in athlete_list:
            athlete_id = athlete.get("id")
            attrs = athlete.get("attributes", {})
            athletes[athlete_id] = {
                "firstName": attrs.get("firstName"),
                "lastName": attrs.get("lastName"),
                "displayName": f"{attrs.get('displayFirstName', attrs.get('firstName', ''))} {attrs.get('lastName', '')}".strip(),
            }

    except Exception as e:
        print(f"Error fetching athletes from API: {e}")
        raise

    return athletes


def load_all_events_from_cache() -> List[Dict]:
    """Load all events from cache"""
    cache_dir = Path("api_cache")
    all_events = []

    # Load events list files
    events_list_files = list(cache_dir.glob("*events_2*.json"))
    event_nodes_files = list(cache_dir.glob("*event-nodes*.json"))

    for events_file in events_list_files:
        if "events_ID" in events_file.name:
            continue

        try:
            with open(events_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                events_data = data.get("data", [])
                all_events.extend(events_data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Error loading {events_file}: {e}")

    # Also load from event-nodes files
    for nodes_file in event_nodes_files:
        try:
            with open(nodes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                nodes_data = data.get("data", [])

                for node in nodes_data:
                    if node.get("type") == "eventNode":
                        event_ref = node.get("relationships", {}).get("event", {}).get("data", {})
                        if event_ref:
                            event_id = event_ref.get("id")
                            event = {
                                "id": event_id,
                                "type": "event",
                                "attributes": node.get("attributes", {})
                            }
                            all_events.append(event)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Error loading {nodes_file}: {e}")

    # Deduplicate by event ID
    events_by_id = {}
    for event in all_events:
        event_id = event.get("id")
        if event_id not in events_by_id:
            events_by_id[event_id] = event

    unique_events = list(events_by_id.values())
    unique_events.sort(key=lambda e: int(e.get("attributes", {}).get("eventNumber", "999")))

    return unique_events


def load_all_events_from_api(meet_id: str) -> List[Dict]:
    """Load all events from live API"""
    if not API_CLIENT:
        raise Exception("API client not initialized")

    url = f"{API_CLIENT.base_url}/v3/meets/{meet_id}/event-nodes"

    try:
        response = API_CLIENT.session.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        nodes_data = data.get("data", [])

        all_events = []
        for node in nodes_data:
            if node.get("type") == "eventNode":
                event_ref = node.get("relationships", {}).get("event", {}).get("data", {})
                if event_ref:
                    event_id = event_ref.get("id")
                    event = {
                        "id": event_id,
                        "type": "event",
                        "attributes": node.get("attributes", {})
                    }
                    all_events.append(event)

        all_events.sort(key=lambda e: int(e.get("attributes", {}).get("eventNumber", "999")))
        return all_events

    except Exception as e:
        print(f"Error fetching events from API: {e}")
        raise


def load_event_details_from_cache(event_id: str) -> Dict:
    """Load detailed event data from cache"""
    cache_dir = Path("api_cache")
    event_detail_files = list(cache_dir.glob(f"*events_ID_*.json"))

    for detail_file in event_detail_files:
        try:
            with open(detail_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                event_data = data.get("data", {})

                if event_data.get("id") == event_id:
                    event_data["included"] = data.get("included", [])
                    return event_data
        except (json.JSONDecodeError, Exception):
            continue

    return {}


def load_event_details_from_api(meet_id: str, event_id: str) -> Dict:
    """Load detailed event data from live API"""
    if not API_CLIENT:
        raise Exception("API client not initialized")

    url = f"{API_CLIENT.base_url}/v3/meets/{meet_id}/events/{event_id}"

    try:
        response = API_CLIENT.session.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        event_data = data.get("data", {})
        event_data["included"] = data.get("included", [])

        return event_data

    except Exception as e:
        # Event details might not be available, that's ok
        print(f"Note: Event {event_id} details not available: {e}")
        return {}


def load_meet_info_from_cache() -> Dict:
    """Load meet information from cache"""
    cache_dir = Path("api_cache")

    # Try to load from meet detail files
    meet_files = list(cache_dir.glob("*meets_ID_2*.json"))

    for meet_file in meet_files:
        if "events" in meet_file.name or "athletes" in meet_file.name:
            continue

        try:
            with open(meet_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if this is a meet detail response (single meet)
            meet_data = data.get("data", {})
            if isinstance(meet_data, dict) and meet_data.get("type") == "meet":
                return meet_data.get("attributes", {})

        except (json.JSONDecodeError, Exception):
            continue

    return {}


def load_meet_info_from_api(meet_id: str) -> Dict:
    """Load meet information from live API"""
    if not API_CLIENT:
        raise Exception("API client not initialized")

    url = f"{API_CLIENT.base_url}/v3/meets/{meet_id}"

    try:
        response = API_CLIENT.session.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()
        meet_data = data.get("data", {})
        return meet_data.get("attributes", {})

    except Exception as e:
        print(f"Error fetching meet info from API: {e}")
        return {}


def format_time(time_int):
    """Format time integer to MM:SS.ss"""
    if not time_int:
        return "NT"
    minutes = time_int // 6000
    seconds = (time_int % 6000) / 100
    if minutes > 0:
        return f"{minutes}:{seconds:05.2f}"
    return f"{seconds:.2f}"


def generate_scoreboard_data():
    """Generate scoreboard data from cache or live API"""
    if MODE == "cache":
        athletes = load_athletes_from_cache()
        all_events = load_all_events_from_cache()
        meet_info = load_meet_info_from_cache()

        def get_event_details(event_id):
            return load_event_details_from_cache(event_id)

    else:  # live mode
        if not MEET_ID:
            raise Exception("MEET_ID not set for live mode")

        athletes = load_athletes_from_api(MEET_ID)
        all_events = load_all_events_from_api(MEET_ID)
        meet_info = load_meet_info_from_api(MEET_ID)

        def get_event_details(event_id):
            return load_event_details_from_api(MEET_ID, event_id)

    return {
        "athletes": athletes,
        "events": all_events,
        "meet_info": meet_info,
        "get_event_details": get_event_details,
        "mode": MODE,
        "timestamp": datetime.now().strftime("%B %d, %Y at %I:%M %p")
    }


@app.route("/")
def scoreboard():
    """Render the scoreboard"""
    try:
        data = generate_scoreboard_data()
    except Exception as e:
        return f"<h1>Error Loading Scoreboard</h1><p>{str(e)}</p>", 500

    # Read the HTML template
    template_path = Path("scoreboard_template.html")
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        return "<h1>Error</h1><p>scoreboard_template.html not found</p>", 500

    return render_template_string(
        template,
        data=data,
        format_time=format_time,
        enumerate=enumerate,
        sorted=sorted,
        int=int
    )


def main():
    """Main entry point"""
    global MODE, MEET_ID, API_CLIENT

    parser = argparse.ArgumentParser(description="Live Scoreboard Server")
    parser.add_argument(
        "--mode",
        choices=["cache", "live"],
        default="cache",
        help="Data source mode: cache (offline) or live (fetch from API)"
    )
    parser.add_argument(
        "--meet-id",
        type=str,
        help="Meet ID for live mode"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.json",
        help="Config file for live mode (default: config.json)"
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=5000,
        help="Port to run server on (default: 5000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1, use 0.0.0.0 for network access)"
    )

    args = parser.parse_args()

    MODE = args.mode

    if MODE == "live":
        # Initialize API client
        print(f"\n=== Starting Scoreboard Server (LIVE MODE) ===\n")

        config = load_config(args.config)
        API_CLIENT = SwimtopiaExporter()

        # Authenticate
        print("Authenticating...")
        auth_config = config.get("auth", {})
        if not API_CLIENT.authenticate(
            auth_config.get("username"), auth_config.get("password")
        ):
            print("❌ Authentication failed")
            sys.exit(1)
        print("✓ Authenticated\n")

        # Get meet ID from args or config
        MEET_ID = args.meet_id or config.get("export", {}).get("meet_id")
        if not MEET_ID:
            print("❌ Meet ID required for live mode (use --meet-id or set in config)")
            sys.exit(1)

        print(f"Meet ID: {MEET_ID}")

        # Test API connection
        try:
            print("Testing API connection...")
            _ = load_all_events_from_api(MEET_ID)
            print("✓ API connection successful\n")
        except Exception as e:
            print(f"❌ Failed to connect to API: {e}")
            sys.exit(1)

    else:
        print(f"\n=== Starting Scoreboard Server (CACHE MODE) ===\n")

        # Check cache exists
        cache_dir = Path("api_cache")
        if not cache_dir.exists():
            print("❌ api_cache/ directory not found")
            sys.exit(1)

        cache_files = list(cache_dir.glob("*.json"))
        print(f"Found {len(cache_files)} cached files\n")

    print(f"Server starting on http://{args.host}:{args.port}")
    print(f"Mode: {MODE.upper()}")
    print(f"\nPress Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
