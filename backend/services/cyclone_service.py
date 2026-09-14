import requests


def get_cyclones():

    print("Requesting cyclone data from GDACS...")

    url = (
        "https://www.gdacs.org/gdacsapi/api/"
        "Events/geteventlist/SEARCH"
        "?eventlist=TC"
    )

    response = requests.get(url)

    if response.status_code != 200:
        print("GDACS request failed.")
        print("Status code:", response.status_code)
        return []

    try:
        data = response.json()
    except ValueError:
        print("GDACS returned invalid JSON.")
        return []

    print("GDACS response received!")

    # Show the structure for us to inspect
    if isinstance(data, dict):
        print("Response keys:", data.keys())

    cyclones = []

    # GDACS normally returns GeoJSON-style features
    features = data.get("features", [])

    for feature in features:

        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        coordinates = geometry.get("coordinates", [])

        if len(coordinates) >= 2:

            cyclone = {
                "type": "cyclone",
                "name": properties.get("name"),
                "latitude": coordinates[1],
                "longitude": coordinates[0],
                "source": "GDACS"
            }

            cyclones.append(cyclone)

    return cyclones