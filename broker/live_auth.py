import os

def load_live_credentials(api_key_env="BROKER_API_KEY", api_secret_env="BROKER_API_SECRET"):
    return {
        "api_key_present": bool(os.getenv(api_key_env)),
        "api_secret_present": bool(os.getenv(api_secret_env)),
        "api_key_env": api_key_env,
        "api_secret_env": api_secret_env,
    }

def auth_ready(creds: dict):
    return bool(creds.get("api_key_present")) and bool(creds.get("api_secret_present"))
