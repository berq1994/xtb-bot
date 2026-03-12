from real_sources.config import load_real_sources_config
from real_sources.gdelt_connector import poll_gdelt_real
from real_sources.sec_connector import poll_sec_real
from real_sources.earnings_connector import poll_earnings_real
from real_sources.macro_connector import poll_macro_real

def build_real_source_snapshot():
    cfg = load_real_sources_config()
    payload = {
        "config": cfg,
        "gdelt": poll_gdelt_real(),
        "sec": poll_sec_real(),
        "earnings": poll_earnings_real(),
        "macro": poll_macro_real(),
    }
    return payload
