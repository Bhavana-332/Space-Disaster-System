def create_disaster_event(
    disaster_type,
    latitude,
    longitude,
    severity,
    status,
    timestamp,
    source,
    details=None
):
    """
    Convert different disaster sources
    into one common format.
    """

    return {
        "type": disaster_type,
        "latitude": latitude,
        "longitude": longitude,
        "severity": severity,
        "status": status,
        "timestamp": timestamp,
        "source": source,
        "details": details or {}
    }