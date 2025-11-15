#!/usr/bin/env python3
"""
Swimtopia API Export Script
Handles OAuth authentication and export task creation/polling
"""

import json
import time
import uuid
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class SwimtopiaExporter:
    """Handles Swimtopia API authentication and export operations"""
    
    def __init__(self, base_url: str = "https://api.swimtopia.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token = None
        
        # Set default headers
        self.session.headers.update({
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'
        })
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate using simplified OAuth 2.0 Password Grant flow
        (No client_id or client_secret required)
        
        Args:
            username: User's Swimtopia username (email)
            password: User's Swimtopia password
            
        Returns:
            True if authentication successful
        """
        token_url = urljoin(self.base_url, "/oauth/token")
        
        # OAuth token request - simplified without client credentials
        token_data = {
            'grant_type': 'password',
            'username': username,
            'password': password
        }
        
        # Use form encoding for OAuth endpoint
        response = requests.post(
            token_url,
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            token_response = response.json()
            self.access_token = token_response.get('access_token')
            
            # Update session with auth header
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            print(f"✓ Authentication successful")
            return True
        else:
            print(f"✗ Authentication failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    
    def create_export_task(self, meet_id: str, export_type: str = "result",
                          export_format: str = "hy3", 
                          team_filter: int = -1, session_filter: int = -1) -> Optional[str]:
        """
        Create an export task with client-generated UUID
        
        Args:
            meet_id: ID of the meet to export
            export_type: Type of export ("result", "merge-results", "merge-entries")
            export_format: Format for export (typically "hy3")
            team_filter: Team ID to filter (-1 for all teams)
            session_filter: Session ID to filter (-1 for all sessions)
            
        Returns:
            Task ID if successful, None otherwise
        """
        # Generate client-side UUID
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
                            "id": meet_id
                        }
                    }
                }
            }
        }
        
        print(f"\n📤 Creating export task...")
        print(f"   Task ID: {task_id}")
        print(f"   Export Type: {export_type}")
        print(f"   Format: {export_format}")
        
        response = self.session.post(export_url, json=payload)
        
        if response.status_code == 201:
            print(f"✓ Export task created successfully")
            return task_id
        else:
            print(f"✗ Failed to create export task: {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    
    def poll_export_status(self, meet_id: str, task_id: str, 
                          max_attempts: int = 30, 
                          poll_interval: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Poll export task status until completion
        
        Args:
            meet_id: ID of the meet
            task_id: ID of the export task
            max_attempts: Maximum polling attempts
            poll_interval: Seconds between polls
            
        Returns:
            Task data when completed, None if failed
        """
        status_url = f"{self.base_url}/v3/meets/{meet_id}/export-tasks/{task_id}"
        
        print(f"\n⏳ Polling export status...")
        
        for attempt in range(1, max_attempts + 1):
            response = self.session.get(status_url)
            
            if response.status_code == 200:
                data = response.json()
                task_data = data.get('data', {})
                attributes = task_data.get('attributes', {})
                current_state = attributes.get('currentState')
                
                print(f"   Attempt {attempt}: State = {current_state}")
                
                if current_state == 'completed':
                    export_href = attributes.get('exportHref')
                    export_filename = attributes.get('exportFilename')
                    
                    print(f"\n✓ Export completed!")
                    print(f"   Filename: {export_filename}")
                    print(f"   Download URL: {export_href}")
                    
                    return task_data
                
                elif current_state == 'failed':
                    print(f"\n✗ Export failed")
                    return None
                
            elif response.status_code == 304:
                # Not modified, task still in progress
                print(f"   Attempt {attempt}: No change (304)")
            else:
                print(f"✗ Failed to get status: {response.status_code}")
                return None
            
            if attempt < max_attempts:
                time.sleep(poll_interval)
        
        print(f"\n✗ Timeout: Export did not complete within {max_attempts * poll_interval} seconds")
        return None
    
    def download_export(self, export_url: str, output_filename: Optional[str] = None) -> bool:
        """
        Download the exported file
        
        Args:
            export_url: URL from exportHref
            output_filename: Local filename to save (uses server filename if None)
            
        Returns:
            True if download successful
        """
        print(f"\n📥 Downloading export...")
        
        # Download with streaming to handle large files
        response = requests.get(export_url, stream=True)
        
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
            
            # Write file
            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = len(response.content) / 1024 / 1024  # MB
            print(f"✓ Downloaded: {output_filename} ({file_size:.2f} MB)")
            return True
        else:
            print(f"✗ Download failed: {response.status_code}")
            return False
    
    def list_export_tasks(self, meet_id: str) -> Optional[list]:
        """
        List all export tasks for a meet
        
        Args:
            meet_id: ID of the meet
            
        Returns:
            List of export tasks or None if failed
        """
        list_url = f"{self.base_url}/v3/meets/{meet_id}/export-tasks"
        
        response = self.session.get(list_url)
        
        if response.status_code == 200:
            data = response.json()
            tasks = data.get('data', [])
            
            print(f"\n📋 Found {len(tasks)} export tasks for meet {meet_id}:")
            for task in tasks:
                attrs = task.get('attributes', {})
                print(f"   - {attrs.get('exportType')} ({attrs.get('currentState')})")
                print(f"     Created: {attrs.get('createdAt')}")
                print(f"     File: {attrs.get('exportFilename', 'N/A')}")
            
            return tasks
        else:
            print(f"✗ Failed to list tasks: {response.status_code}")
            return None


def main():
    """Example usage of the SwimtopiaExporter"""
    
    # Configuration - just username and password needed!
    config = {
        'username': 'your_email@example.com',  # Your Swimtopia login email
        'password': 'your_password',           # Your Swimtopia password
        'meet_id': '12345'                     # The meet ID to export
    }
    
    # Initialize exporter
    exporter = SwimtopiaExporter()
    
    # Step 1: Authenticate
    print("=== Swimtopia Export Script ===\n")
    print("Step 1: Authenticating...")
    
    if not exporter.authenticate(
        config['username'],
        config['password']
    ):
        print("Authentication failed. Exiting.")
        return
    
    # Step 2: List existing export tasks (optional)
    print("\nStep 2: Checking existing exports...")
    exporter.list_export_tasks(config['meet_id'])
    
    # Step 3: Create new export task
    print("\nStep 3: Creating new export...")
    task_id = exporter.create_export_task(
        meet_id=config['meet_id'],
        export_type="result",  # or "merge-results", "merge-entries"
        export_format="hy3",
        team_filter=-1,  # All teams
        session_filter=-1  # All sessions
    )
    
    if not task_id:
        print("Failed to create export task. Exiting.")
        return
    
    # Step 4: Poll for completion
    print("\nStep 4: Waiting for export to complete...")
    task_data = exporter.poll_export_status(
        config['meet_id'],
        task_id,
        max_attempts=30,
        poll_interval=2.0
    )
    
    if not task_data:
        print("Export did not complete successfully.")
        return
    
    # Step 5: Download the export
    print("\nStep 5: Downloading export file...")
    export_url = task_data.get('attributes', {}).get('exportHref')
    
    if export_url:
        exporter.download_export(export_url)
        print("\n✅ Export complete!")
    else:
        print("No download URL available.")


if __name__ == "__main__":
    main()
