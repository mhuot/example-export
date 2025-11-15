# Scoreboard Server Usage

Live web-based scoreboard for swim meets with auto-refresh capability.

## Features

- **Cache Mode**: Uses locally cached API data (for development, reduces API hits)
- **Live Mode**: Fetches real-time data from Swimtopia API (auto-refreshes every 15 seconds)
- **Auto-Refresh**: Live mode automatically reloads to show updated results
- **Meet Information**: Displays meet name, dates, location, and course type at the top
- **Full Heat Sheets**: Shows lanes, swimmers, seed times, and results
- **Professional Display**: Ready for projection on TVs/monitors at meets

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Usage

### Cache Mode (Development)

Use cached data from `api_cache/` directory. No API calls, faster for testing.

```bash
python scoreboard_server.py --mode cache
```

Then open http://127.0.0.1:5000 in your browser.

### Live Mode (At the Meet)

Fetches live data from Swimtopia API. Auto-refreshes every 15 seconds.

```bash
python scoreboard_server.py --mode live --meet-id 12345
```

Or use the meet ID from your config file:

```bash
python scoreboard_server.py --mode live
```

**The scoreboard will auto-refresh every 15 seconds to show new results as they're posted!**

### Network Access

To display on another device (TV, tablet, etc.) on your network:

```bash
python scoreboard_server.py --mode live --host 0.0.0.0 --port 8080
```

Then access from any device on your network at: `http://YOUR_IP:8080`

## Command Line Options

```
--mode {cache,live}     Data source: cache (offline) or live (API)
--meet-id ID            Meet ID for live mode
--config FILE           Config file (default: config.json)
--port PORT             Port number (default: 5000)
--host HOST             Host to bind (default: 127.0.0.1, use 0.0.0.0 for network)
```

## Examples

### Development with Cache
```bash
# Use cached data, no API calls
python scoreboard_server.py --mode cache
```

### Live at the Meet
```bash
# Live data, auto-refresh, specific meet
python scoreboard_server.py --mode live --meet-id 107684
```

### Display on TV via Network
```bash
# Allow network access, custom port
python scoreboard_server.py --mode live --host 0.0.0.0 --port 8080
```

## What's Displayed

### Meet Header
- Meet name (e.g., "Championship Finals")
- Meet dates (single day or date range)
- Location (if specified)
- Course type (25 Yards SCY, 25 Meters SCM, or 50 Meters LCM)
- Live/Cache mode indicator
- Last updated timestamp

### Event Status Indicators
- **SCORED** (green) - Event completed with results
- **SEEDED** (yellow) - Event seeded with lane assignments
- **PARTIAL** (yellow) - Event partially seeded
- **UNSEEDED** (gray) - Event not yet seeded

### Event Details
- Lane assignments
- Swimmer names (individual and relay teams)
- Seed times
- Result times (when available)
- Places with medal highlighting (gold/silver/bronze)

## Tips

- **Cache Mode**: Great for development, testing layout, reducing API usage
- **Live Mode**: Use at meets for real-time results display
- **Auto-Refresh**: In live mode, results update automatically every 15 seconds
- **Full Screen**: Press F11 in browser for full-screen display on TVs
- **Multiple Displays**: Run the server once, access from multiple devices

## Troubleshooting

**Server won't start in live mode:**
- Check credentials in config.json
- Verify meet ID is correct
- Ensure internet connection available

**No events showing:**
- Cache mode: Run `python dev_cache_api.py --har` to extract HAR files
- Live mode: Verify meet ID exists and has events

**Can't access from other devices:**
- Use `--host 0.0.0.0` to allow network access
- Check firewall settings
- Find your IP with `ifconfig` (Mac/Linux) or `ipconfig` (Windows)
