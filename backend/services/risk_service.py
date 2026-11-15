"""
Risk Intelligence Engine for SpaceDisasterSystem.

These calculations are dashboard screening heuristics.
They are NOT official emergency warnings or predictions.
"""


def calculate_weather_risk(weather):
    """
    Analyze current and forecast weather conditions.
    """

    risks = []

    temperature = float(
        weather.get("apparent_temperature", 0) or 0
    )

    rain = float(
        weather.get("rain", 0) or 0
    )

    wind = float(
        weather.get("wind_speed", 0) or 0
    )

    # =========================
    # CURRENT HEAT
    # =========================

    if temperature >= 45:

        risks.append({
            "type": "heat",
            "risk": "HIGH",
            "status": "NOW",
            "message": "Extreme heat conditions detected."
        })

    elif temperature >= 40:

        risks.append({
            "type": "heat",
            "risk": "MEDIUM",
            "status": "NOW",
            "message": "High heat conditions detected."
        })

    # =========================
    # CURRENT RAIN
    # =========================

    if rain >= 20:

        risks.append({
            "type": "heavy_rain",
            "risk": "HIGH",
            "status": "NOW",
            "message": "Heavy rainfall detected."
        })

    elif rain >= 10:

        risks.append({
            "type": "heavy_rain",
            "risk": "MEDIUM",
            "status": "NOW",
            "message": "Moderate to heavy rainfall detected."
        })

    # =========================
    # CURRENT WIND
    # =========================

    if wind >= 60:

        risks.append({
            "type": "strong_wind",
            "risk": "HIGH",
            "status": "NOW",
            "message": "Very strong winds detected."
        })

    elif wind >= 40:

        risks.append({
            "type": "strong_wind",
            "risk": "MEDIUM",
            "status": "NOW",
            "message": "Strong winds detected."
        })

    # =========================
    # FORECAST
    # =========================

    forecast = weather.get("forecast") or {}

    rainfall = forecast.get(
        "precipitation",
        []
    ) or []

    rain_probability = forecast.get(
        "precipitation_probability",
        []
    ) or []

    temperatures = forecast.get(
        "temperature_2m",
        []
    ) or []

    forecast_wind = forecast.get(
        "wind_speed_10m",
        []
    ) or []

    forecast_times = forecast.get(
        "time",
        []
    ) or []

    # =========================
    # FORECAST HEAVY RAIN
    # =========================

    for i, amount in enumerate(rainfall):

        probability = (
            rain_probability[i]
            if i < len(rain_probability)
            else 0
        )

        if (
            float(amount or 0) >= 20
            and float(probability or 0) >= 60
        ):

            risks.append({

                "type": "heavy_rain",

                "risk": "HIGH",

                "status": "FORECAST",

                "expected_time":
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown",

                "rainfall":
                    amount,

                "probability":
                    probability,

                "message":
                    "Heavy rainfall is expected."
            })

            break

    # =========================
    # FORECAST HEAT
    # =========================

    for i, temperature_value in enumerate(
        temperatures
    ):

        if float(temperature_value or 0) >= 42:

            risks.append({

                "type": "heat",

                "risk": "HIGH",

                "status": "FORECAST",

                "expected_time":
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown",

                "temperature":
                    temperature_value,

                "message":
                    "Extreme temperature is expected."
            })

            break

    # =========================
    # FORECAST WIND
    # =========================

    for i, wind_value in enumerate(
        forecast_wind
    ):

        if float(wind_value or 0) >= 60:

            risks.append({

                "type": "strong_wind",

                "risk": "HIGH",

                "status": "FORECAST",

                "expected_time":
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown",

                "wind_speed":
                    wind_value,

                "message":
                    "Very strong winds are expected."
            })

            break

    return risks


# ============================================================
# FIRE + WEATHER COMBINED RISK
# ============================================================

def calculate_combined_fire_risk(
    fire,
    weather
):

    """
    Combine NASA FIRMS fire information
    with nearby weather conditions.
    """

    # =========================
    # FIRE DATA
    # =========================

    brightness = float(
        fire.get(
            "max_brightness",
            fire.get("brightness", 0)
        ) or 0
    )

    detections = int(
        float(
            fire.get(
                "detections",
                1
            ) or 1
        )
    )

    confidence = str(
        fire.get(
            "confidence",
            "n"
        )
    ).lower()

    # =========================
    # FIRE SCORE
    # =========================

    brightness_score = max(
        0,
        min(
            45,
            (brightness - 300) * 0.5
        )
    )

    detection_score = max(
        0,
        min(
            25,
            detections * 2.5
        )
    )

    if confidence in (
        "h",
        "high"
    ):

        confidence_score = 30

    elif confidence in (
        "n",
        "nominal",
        "medium"
    ):

        confidence_score = 18

    else:

        confidence_score = 10

    fire_score = round(
        min(
            100,
            brightness_score
            + detection_score
            + confidence_score
        ),
        1
    )

    # =========================
    # WEATHER DATA
    # =========================

    temperature = float(
        weather.get(
            "apparent_temperature",
            0
        ) or 0
    )

    rain = float(
        weather.get(
            "rain",
            0
        ) or 0
    )

    wind = float(
        weather.get(
            "wind_speed",
            0
        ) or 0
    )

    # =========================
    # WEATHER MODIFIERS
    # =========================

    heat_factor = min(
        15,
        max(
            0,
            temperature - 30
        )
    )

    dry_factor = max(
        0,
        min(
            15,
            15 - rain * 0.75
        )
    )

    wind_factor = max(
        0,
        min(
            10,
            wind / 6
        )
    )

    weather_modifier = round(
        heat_factor
        + dry_factor
        + wind_factor,
        1
    )

    # =========================
    # COMBINED SCORE
    # =========================

    combined_score = round(
        min(
            100,
            fire_score * 0.70
            + weather_modifier * 2.0
        ),
        1
    )

    # =========================
    # RISK LEVEL
    # =========================

    if combined_score >= 75:

        level = "CRITICAL"

    elif combined_score >= 55:

        level = "HIGH"

    elif combined_score >= 35:

        level = "MODERATE"

    else:

        level = "LOW"

    # =========================
    # EXPLAINABLE FACTORS
    # =========================

    factors = [

        {
            "name":
                "NASA fire signal",

            "value":
                fire_score,

            "weight":
                "70%"
        },

        {
            "name":
                "Heat stress",

            "value":
                round(
                    heat_factor,
                    1
                ),

            "weight":
                "weather"
        },

        {
            "name":
                "Dryness",

            "value":
                round(
                    dry_factor,
                    1
                ),

            "weight":
                "weather"
        },

        {
            "name":
                "Wind",

            "value":
                round(
                    wind_factor,
                    1
                ),

            "weight":
                "weather"
        }

    ]

    return {

        "score":
            combined_score,

        "level":
            level,

        "fire_score":
            fire_score,

        "weather_modifier":
            weather_modifier,

        "factors":
            factors,

        "weather_risks":
            calculate_weather_risk(
                weather
            ),

        "method":
            "70% NASA fire signal + weather screening factors",

        "disclaimer":
            "Heuristic dashboard screening score; "
            "not an official warning or emergency forecast."
    }
# ============================================================
# STAGE 3 — FLOOD / HEAT / EXTREME RAIN INTELLIGENCE
# ============================================================

def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _forecast_arrays(weather):
    forecast = weather.get("forecast") or {}

    return (
        forecast.get("time") or [],
        forecast.get("precipitation") or [],
        forecast.get("precipitation_probability") or [],
        forecast.get("temperature_2m") or [],
    )


def calculate_extreme_rain_risk(weather):
    """
    Screen current and forecast rainfall conditions.

    This is a dashboard heuristic, not an official flood warning.
    """

    current_rain = _safe_float(weather.get("rain"))
    current_precipitation = _safe_float(
        weather.get("precipitation")
    )

    times, rainfall, probabilities, _ = _forecast_arrays(weather)

    max_forecast_rain = 0.0
    max_probability = 0.0
    expected_time = None

    for i, amount in enumerate(rainfall):
        amount = _safe_float(amount)
        probability = (
            _safe_float(probabilities[i])
            if i < len(probabilities)
            else 0.0
        )

        if amount > max_forecast_rain:
            max_forecast_rain = amount
            max_probability = probability
            expected_time = (
                times[i] if i < len(times) else None
            )

    if current_rain >= 30 or (
        max_forecast_rain >= 30 and max_probability >= 60
    ):
        level = "HIGH"
    elif current_rain >= 15 or (
        max_forecast_rain >= 20 and max_probability >= 50
    ):
        level = "MODERATE"
    else:
        level = "LOW"

    return {
        "type": "extreme_rain",
        "level": level,
        "current_rain": round(current_rain, 1),
        "current_precipitation": round(current_precipitation, 1),
        "max_forecast_rain": round(max_forecast_rain, 1),
        "forecast_probability": round(max_probability, 1),
        "expected_time": expected_time,
        "message": (
            "High rainfall conditions detected."
            if level == "HIGH"
            else
            "Elevated rainfall conditions detected."
            if level == "MODERATE"
            else
            "No extreme rainfall signal detected."
        ),
    }


def calculate_flood_risk(weather):
    """
    Estimate localized flood potential using rainfall intensity,
    forecast probability, and persistence of rainfall.

    This does not use river gauges, drainage maps, soil saturation,
    elevation, or official flood warnings.
    """

    current_rain = _safe_float(weather.get("rain"))
    current_precipitation = _safe_float(
        weather.get("precipitation")
    )

    times, rainfall, probabilities, _ = _forecast_arrays(weather)

    heavy_hours = 0
    cumulative_forecast_rain = 0.0
    peak_rain = 0.0
    peak_probability = 0.0
    peak_time = None

    for i, amount in enumerate(rainfall):
        amount = _safe_float(amount)
        probability = (
            _safe_float(probabilities[i])
            if i < len(probabilities)
            else 0.0
        )

        cumulative_forecast_rain += amount

        if amount > peak_rain:
            peak_rain = amount
            peak_probability = probability
            peak_time = (
                times[i] if i < len(times) else None
            )

        if amount >= 10 and probability >= 50:
            heavy_hours += 1

    score = 0.0

    if current_rain >= 30:
        score += 35
    elif current_rain >= 15:
        score += 20
    elif current_rain >= 5:
        score += 8

    if peak_rain >= 30 and peak_probability >= 60:
        score += 30
    elif peak_rain >= 20 and peak_probability >= 50:
        score += 20
    elif peak_rain >= 10 and peak_probability >= 40:
        score += 10

    if cumulative_forecast_rain >= 80:
        score += 25
    elif cumulative_forecast_rain >= 50:
        score += 18
    elif cumulative_forecast_rain >= 25:
        score += 10

    if heavy_hours >= 6:
        score += 10
    elif heavy_hours >= 3:
        score += 6

    score = round(min(100, score), 1)

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MODERATE"
    else:
        level = "LOW"

    return {
        "type": "flood",
        "score": score,
        "level": level,
        "current_rain": round(current_rain, 1),
        "current_precipitation": round(current_precipitation, 1),
        "peak_forecast_rain": round(peak_rain, 1),
        "peak_probability": round(peak_probability, 1),
        "forecast_rain_total": round(cumulative_forecast_rain, 1),
        "heavy_rain_hours": heavy_hours,
        "peak_time": peak_time,
        "message": (
            "Significant rainfall may increase localized flood potential."
            if level == "HIGH"
            else
            "Rainfall conditions may contribute to localized water accumulation."
            if level == "MODERATE"
            else
            "No strong rainfall-based flood signal detected."
        ),
    }


def calculate_heat_risk(weather):
    """
    Screen current and forecast heat conditions.
    """

    current_temperature = _safe_float(
        weather.get("apparent_temperature")
    )

    _, _, _, temperatures = _forecast_arrays(weather)

    peak_temperature = current_temperature
    peak_time = None

    for i, value in enumerate(temperatures):
        value = _safe_float(value)

        if value > peak_temperature:
            peak_temperature = value
            forecast = weather.get("forecast") or {}
            times = forecast.get("time") or []
            peak_time = (
                times[i] if i < len(times) else None
            )

    if current_temperature >= 45 or peak_temperature >= 45:
        level = "HIGH"
    elif current_temperature >= 40 or peak_temperature >= 42:
        level = "MODERATE"
    else:
        level = "LOW"

    return {
        "type": "heat",
        "level": level,
        "current_apparent_temperature": round(
            current_temperature, 1
        ),
        "peak_forecast_temperature": round(
            peak_temperature, 1
        ),
        "peak_time": peak_time,
        "message": (
            "Extreme heat conditions detected."
            if level == "HIGH"
            else
            "Elevated heat conditions detected."
            if level == "MODERATE"
            else
            "No strong heat-risk signal detected."
        ),
    }


def calculate_combined_weather_risk(weather):
    """
    Combine flood, extreme-rain, heat and wind signals.

    The result is a dashboard screening score only.
    """

    flood = calculate_flood_risk(weather)
    rain = calculate_extreme_rain_risk(weather)
    heat = calculate_heat_risk(weather)
    weather_risks = calculate_weather_risk(weather)

    score = 0.0

    level_values = {
        "LOW": 0,
        "MODERATE": 40,
        "HIGH": 75,
    }

    score += level_values.get(flood["level"], 0) * 0.40
    score += level_values.get(rain["level"], 0) * 0.25
    score += level_values.get(heat["level"], 0) * 0.25

    wind_risk = 0
    for item in weather_risks:
        if item.get("type") == "strong_wind":
            if item.get("risk") == "HIGH":
                wind_risk = 75
            elif item.get("risk") == "MEDIUM":
                wind_risk = 40

    score += wind_risk * 0.10
    score = round(min(100, score), 1)

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MODERATE"
    else:
        level = "LOW"

    factors = []

    if flood["level"] != "LOW":
        factors.append({
            "type": "flood",
            "level": flood["level"],
            "message": flood["message"]
        })

    if rain["level"] != "LOW":
        factors.append({
            "type": "extreme_rain",
            "level": rain["level"],
            "message": rain["message"]
        })

    if heat["level"] != "LOW":
        factors.append({
            "type": "heat",
            "level": heat["level"],
            "message": heat["message"]
        })

    if wind_risk:
        factors.append({
            "type": "wind",
            "level": "HIGH" if wind_risk == 75 else "MODERATE",
            "message": "Strong wind conditions detected."
        })

    return {
        "score": score,
        "level": level,
        "flood": flood,
        "extreme_rain": rain,
        "heat": heat,
        "weather_risks": weather_risks,
        "factors": factors,
        "method": (
            "Rainfall + forecast persistence + heat + wind "
            "dashboard screening heuristic"
        ),
        "disclaimer": (
            "Heuristic dashboard screening score; "
            "not an official warning or emergency forecast."
        )
    }
