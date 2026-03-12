def health_guard(import_ok=True, state_files_ok=True, data_quality_ok=True):
    issues = []
    if not import_ok:
        issues.append("IMPORT_FAILURE")
    if not state_files_ok:
        issues.append("STATE_FILES_MISSING")
    if not data_quality_ok:
        issues.append("LOW_DATA_QUALITY")
    return {
        "healthy": len(issues) == 0,
        "issues": issues,
    }
