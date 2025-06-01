import os
import base64
from dotenv import load_dotenv

load_dotenv()

ZOOM_ACCOUNT_ID = None
ZOOM_CLIENT_ID = None
ZOOM_CLIENT_SECRET = None

def initialize_config(zoom_account_id=None, zoom_client_id=None, zoom_client_secret=None):
    """Initialize configuration with command-line arguments or environment variables."""
    global ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET
    
    # Use command-line arguments if provided, otherwise fall back to environment variables
    ZOOM_ACCOUNT_ID = zoom_account_id or os.getenv('ZOOM_ACCOUNT_ID')
    ZOOM_CLIENT_ID = zoom_client_id or os.getenv('ZOOM_CLIENT_ID')
    ZOOM_CLIENT_SECRET = zoom_client_secret or os.getenv('ZOOM_CLIENT_SECRET')
    
    if not ZOOM_ACCOUNT_ID:
        raise ValueError("ZOOM_ACCOUNT_ID must be provided via --zoom-account-id argument or ZOOM_ACCOUNT_ID environment variable")
    if not ZOOM_CLIENT_ID:
        raise ValueError("ZOOM_CLIENT_ID must be provided via --zoom-client-id argument or ZOOM_CLIENT_ID environment variable")
    if not ZOOM_CLIENT_SECRET:
        raise ValueError("ZOOM_CLIENT_SECRET must be provided via --zoom-client-secret argument or ZOOM_CLIENT_SECRET environment variable")

def get_auth_header():
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"