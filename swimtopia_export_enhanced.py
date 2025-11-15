#!/usr/bin/env python3
"""
Enhanced Swimtopia API Export Script with config file support
"""

import json
import time
import uuid
import requests
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin
from pathlib import Path
import argparse


class SwimtopiaExporter:
    """Handles Swimtopia API authentication and export operations"""
    
    def __init__(self, base_url: str = "https://api.swimtopia.org", verify_ssl: bool = True):
        self.base_url = base_url
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.access_token = None
        self.token_expires_at = None
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json',
            'User-Agent': 'SwimtopiaExporter/1.0'
        })
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate using simplified OAuth 2.0 Password Grant flow
        (No client_id or client_secret required for Swimtopia)
        """
        token_url = urljoin(self.base_url, "/oauth/token")
        
        # OAuth token request - Swimtopia doesn't require client credentials
        token_data = {
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        
        try:
            # Use form encoding for OAuth endpoint
            response = requests.post(
                token_url,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                verify=self.verify_ssl,
                timeout=30
            )
            
            if response.status_code == 200:
                token_response = response.json()
                self.access_token = token_response.get('access_token')
                
                # Calculate token expiration if provided
                expires_in = token_response.get('expires_in')
                if expires_in:
                    self.token_expires_at = time.time() + expires_in
                
                # Update session with auth header
                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_token}'
                })
                
                print(f"✓ Authentication successful")
                print(f"  Token type: {token_response.get('token_type', 'Bearer')}")
                if expires_in:
                    print(f"  Expires in: {expires_in} seconds")
                
                return True
            else:
                print(f"✗ Authentication failed: {response.status_code}")
                
                # Try to parse error response
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        print(f"  Error: {error_data.get('error')}")
                        if 'error_description' in error_data:
                            print(f"  Description: {error_data.get('error_description')}")
                except:
                    print(f"  Response: {response.text[:200]}")
                
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Authentication request failed: {e}")
            return False
    
    def is_token_valid(self) -> bool:
        """Check if the current token is still valid"""
        if not self.access_token:
            return False
        if self.token_expires_at and time.time() >= self.token_expires_at:
            return False
        return True
    
    def create_export_task(self, meet_id: str, export_type: str = "result",
                          export_format: str = "hy3", 
                          team_filter: int = -1, session_filter: int = -1,
                          task_id: Optional[str] = None) -> Optional[str]:
        """
        Create an export task with client-generated UUID
        """
        # Generate client-side UUID if not provided
        if not task_id:
            task_id = str(uuid.uuid4())
        
        export_url = f"{self.base_url}/v3/meets/{meet_id}/export-tasks"
        
        # Build request payload
        payload = {
            "data": {
                "type": "exportTask",
                "id": task_id,
                "attributes": {
                    "exportType": export_type,
                    "exportFormat": export_format,
                    "exportOptions": {
                        "team": {
                            "value": team_filter,
                            "label": "All Teams" if team_filter == -1 else f"Team {team_filter}"
                        },
                        "session": {
                            "value": session_filter,
                            "label": "All Sessions" if session_filter == -1 else f"Session {session_filter}"
                        }
                    }
                },
                "relationships": {
                    "meet": {
                        "data": {
                            "type": "meet",
                            "id": str(meet_id)
                        }
                    }
                }
            }
        }
        
        print(f"\n📤 Creating export task...")
        print(f"   Meet ID: {meet_id}")
        print(f"   Task ID: {task_id}")
        print(f"   Export Type: {export_type}")
        print(f"   Format: {export_format}")
        print(f"   Team Filter: {'All Teams' if team_filter == -1 else f'Team {team_filter}'}")
        print(f"   Session Filter: {'All Sessions' if session_filter == -1 else f'Session {session_filter}'}")
        
        try:
            response = self.session.post(export_url, json=payload, timeout=30)
            
            if response.status_code == 201:
                print(f"✓ Export task created successfully")
                
                # Parse response for confirmation
                response_data = response.json()
                created_state = response_data.get('data', {}).get('attributes', {}).get('currentState')
                print(f"  Initial state: {created_state}")
                
                return task_id
            else:
                print(f"✗ Failed to create export task: {response.status_code}")
                
                # Try to parse error response
                try:
                    error_data = response.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            print(f"  Error: {error.get('title', error.get('detail', str(error)))}")
                except:
                    print(f"  Response: {response.text[:500]}")
                
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Export task creation failed: {e}")
            return None
    
    def poll_export_status(self, meet_id: str, task_id: str, 
                          max_attempts: int = 30, 
                          poll_interval: float = 2.0,
                          show_progress: bool = True) -> Optional[Dict[str, Any]]:
        """
        Poll export task status until completion
        """
        status_url = f"{self.base_url}/v3/meets/{meet_id}/export-tasks/{task_id}"
        
        if show_progress:
            print(f"\n⏳ Polling export status...")
        
        start_time = time.time()
        
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.session.get(status_url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    task_data = data.get('data', {})
                    attributes = task_data.get('attributes', {})
                    current_state = attributes.get('currentState')
                    
                    elapsed = time.time() - start_time
                    
                    if show_progress:
                        print(f"   [{elapsed:.1f}s] Attempt {attempt}: State = {current_state}")
                    
                    if current_state == 'completed':
                        export_href = attributes.get('exportHref')
                        export_filename = attributes.get('exportFilename')
                        
                        print(f"\n✓ Export completed!")
                        print(f"   Total time: {elapsed:.1f} seconds")
                        print(f"   Filename: {export_filename}")
                        if show_progress:
                            print(f"   Download URL: {export_href[:100]}...")
                        
                        return task_data
                    
                    elif current_state == 'failed':
                        print(f"\n✗ Export failed")
                        error_message = attributes.get('errorMessage')
                        if error_message:
                            print(f"   Error: {error_message}")
                        return None
                    
                elif response.status_code == 304:
                    # Not modified, task still in progress
                    if show_progress:
                        elapsed = time.time() - start_time
                        print(f"   [{elapsed:.1f}s] Attempt {attempt}: No change (304)")
                else:
                    print(f"✗ Failed to get status: {response.status_code}")
                    return None
                
            except requests.exceptions.RequestException as e:
                print(f"✗ Status poll failed: {e}")
                return None
            
            if attempt < max_attempts:
                time.sleep(poll_interval)
        
        print(f"\n✗ Timeout: Export did not complete within {max_attempts * poll_interval} seconds")
        return None
    
    def download_export(self, export_url: str, output_dir: str = ".", 
                       output_filename: Optional[str] = None) -> Optional[str]:
        """
        Download the exported file
        
        Returns:
            Path to downloaded file if successful, None otherwise
        """
        print(f"\n📥 Downloading export...")
        
        try:
            # Create output directory if it doesn't exist
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # Download with streaming to handle large files
            response = requests.get(export_url, stream=True, timeout=60)
            
            if response.status_code == 200:
                # Get filename from headers or URL if not provided
                if not output_filename:
                    content_disposition = response.headers.get('content-disposition', '')
                    if 'filename=' in content_disposition:
                        output_filename = content_disposition.split('filename=')[1].strip('"')
                    else:
                        # Extract from URL
                        output_filename = export_url.split('/')[-1].split('?')[0]
                        output_filename = requests.utils.unquote(output_filename)
                
                output_path = Path(output_dir) / output_filename
                
                # Get total size if available
                total_size = int(response.headers.get('content-length', 0))
                
                # Write file with progress
                downloaded = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r   Progress: {progress:.1f}% ({downloaded}/{total_size} bytes)", end='')
                
                print()  # New line after progress
                
                file_size_mb = output_path.stat().st_size / 1024 / 1024
                print(f"✓ Downloaded: {output_path} ({file_size_mb:.2f} MB)")
                return str(output_path)
            else:
                print(f"✗ Download failed: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Download failed: {e}")
            return None


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"✗ Config file not found: {config_file}")
        print("  Create a config.json file based on config.example.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in config file: {e}")
        sys.exit(1)


def main():
    """Main entry point with argument parsing"""
    
    parser = argparse.ArgumentParser(description='Export data from Swimtopia')
    parser.add_argument('-c', '--config', default='config.json', 
                       help='Configuration file (default: config.json)')
    parser.add_argument('-m', '--meet-id', help='Override meet ID from config')
    parser.add_argument('-t', '--type', choices=['result', 'merge-results', 'merge-entries'],
                       help='Override export type from config')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('--list-only', action='store_true', 
                       help='Only list existing export tasks')
    parser.add_argument('--no-download', action='store_true',
                       help='Create export but skip download')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    if args.meet_id:
        config['export']['meet_id'] = args.meet_id
    if args.type:
        config['export']['export_type'] = args.type
    if args.output:
        config['export']['output_directory'] = args.output
    
    # Initialize exporter
    exporter = SwimtopiaExporter(
        base_url=config.get('api', {}).get('base_url', 'https://api.swimtopia.org'),
        verify_ssl=config.get('api', {}).get('verify_ssl', True)
    )
    
    print("=== Swimtopia Export Script ===\n")
    
    # Authenticate
    print("Authenticating...")
    auth_config = config.get('auth', {})
    
    if not exporter.authenticate(
        auth_config.get('username'),
        auth_config.get('password')
    ):
        print("\n✗ Authentication failed. Check your credentials in the config file.")
        sys.exit(1)
    
    export_config = config.get('export', {})
    meet_id = str(export_config.get('meet_id'))
    
    # List existing tasks
    if args.list_only:
        print(f"\nListing export tasks for meet {meet_id}...")
        tasks = exporter.list_export_tasks(meet_id)
        sys.exit(0)
    
    # Create new export
    task_id = exporter.create_export_task(
        meet_id=meet_id,
        export_type=export_config.get('export_type', 'result'),
        export_format=export_config.get('export_format', 'hy3'),
        team_filter=export_config.get('team_filter', -1),
        session_filter=export_config.get('session_filter', -1)
    )
    
    if not task_id:
        print("\n✗ Failed to create export task.")
        sys.exit(1)
    
    # Poll for completion
    api_config = config.get('api', {})
    task_data = exporter.poll_export_status(
        meet_id,
        task_id,
        max_attempts=api_config.get('max_poll_attempts', 30),
        poll_interval=api_config.get('poll_interval_seconds', 2.0)
    )
    
    if not task_data:
        print("\n✗ Export did not complete successfully.")
        sys.exit(1)
    
    # Download the export
    if not args.no_download:
        export_url = task_data.get('attributes', {}).get('exportHref')
        
        if export_url:
            output_dir = export_config.get('output_directory', './exports')
            downloaded_file = exporter.download_export(export_url, output_dir)
            
            if downloaded_file:
                print(f"\n✅ Export complete!")
                print(f"   File saved to: {downloaded_file}")
            else:
                print("\n✗ Download failed.")
                sys.exit(1)
        else:
            print("\n✗ No download URL available.")
            sys.exit(1)
    else:
        print("\n✅ Export created successfully (download skipped)")


if __name__ == "__main__":
    main()
