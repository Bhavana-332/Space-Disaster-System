import requests


def get_weather(latitude, longitude):

    print("Requesting weather data...")

    url = (
        "https://api.open-meteo.com/v1/forecast"
    )

    params = {

        "latitude":
            latitude,

        "longitude":
            longitude,

        "current": [

            "temperature_2m",

            "relative_humidity_2m",

            "apparent_temperature",

            "precipitation",

            "rain",

            "weather_code",

            "wind_speed_10m",

            "wind_direction_10m"

        ],

        "hourly": [

            "temperature_2m",

            "precipitation_probability",

            "precipitation",

            "rain",

            "wind_speed_10m"

        ],

        "forecast_days":
            3,

        "timezone":
            "auto"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as e:

        print(
            "Weather API request failed:",
            str(e)
        )

        return None

    except ValueError as e:

        print(
            "Weather API returned invalid JSON:",
            str(e)
        )

        return None

    current = data.get(
        "current",
        {}
    )

    weather = {

        "type":
            "weather",

        "latitude":
            latitude,

        "longitude":
            longitude,

        # Current conditions
        "temperature":
            current.get(
                "temperature_2m"
            ),

        "humidity":
            current.get(
                "relative_humidity_2m"
            ),

        "apparent_temperature":
            current.get(
                "apparent_temperature"
            ),

        "precipitation":
            current.get(
                "precipitation",
                0
            ),

        "rain":
            current.get(
                "rain",
                0
            ),

        "weather_code":
            current.get(
                "weather_code"
            ),

        "wind_speed":
            current.get(
                "wind_speed_10m"
            ),

        "wind_direction":
            current.get(
                "wind_direction_10m"
            ),

        # Forecast
        "forecast":
            data.get(
                "hourly",
                {}
            ),

        "source":
            "Open-Meteo"
    }

    return weather
# Stage 3 note:
# The existing 3-day hourly forecast already provides the rainfall,
# precipitation probability, and temperature data used by the
# Stage 3 risk engine.
