import os

def provider_credentials_status():
    return {
        "fmp_api_key_present": bool(os.getenv("FMP_API_KEY")),
        "newsapi_key_present": bool(os.getenv("NEWSAPI_KEY")),
        "broker_api_key_present": bool(os.getenv("BROKER_API_KEY")),
    }
