def source_registry():
    return {
        "geo": ["gdelt", "official_gov", "major_news"],
        "corporate": ["sec", "ir_pages", "press_release"],
        "earnings": ["fmp_calendar", "sec", "transcripts"],
        "macro": ["calendar", "central_bank", "official_stats"],
    }
