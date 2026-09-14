def calculate_weather_risk(weather):

    risks = []

    # =========================
    # CURRENT WEATHER
    # =========================

    apparent_temperature = weather["apparent_temperature"]
    rain = weather["rain"]
    wind_speed = weather["wind_speed"]

    # -------------------------
    # CURRENT HEAT
    # -------------------------

    if apparent_temperature >= 45:

        risks.append({
            "type": "heat",
            "risk": "HIGH",
            "status": "NOW",
            "message": "Extreme heat conditions detected."
        })

    elif apparent_temperature >= 40:

        risks.append({
            "type": "heat",
            "risk": "MEDIUM",
            "status": "NOW",
            "message": "High heat conditions detected."
        })


    # -------------------------
    # CURRENT RAIN
    # -------------------------

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


    # -------------------------
    # CURRENT WIND
    # -------------------------

    if wind_speed >= 60:

        risks.append({
            "type": "strong_wind",
            "risk": "HIGH",
            "status": "NOW",
            "message": "Very strong winds detected."
        })

    elif wind_speed >= 40:

        risks.append({
            "type": "strong_wind",
            "risk": "MEDIUM",
            "status": "NOW",
            "message": "Strong winds detected."
        })


    # =========================
    # FORECAST ANALYSIS
    # =========================

    forecast = weather.get("forecast")

    if forecast:

        rainfall = forecast.get(
            "precipitation", []
        )

        rain_probability = forecast.get(
            "precipitation_probability", []
        )

        temperatures = forecast.get(
            "temperature_2m", []
        )

        forecast_wind = forecast.get(
            "wind_speed_10m", []
        )

        # ⭐ NEW: Forecast timestamps
        forecast_times = forecast.get(
            "time", []
        )


        # =========================
        # UPCOMING HEAVY RAIN
        # =========================

        for i in range(len(rainfall)):

            rain_amount = rainfall[i]

            probability = (
                rain_probability[i]
                if i < len(rain_probability)
                else 0
            )

            if rain_amount >= 20 and probability >= 60:

                expected_time = (
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown"
                )

                risks.append({
                    "type": "heavy_rain",
                    "risk": "HIGH",
                    "status": "FORECAST",
                    "expected_time": expected_time,
                    "rainfall": rain_amount,
                    "probability": probability,
                    "message": "Heavy rainfall is expected."
                })

                break


        # =========================
        # UPCOMING HEAT
        # =========================

        for i in range(len(temperatures)):

            temperature = temperatures[i]

            if temperature >= 42:

                expected_time = (
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown"
                )

                risks.append({
                    "type": "heat",
                    "risk": "HIGH",
                    "status": "FORECAST",
                    "expected_time": expected_time,
                    "temperature": temperature,
                    "message": "Extreme temperature is expected."
                })

                break


        # =========================
        # UPCOMING STRONG WIND
        # =========================

        for i in range(len(forecast_wind)):

            wind = forecast_wind[i]

            if wind >= 60:

                expected_time = (
                    forecast_times[i]
                    if i < len(forecast_times)
                    else "Unknown"
                )

                risks.append({
                    "type": "strong_wind",
                    "risk": "HIGH",
                    "status": "FORECAST",
                    "expected_time": expected_time,
                    "wind_speed": wind,
                    "message": "Very strong winds are expected."
                })

                break


    return risks