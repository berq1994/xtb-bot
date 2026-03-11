def render_sources_report(payload: dict):
    lines = ["REAL SOURCES REPORT"]
    for key in ["gdelt", "sec", "earnings", "macro"]:
        row = payload.get(key, {})
        lines.append(f"{key.upper()}: enabled={row.get('enabled')} ok={row.get('ok')} reason={row.get('reason')}")
    return "\n".join(lines)
