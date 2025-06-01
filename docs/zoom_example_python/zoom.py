#!/opt/datadog-agent/embedded/bin/python3
import requests
import json
from time import time
import yaml
import os

class ZoomAuth:
    def __init__(self, account_id, auth_header):
        self.token = None
        self.token_expiry = 0
        self.account_id = account_id
        self.auth_header = auth_header
        self.token_cache_file = f'/tmp/zoom_token_{account_id}.json'
        self._load_cached_token()

    def _load_cached_token(self):
        try:
            with open(self.token_cache_file, 'r') as f:
                cache = json.load(f)
                self.token = cache['token']
                self.token_expiry = cache['expiry']
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def _save_token_cache(self):
        with open(self.token_cache_file, 'w') as f:
            json.dump({
                'token': self.token,
                'expiry': self.token_expiry
            }, f)
        os.chmod(self.token_cache_file, 0o600)

    def get_valid_token(self):
        if self.token and time() < self.token_expiry:
            return self.token

        url = "https://zoom.us/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.auth_header
        }
        data = f"grant_type=account_credentials&account_id={self.account_id}"

        response = requests.post(url, headers=headers, data=data)
        token_data = response.json()

        self.token = token_data["access_token"]
        self.token_expiry = time() + token_data["expires_in"] - 300  # Buffer of 5 minutes

        self._save_token_cache()  # Save new token to cache

        # Log token request to file
        with open('/var/log/datadog/zoom_token_requests.log', 'a') as f:
            f.write(f"{time()}: New token requested for account {self.account_id}\n")

        return self.token

def zoom_api_get(zoom_auth, url_suffix, params=None):
    API_PREFIX = 'https://api.zoom.us/v2/'
    url = f'{API_PREFIX}{url_suffix}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {zoom_auth.get_valid_token()}'
    }
    print(f"Making request to {url} with params {params}")
    response = requests.get(url, headers=headers, params=params or {})
    if not response.ok:
        raise Exception(f"Zoom API request failed: {response.status_code} - {response.text}")
    return response.json()

def get_rooms_by_location(zoom_auth, location_id):
    """Get rooms for a specific location"""
    params = {'page_size': '100', 'location_id': location_id}
    return zoom_api_get(zoom_auth, 'rooms', params)

def _collect_api_data(zoom_auth, instance):
    """Collect room data from Zoom API for configured sites"""
    all_rooms = []
    sites = instance.get('sites', {})

    for site_id, site_name in sites.items():
        rooms = get_rooms_by_location(zoom_auth, site_id)
        for room in rooms.get('rooms', []):
            room['site'] = site_name  # Add site name for tagging
            all_rooms.append(room)

    return all_rooms



