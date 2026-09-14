import os
import requests
from dotenv import load_dotenv

load_dotenv()

MAP_KEY = os.getenv("FIRMS_MAP_KEY")


def get_fires():

    if not MAP_KEY:
        print("ERROR: FIRMS_MAP_KEY not found in .env")
        return []

    print("Requesting fire data from NASA FIRMS...")

    url = (
        f"https://firms.modaps.eosdis.nasa.gov/"
        f"api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/world/1"
    )

    try:

        response = requests.get(url, timeout=30)

        if response.status_code != 200:

            print("NASA FIRMS request failed.")
            print("Status code:", response.status_code)

            return []

        print("NASA FIRMS data received successfully!")

        lines = response.text.splitlines()

        if len(lines) <= 1:

            print("No fire records found.")

            return []

        # First row contains column names
        headers = lines[0].split(",")

        fires = []

        for line in lines[1:]:

            values = line.split(",")

            if len(values) != len(headers):
                continue

            fire = dict(zip(headers, values))

            try:

                fire_event = {
                    "type": "fire",

                    "latitude": float(
                        fire.get("latitude", 0)
                    ),

                    "longitude": float(
                        fire.get("longitude", 0)
                    ),

                    "confidence": fire.get(
                        "confidence"
                    ),

                    "brightness": fire.get(
                        "bright_ti4"
                    ),

                    "brightness_day": fire.get(
                        "bright_ti5"
                    ),

                    "acq_date": fire.get(
                        "acq_date"
                    ),

                    "acq_time": fire.get(
                        "acq_time"
                    ),

                    "satellite": fire.get(
                        "satellite"
                    ),

                    "instrument": fire.get(
                        "instrument"
                    ),

                    "source": "NASA FIRMS"
                }

                fires.append(fire_event)

            except Exception as e:

                print(
                    "Could not process fire:",
                    e
                )

        print(
            "Number of fire records:",
            len(fires)
        )

        return fires

    except requests.RequestException as e:

        print(
            "Could not connect to NASA FIRMS:",
            e
        )

        return []