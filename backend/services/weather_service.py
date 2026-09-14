import requests


def get_weather(latitude, longitude):

    print("Requesting weather data...")

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
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
        "forecast_days": 3,
        "timezone": "auto"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print("Weather API failed.")
        print("Status code:", response.status_code)
        return None

    data = response.json()

    current = data["current"]

    weather = {
        "type": "weather",

    "latitude": latitude,
    "longitude": longitude,

    # Current conditions
    "temperature": current["temperature_2m"],
    "humidity": current["relative_humidity_2m"],
    "apparent_temperature": current["apparent_temperature"],
    "precipitation": current["precipitation"],
    "rain": current["rain"],
    "weather_code": current["weather_code"],
    "wind_speed": current["wind_speed_10m"],
    "wind_direction": current["wind_direction_10m"],

    # Forecast
    "forecast": data["hourly"],

    "source": "Open-Meteo"
    }

    return weather