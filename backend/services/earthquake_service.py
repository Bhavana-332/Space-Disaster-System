import requests


def get_earthquakes():

    print("Requesting earthquake data from USGS...")

    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

    response = requests.get(url)

    if response.status_code != 200:
        print("USGS request failed.")
        return []

    data = response.json()

    earthquakes = []

    for feature in data["features"]:

        properties = feature["properties"]
        coordinates = feature["geometry"]["coordinates"]

        earthquake = {
            "type": "earthquake",
            "title": properties["title"],
            "magnitude": properties["mag"],
            "latitude": coordinates[1],
            "longitude": coordinates[0],
            "depth": coordinates[2],
            "time": properties["time"],
            "source": "USGS"
        }

        earthquakes.append(earthquake)

    return earthquakes