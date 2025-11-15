#!/usr/bin/env python3
"""
Simple Swimtopia Export Script - Just add your login credentials!
No OAuth client_id or client_secret needed.
"""

import json
import time
import uuid
import requests
import sys
from pathlib import Path


def authenticate(username, password):
    """Login to Swimtopia and get access token"""
    print(f"Authenticating as {username}...")
    
    response = requests.post(
        "https://api.swimtopia.org/oauth/token",
        data={
            'grant_type': 'password',
            'username': username,
            'password': password
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    if response.status_code == 200:
        token_data = response.json()
        print("✓ Login successful!")
        return token_data.get('access_token')
    else:
        print(f"✗ Login failed: {response.status_code}")
        try:
            error = response.json()
            print(f"  Error: {error.get('error_description', error.get('error', 'Unknown error'))}")
        except:
            print(f"  Response: {response.text[:200]}")
        return None


def create_export(token, meet_id, export_type="result"):
    """Create an export task"""
    task_id = str(uuid.uuid4())
    
    print(f"\nCreating {export_type} export for meet {meet_id}...")
    print(f"Task ID: {task_id}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/vnd.api+json',
        'Accept': 'application/vnd.api+json'
    }
    
    payload = {
        "data": {
            "type": "exportTask",
            "id": task_id,
            "attributes": {
                "exportType": export_type,
                "exportFormat": "hy3",
                "exportOptions": {
                    "team": {"value": -1, "label": "All Teams"},
                    "session": {"value": -1, "label": "All Sessions"}
                }
            },
            "relationships": {
                "meet": {
                    "data": {"type": "meet", "id": str(meet_id)}
                }
            }
        }
    }
    
    response = requests.post(
        f"https://api.swimtopia.org/v3/meets/{meet_id}/export-tasks",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 201:
        print("✓ Export task created")
        return task_id
    else:
        print(f"✗ Failed to create export: {response.status_code}")
        return None


def wait_for_export(token, meet_id, task_id, max_wait=60):
    """Poll until export is ready"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.api+json'
    }
    
    print("\nWaiting for export to complete...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(
            f"https://api.swimtopia.org/v3/meets/{meet_id}/export-tasks/{task_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data['data']['attributes']['currentState']
            
            if status == 'completed':
                download_url = data['data']['attributes']['exportHref']
                filename = data['data']['attributes']['exportFilename']
                print(f"✓ Export ready: {filename}")
                return download_url, filename
            elif status == 'failed':
                print("✗ Export failed")
                return None, None
        
        time.sleep(2)
        print(".", end="", flush=True)
    
    print("\n✗ Export timed out")
    return None, None


def download_file(url, filename):
    """Download the export file"""
    print(f"\nDownloading {filename}...")
    
    response = requests.get(url, stream=True)
    
    if response.status_code == 200:
        # Create exports directory if it doesn't exist
        Path("exports").mkdir(exist_ok=True)
        
        filepath = Path("exports") / filename
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        size_mb = filepath.stat().st_size / 1024 / 1024
        print(f"✓ Downloaded: {filepath} ({size_mb:.2f} MB)")
        return str(filepath)
    else:
        print(f"✗ Download failed: {response.status_code}")
        return None


def main():
    print("=== Swimtopia Export Tool ===\n")
    
    # EDIT THESE WITH YOUR CREDENTIALS
    USERNAME = "your_email@example.com"  # Your Swimtopia login email
    PASSWORD = "your_password"           # Your Swimtopia password
    MEET_ID = "12345"                    # The meet ID you want to export
    
    # Check if credentials were edited
    if USERNAME == "your_email@example.com":
        print("Please edit this script and add your Swimtopia credentials.")
        print("Look for the USERNAME and PASSWORD variables in the main() function.")
        sys.exit(1)
    
    # Login
    token = authenticate(USERNAME, PASSWORD)
    if not token:
        sys.exit(1)
    
    # Create export
    task_id = create_export(token, MEET_ID, export_type="result")
    if not task_id:
        sys.exit(1)
    
    # Wait for completion
    download_url, filename = wait_for_export(token, MEET_ID, task_id)
    if not download_url:
        sys.exit(1)
    
    # Download file
    filepath = download_file(download_url, filename)
    if filepath:
        print(f"\n✅ Success! Export saved to: {filepath}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
