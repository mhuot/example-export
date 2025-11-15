# Swimtopia Export Script

Python script to export meet data from Swimtopia's API using your regular Swimtopia login credentials.

## Features

- Simple authentication using your Swimtopia username/password (no API keys needed!)
- Client-side UUID generation for export tasks
- Asynchronous task polling with progress updates
- Support for different export types (results, merge-results, merge-entries)
- HY3 format exports (HyTek compatible)
- Team and session filtering options
- Configuration file support
- Command-line argument overrides

## Installation

1. Install Python 3.6 or higher
2. Install dependencies:
```bash
pip install requests
```

## Quick Start - Simple Script

The easiest way to get started is with `swimtopia_simple.py`:

1. Edit the script and add your credentials:
```python
USERNAME = "your_email@example.com"  # Your Swimtopia login email
PASSWORD = "your_password"           # Your Swimtopia password
MEET_ID = "12345"                    # The meet ID you want to export
```

2. Run the script:
```bash
python swimtopia_simple.py
```

That's it! The script will login, create an export, and download it to the `exports/` directory.

## Advanced Usage - Configurable Script

For more control, use `swimtopia_export_enhanced.py`:

1. Copy the example configuration file:
```bash
cp config.example.json config.json
```

2. Edit `config.json` with your credentials:
```json
{
    "auth": {
        "username": "your_email@example.com",
        "password": "your_password"
    },
    "export": {
        "meet_id": "12345",
        "export_type": "result",
        "export_format": "hy3",
        "team_filter": -1,
        "session_filter": -1,
        "output_directory": "./exports"
    }
}
```

3. Run the script:
```bash
python swimtopia_export_enhanced.py
```

### Command Line Options

```bash
# Use a different config file
python swimtopia_export_enhanced.py -c myconfig.json

# Override meet ID
python swimtopia_export_enhanced.py -m 67890

# Change export type
python swimtopia_export_enhanced.py -t merge-results

# Specify output directory
python swimtopia_export_enhanced.py -o ./my_exports

# List existing export tasks without creating new one
python swimtopia_export_enhanced.py --list-only

# Create export but skip download
python swimtopia_export_enhanced.py --no-download
```

## How It Works

The script uses Swimtopia's simplified OAuth flow that only requires your regular login credentials:

1. **Authentication**: Sends username/password to `/oauth/token` to get an access token
2. **Create Export Task**: POST to `/v3/meets/{meet_id}/export-tasks` with client-generated UUID
3. **Poll Status**: GET `/v3/meets/{meet_id}/export-tasks/{task_id}` until state is "completed"
4. **Download**: Use the `exportHref` URL to download the zip file

No API keys, client IDs, or special developer access needed!

## Export Types

- **result**: Standard meet results
- **merge-results**: Combined results from multiple sources
- **merge-entries**: Combined entry data

## Filter Options

- **team_filter**: 
  - `-1` for all teams
  - Specific team ID to filter by team
  
- **session_filter**:
  - `-1` for all sessions
  - Specific session ID to filter by session

## API Workflow

1. **Authentication**: OAuth token request to `/oauth/token`
2. **Create Export Task**: POST to `/v3/meets/{meet_id}/export-tasks` with client-generated UUID
3. **Poll Status**: GET `/v3/meets/{meet_id}/export-tasks/{task_id}` until state is "completed"
4. **Download**: Use the `exportHref` URL to download the zip file

## Output

Exports are saved as zip files containing HY3 format data compatible with HyTek Meet Manager.

Example output filename: `Results 2025-12-15 EXAMPLE 002.zip`

## Error Handling

The script includes error handling for:
- Authentication failures
- Network timeouts
- Export task failures
- Download errors

## Notes

- Export processing is typically very fast (under 1 second)
- The script uses a 2-second polling interval by default
- Maximum polling attempts is set to 30 (1 minute timeout)
- Downloaded files are saved to the configured output directory
- The OAuth token is automatically included in all API requests after authentication

## Security Considerations

- Store credentials securely - never commit config.json to version control
- Add `config.json` to your `.gitignore` file
- Consider using environment variables for sensitive credentials
- The export URLs use signed tokens that expire after a period of time
