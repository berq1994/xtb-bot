def detect_anomaly(metric_value, threshold):
    return {"anomaly": metric_value is not None and metric_value > threshold}
