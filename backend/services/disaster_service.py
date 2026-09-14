from services.fire_service import get_fires
from services.weather_service import get_weather
from services.normalizer import create_disaster_event


# ==========================================
# FIRE SEVERITY
# ==========================================

def calculate_fire_severity(fire):

    confidence = fire.get("confidence", 0)

    try:
        confidence = float(confidence)
    except:
        confidence = 0

    if confidence >= 80:

        return "HIGH"

    elif confidence >= 50:

        return "MEDIUM"

    else:

        return "LOW"


# ==========================================
# COLLECT ALL DISASTERS
# ==========================================

def collect_disasters(latitude, longitude):

    all_events = []


    # ======================================
    # NASA FIRMS - FIRE DATA
    # ======================================

    print("\n🔥 Collecting fire data...")

    fires = get_fires()

    for fire in fires:

        try:

            # Combine date + time
            timestamp = None

            if fire.get("acq_date"):

                timestamp = fire["acq_date"]

                if fire.get("acq_time"):

                    timestamp += " " + fire["acq_time"]


            event = create_disaster_event(

                disaster_type="fire",

                latitude=fire["latitude"],

                longitude=fire["longitude"],

                severity=calculate_fire_severity(
                    fire
                ),

                status="NOW",

                timestamp=timestamp,

                source="NASA FIRMS",

                details=fire
            )


            all_events.append(event)


        except Exception as e:

            print(
                "Could not process fire:",
                e
            )


    # ======================================
    # OPEN-METEO - WEATHER DATA
    # ======================================

    print("\n🌦️ Collecting weather data...")

    weather = get_weather(
        latitude,
        longitude
    )


    if weather:

        weather_event = create_disaster_event(

            disaster_type="weather",

            latitude=latitude,

            longitude=longitude,

            severity="LOW",

            status="NOW",

            timestamp=None,

            source="Open-Meteo",

            details=weather
        )


        all_events.append(
            weather_event
        )


    # ======================================
    # RETURN EVERYTHING
    # ======================================

    return all_events