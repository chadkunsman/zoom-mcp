import json
import os
import aiohttp
from time import time
from typing import Optional

class ZoomAuth:
    def __init__(self, account_id: str, auth_header: str):
        self.token: Optional[str] = None
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

    async def get_valid_token(self) -> str:
        if self.token and time() < self.token_expiry:
            return self.token

        url = "https://zoom.us/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.auth_header
        }
        data = f"grant_type=account_credentials&account_id={self.account_id}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if not response.ok:
                    raise Exception(f"Failed to get Zoom token: {response.status} - {await response.text()}")
                token_data = await response.json()

        self.token = token_data["access_token"]
        self.token_expiry = time() + token_data["expires_in"] - 300  # Buffer of 5 minutes

        self._save_token_cache()
        return self.token

async def zoom_api_get(zoom_auth: ZoomAuth, url_suffix: str, params: dict = None) -> dict:
    API_PREFIX = 'https://api.zoom.us/v2/'
    url = f'{API_PREFIX}{url_suffix}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {await zoom_auth.get_valid_token()}'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params or {}) as response:
            if not response.ok:
                raise Exception(f"Zoom API request failed: {response.status} - {await response.text()}")
            return await response.json()