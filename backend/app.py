from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import requests
import pandas as pd
from math import radians, sin, cos, sqrt, atan2, degrees
from datetime import datetime

from fire_event_processor import process_firms_data


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

app = Flask(__name__)
CORS(app)

# Frontend directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

NASA_FIRMS_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/"
    "area/csv"
)

USGS_EARTHQUAKE_URL = (
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/"
    "summary/all_day.geojson"
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Default location
# Only used if /api/weather is opened without coordinates.
DEFAULT_LATITUDE = 17.3850
DEFAULT_LONGITUDE = 78.4867


# ============================================================
# HELPER
# ============================================================

def safe_float(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except:
        return default
def direction_to_degrees(value):
    """Convert numeric or compass direction to degrees clockwise from north."""
    if value in (None, "", -9999, "-9999"):
        return None

    try:
        number = float(value)
        if 0 <= number <= 360:
            return round(number, 1)
    except (TypeError, ValueError):
        pass

    text = str(value).strip().upper().replace("-", " ")
    compass = {
        "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
        "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
        "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
        "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5
    }
    return compass.get(text)


def degrees_to_compass(degrees_value):
    """Convert bearing degrees to an 8/16-point compass label."""
    if degrees_value is None:
        return "Not available"

    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    index = int((float(degrees_value) + 11.25) / 22.5) % 16
    return directions[index]


def parse_atcf_coordinate(value, is_latitude=True):
    """Parse ATCF coordinates such as 176N / 849E into decimal degrees."""
    if value is None:
        return None

    text = str(value).strip().upper()
    if not text:
        return None

    hemisphere = text[-1] if text[-1] in "NSEW" else None
    number_text = text[:-1] if hemisphere else text

    try:
        number = float(number_text)
    except ValueError:
        return None

    # Standard ATCF uses tenths of degrees.
    if abs(number) > (90 if is_latitude else 180):
        number /= 10.0

    if hemisphere in ("S", "W"):
        number = -abs(number)

    return number


def extract_atcf_track_movement(storm):
    """
    Read the storm ATCF sector file and return:
      (movement_direction_degrees, movement_speed_knots, observed_track)

    The observed_track contains recent BEST-track tau-0 positions so the
    frontend can draw the dashed historical path behind the cyclone and a
    heading arrow from the latest position.
    """
    url = storm.get("atcf_sector_file") or storm.get("interp_sector_file")
    if not url or not str(url).lower().startswith(("http://", "https://")):
        return None, None, []

    try:
        response = requests.get(
            str(url),
            timeout=15,
            headers={"User-Agent": "SpaceDisasterSystem/1.0"}
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠️ ATCF track fetch failed: {exc}")
        return None, None, []

    import csv
    from io import StringIO

    rows = []
    try:
        reader = csv.reader(StringIO(response.text))
        for row in reader:
            if len(row) < 28:
                continue

            # ATCF fields: 2 DTG, 4 TECH, 5 TAU, 6 LAT, 7 LON,
            # 26 DIR and 27 SPEED.
            tech = row[4].strip().upper()
            tau = row[5].strip()
            lat = parse_atcf_coordinate(row[6], True)
            lon = parse_atcf_coordinate(row[7], False)
            if lat is None or lon is None:
                continue

            try:
                dtg = datetime.strptime(row[2].strip(), "%Y%m%d%H")
            except ValueError:
                continue

            rows.append({
                "dtg": dtg,
                "tech": tech,
                "tau": tau,
                "lat": lat,
                "lon": lon,
                "direction": direction_to_degrees(row[26].strip()),
                "speed": safe_float(row[27].strip(), None)
            })
    except Exception as exc:
        print(f"⚠️ ATCF track parsing failed: {exc}")
        return None, None, []

    if not rows:
        return None, None, []

    # Prefer BEST tau-0 records: these are observed/current storm positions.
    preferred = [r for r in rows if r["tech"] == "BEST" and r["tau"] == "0"]
    if len(preferred) < 2:
        preferred = [r for r in rows if r["tau"] == "0"]
    preferred.sort(key=lambda r: r["dtg"])

    # Keep a compact recent track for the map.
    track_rows = preferred[-12:] if preferred else []
    observed_track = [
        {
            "latitude": round(r["lat"], 4),
            "longitude": round(r["lon"], 4),
            "time": r["dtg"].isoformat()
        }
        for r in track_rows
    ]

    latest = preferred[-1] if preferred else max(rows, key=lambda r: r["dtg"])

    if latest["direction"] is not None:
        return latest["direction"], latest["speed"], observed_track

    if len(preferred) >= 2:
        previous = preferred[-2]
        lat1 = radians(previous["lat"])
        lat2 = radians(latest["lat"])
        delta_lon = radians(latest["lon"] - previous["lon"])

        x = sin(delta_lon) * cos(lat2)
        y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)
        bearing = (degrees(atan2(x, y)) + 360) % 360

        speed = latest["speed"]
        if speed is None:
            distance_nm = 60 * degrees(
                atan2(
                    sqrt(
                        (cos(lat2) * sin(delta_lon)) ** 2 +
                        (cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)) ** 2
                    ),
                    sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(delta_lon)
                )
            )
            hours = (latest["dtg"] - previous["dtg"]).total_seconds() / 3600
            if hours > 0:
                speed = distance_nm / hours

        return round(bearing, 1), round(speed, 1) if speed is not None else None, observed_track

    return None, None, observed_track

def get_movement_direction(storm):
    """Get cyclone movement direction, preferring ATCF track information."""
    direction = direction_to_degrees(
        storm.get("movedir")
        or storm.get("movement_direction")
        or storm.get("motion_direction")
    )

    return direction


def get_movement_speed(storm):
    """Get cyclone movement speed from direct ATCF metadata."""
    value = (
        storm.get("movespeed")
        or storm.get("movement_speed")
        or storm.get("motion_speed")
    )
    if value in (None, "", -9999, "-9999"):
        return None
    return safe_float(value, None)


# ============================================================
# ROOT
# ============================================================

@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "disaster-map.html")


# ============================================================
# HEALTH
# ============================================================

@app.route("/api/health")
def health():

    return jsonify({

        "success": True,

        "service": "Space Disaster System",

        "status": "running",

        "firms_configured":
            bool(FIRMS_MAP_KEY)

    })


# ============================================================
# NASA FIRMS
# ============================================================

@app.route("/api/fire-events")
def fire_events():

    try:

        if not FIRMS_MAP_KEY:

            return jsonify({

                "success": False,

                "error":
                    "FIRMS_MAP_KEY is not configured in .env"

            }), 500


        print("\n===================================")
        print("FETCHING NASA FIRMS DATA")
        print("===================================")


        url = (
            f"{NASA_FIRMS_URL}/"
            f"{FIRMS_MAP_KEY}/"
            f"VIIRS_NOAA20_NRT/"
            f"world/1"
        )


        response = requests.get(
            url,
            timeout=60
        )

        response.raise_for_status()


        from io import StringIO

        df = pd.read_csv(
            StringIO(response.text)
        )


        print(
            f"NASA FIRMS detections: {len(df)}"
        )

        print(
            "NASA FIRMS columns:"
        )

        print(
            df.columns.tolist()
        )


        if df.empty:

            return jsonify({

                "success": True,

                "source": "NASA FIRMS",

                "events": [],

                "count": 0

            })


        rename_map = {

            "bright_ti4":
                "brightness",

            "bright_ti5":
                "brightness_day"

        }


        df = df.rename(
            columns=rename_map
        )


        if "brightness_day" not in df.columns:

            df["brightness_day"] = df[
                "brightness"
            ]


        required_columns = [

            "latitude",
            "longitude",
            "brightness",
            "brightness_day",
            "confidence",
            "acq_date",
            "acq_time"

        ]


        missing = [

            col
            for col in required_columns
            if col not in df.columns

        ]


        if missing:

            return jsonify({

                "success": False,

                "error":
                    "Missing FIRMS columns",

                "missing":
                    missing,

                "received_columns":
                    df.columns.tolist()

            }), 500


        print(
            "\n[2] Performing spatial clustering..."
        )


        clustered_df, events_df = (
            process_firms_data(df)
        )


        print(
            f"Clusters detected: "
            f"{clustered_df['cluster_id'].nunique()}"
        )


        print(
            "\n[3] Creating fire events..."
        )


        print(
            f"Fire events generated: "
            f"{len(events_df)}"
        )


        events = events_df.to_dict(
            orient="records"
        )


        return jsonify({

            "success": True,

            "source": "NASA FIRMS",

            "count": len(events),

            "events": events

        })


    except Exception as e:

        print("\n❌ FIRMS ERROR:")
        print(str(e))


        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ============================================================
# EARTHQUAKES
# ============================================================

@app.route("/api/earthquakes")
def earthquakes():

    try:

        print(
            "\n🌎 Fetching earthquake data..."
        )


        response = requests.get(
            USGS_EARTHQUAKE_URL,
            timeout=30
        )

        response.raise_for_status()


        data = response.json()


        earthquakes = []


        for feature in data.get(
            "features",
            []
        ):

            geometry = feature.get(
                "geometry",
                {}
            )

            coordinates = geometry.get(
                "coordinates",
                []
            )


            if len(coordinates) < 2:
                continue


            longitude = safe_float(
                coordinates[0]
            )

            latitude = safe_float(
                coordinates[1]
            )

            depth = safe_float(
                coordinates[2],
                0
            ) if len(coordinates) > 2 else 0


            properties = feature.get(
                "properties",
                {}
            )


            magnitude = safe_float(
                properties.get("mag"),
                0
            )


            if magnitude >= 7:

                risk = "CRITICAL"

            elif magnitude >= 6:

                risk = "HIGH"

            elif magnitude >= 4:

                risk = "MODERATE"

            else:

                risk = "LOW"


            earthquakes.append({

                "id":
                    feature.get("id"),

                "type":
                    "EARTHQUAKE",

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "depth":
                    depth,

                "magnitude":
                    magnitude,

                "place":
                    properties.get("place"),

                "time":
                    properties.get("time"),

                "risk_level":
                    risk,

                "source":
                    "USGS"

            })


        print(
            f"Earthquakes received: "
            f"{len(earthquakes)}"
        )


        return jsonify({

            "success": True,

            "source": "USGS",

            "count":
                len(earthquakes),

            "events":
                earthquakes

        })


    except Exception as e:

        print(
            "❌ Earthquake error:",
            str(e)
        )


        return jsonify({

            "success": False,

            "error": str(e),

            "events": []

        }), 500


# ============================================================
# CYCLONES
# ============================================================

# ============================================================
# CYCLONES
# ============================================================

@app.route("/api/cyclones")
def cyclones():

    """
    Fetch active cyclone/storm information
    from KNACKWX ATCF data.
    """

    try:

        print(
            "\n🌀 Fetching cyclone data..."
        )

        # ----------------------------------------------------
        # KNACKWX ATCF ACTIVE STORMS
        # ----------------------------------------------------

        CYCLONE_URL = (
            "https://api.knackwx.com/atcf/v2"
        )

        response = requests.get(
            CYCLONE_URL,
            timeout=30,
            headers={
                "User-Agent":
                    "SpaceDisasterSystem/1.0"
            }
        )

        response.raise_for_status()

        print(
            "Cyclone API status:",
            response.status_code
        )

        print(
            "Cyclone response length:",
            len(response.text)
        )

        # ----------------------------------------------------
        # CHECK RESPONSE BEFORE JSON
        # ----------------------------------------------------

        if not response.text.strip():

            return jsonify({

                "success": False,

                "error":
                    "Cyclone API returned an empty response",

                "events":
                    []

            }), 502


        # ----------------------------------------------------
        # CONVERT RESPONSE TO JSON
        # ----------------------------------------------------

        try:

            data = response.json()

        except ValueError:

            print(
                "❌ Cyclone API did not return valid JSON"
            )

            print(
                "Response preview:"
            )

            print(
                response.text[:500]
            )

            return jsonify({

                "success": False,

                "error":
                    "Cyclone API returned invalid JSON",

                "events":
                    []

            }), 502


        cyclone_events = []

        # ----------------------------------------------------
        # PROCESS RESPONSE
        # ----------------------------------------------------

        if isinstance(data, list):

            records = data

        elif isinstance(data, dict):

            records = (
                data.get("storms")
                or data.get("data")
                or data.get("events")
                or data.get("cyclones")
                or data.get("results")
                or []
            )

        else:

            records = []


        print(
            "Active cyclone records:",
            len(records)
        )


        # ----------------------------------------------------
        # PROCESS EACH ACTIVE CYCLONE
        # ----------------------------------------------------

        for storm in records:

            if not isinstance(
                storm,
                dict
            ):

                continue


            # ------------------------------------------------
            # BASIC INFORMATION
            # ------------------------------------------------

            latitude = safe_float(
                storm.get("latitude"),
                None
            )

            longitude = safe_float(
                storm.get("longitude"),
                None
            )

            # Ignore records without coordinates

            if latitude is None or longitude is None:

                continue


            pressure = safe_float(
                storm.get("pressure"),
                0
            )


            winds = safe_float(
                storm.get("winds")
                or storm.get("wind")
                or storm.get("wind_speed")
                or storm.get("max_wind"),
                0
            )


            storm_name = (

                storm.get("storm_name")

                or storm.get("name")

                or storm.get("storm")

                or "UNKNOWN"

            )


            storm_id = (

                storm.get("atcf_id")

                or storm.get("id")

                or storm.get("storm_id")

                or storm_name

            )


            basin = (

                storm.get("basin")

                or storm.get("origin_basin")

                or storm.get("region")

                or "UNKNOWN"

            )


            # ------------------------------------------------
            # CYCLONE TYPE
            # ------------------------------------------------

            cyclone_nature = (

                storm.get("cyclone_nature")

                or storm.get("nature")

                or storm.get("type")

                or ""

            ).upper()


            if cyclone_nature == "TY":

                severity = "TYPHOON"

            elif cyclone_nature == "ST":

                severity = "SUPER TYPHOON"

            elif cyclone_nature == "HU":

                severity = "HURRICANE"

            elif cyclone_nature == "TC":

                severity = "TROPICAL CYCLONE"

            elif cyclone_nature == "TS":

                severity = "TROPICAL STORM"

            elif cyclone_nature == "TD":

                severity = "TROPICAL DEPRESSION"

            elif cyclone_nature == "DB":

                severity = "DISTURBANCE"

            else:

                severity = (

                    cyclone_nature

                    if cyclone_nature

                    else "UNKNOWN"

                )


            # ------------------------------------------------
            # RISK LEVEL
            # ------------------------------------------------

            if winds >= 100:

                risk_level = "CRITICAL"

            elif winds >= 64:

                risk_level = "HIGH"

            elif winds >= 34:

                risk_level = "MODERATE"

            elif winds > 0:

                risk_level = "LOW"

            else:

                risk_level = "UNKNOWN"


            # ------------------------------------------------
            # MOVEMENT
            # ------------------------------------------------

            # ------------------------------------------------

            movement_direction = get_movement_direction(storm)
            movement_speed = get_movement_speed(storm)

            # KNACKWX exposes an ATCF sector-file URL. Use it when the v2
            # metadata does not already contain motion information.
            track_direction, track_speed, movement_track = extract_atcf_track_movement(storm)

            if movement_direction is None:
                movement_direction = track_direction

            if movement_speed is None:
                movement_speed = track_speed

            if movement_direction is None:
                movement_direction = "Not available"

            """
            movement_direction = (

                storm.get("movedir")

                or storm.get("movement_direction")

                or storm.get("motion_direction")

            )


            movement_speed = (

                storm.get("movespeed")

                or storm.get("movement_speed")

                or storm.get("motion_speed")

            )


            if movement_direction in (

                None,
                "",
                -9999,
                "-9999"

            ):

                movement_direction = "Not available"


            if movement_speed in (

                None,
                "",
                -9999,
                "-9999"

            ):

                movement_speed = None

            else:

                movement_speed = safe_float(
                    movement_speed,
                    None
                )
                """


            # ------------------------------------------------
            # TIME
            # ------------------------------------------------

            observation_time = (

                storm.get("analysis_time")

                or storm.get("time")

                or storm.get("valid_time")

                or storm.get("timestamp")

            )


            # ------------------------------------------------
            # CREATE CYCLONE EVENT
            # ------------------------------------------------

            cyclone_events.append({

                # Identification
                "id": storm_id,
                "type": "CYCLONE",

                # Name
                "name": storm_name,
                "cyclone_name": storm_name,

                # Location
                "latitude": latitude,
                "longitude": longitude,

                # Region
                "basin": basin,

                # Classification
                "severity": severity,
                "risk_level": risk_level,
                "intensity": cyclone_nature,

                # Intensity
                "wind_speed": winds,
                "wind_unit": "knots",
                "pressure": pressure,

                # Movement
                "movement_direction": movement_direction,
                "movement_direction_label": (
                    f"{degrees_to_compass(movement_direction)} ({movement_direction:.1f}°)"
                    if isinstance(movement_direction, (int, float))
                    else str(movement_direction)
                ),
                "movement_speed": movement_speed,
                "movement_speed_unit": "knots",
                "movement_track": movement_track,

                # Time
                "time": observation_time,
                "last_updated": storm.get("last_updated"),

                # Additional ATCF information
                "atcf_id": storm.get("atcf_id"),
                "long_atcf_id": storm.get("long_atcf_id"),
                "transitioned_from": storm.get("transitioned_from"),

                # Source
                "source": "KNACKWX ATCF",

                # Original API record
                "raw": storm

            })


        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        unique_cyclones = {}


        for event in cyclone_events:

            cyclone_id = event["id"]

            unique_cyclones[
                cyclone_id
            ] = event


        cyclone_events = list(
            unique_cyclones.values()
        )


        # ----------------------------------------------------
        # LOG ACTIVE CYCLONES
        # ----------------------------------------------------

        print(
            "\n🌀 ACTIVE CYCLONES:",
            len(cyclone_events)
        )


        for cyclone in cyclone_events:

            print(

                f"   🌪️ {cyclone['name']} | "

                f"{cyclone['latitude']}, "

                f"{cyclone['longitude']} | "

                f"{cyclone['severity']} | "

                f"{cyclone['wind_speed']} kt | "

                f"Moving: "

                f"{cyclone['movement_direction']}"

            )


        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "source":
                "KNACKWX ATCF",

            "count":
                len(cyclone_events),

            "events":
                cyclone_events

        })


    except requests.exceptions.RequestException as e:

        print(
            "❌ Cyclone network error:"
        )

        print(
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                f"Cyclone API request failed: {str(e)}",

            "events":
                []

        }), 502


    except Exception as e:

        print(
            "❌ Cyclone error:"
        )

        print(
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e),

            "events":
                []

        }), 500


# ============================================================
# WEATHER
# ============================================================

@app.route("/api/weather")
def weather():

    try:

        print("\n🌦️ Fetching weather data...")


        # ----------------------------------------------------
        # IMPORTANT
        #
        # The frontend can send:
        #
        # /api/weather?latitude=17.385&longitude=78.4867
        #
        # We also support:
        #
        # /api/weather?lat=17.385&lon=78.4867
        #
        # ----------------------------------------------------

        latitude_value = request.args.get(
            "latitude"
        )

        longitude_value = request.args.get(
            "longitude"
        )


        # Support lat/lon too
        if latitude_value is None:

            latitude_value = request.args.get(
                "lat"
            )


        if longitude_value is None:

            longitude_value = request.args.get(
                "lon"
            )


        # If no location was supplied,
        # use default Hyderabad location.
        if latitude_value is None:

            latitude = DEFAULT_LATITUDE

        else:

            try:

                latitude = float(
                    latitude_value
                )

            except ValueError:

                return jsonify({

                    "success": False,

                    "error":
                        "Invalid latitude"

                }), 400


        if longitude_value is None:

            longitude = DEFAULT_LONGITUDE

        else:

            try:

                longitude = float(
                    longitude_value
                )

            except ValueError:

                return jsonify({

                    "success": False,

                    "error":
                        "Invalid longitude"

                }), 400


        # ----------------------------------------------------
        # VALIDATE COORDINATES
        # ----------------------------------------------------

        if not -90 <= latitude <= 90:

            return jsonify({

                "success": False,

                "error":
                    "Invalid latitude"

            }), 400


        if not -180 <= longitude <= 180:

            return jsonify({

                "success": False,

                "error":
                    "Invalid longitude"

            }), 400


        print(
            f"📍 Weather location: "
            f"{latitude}, {longitude}"
        )


        # ----------------------------------------------------
        # OPEN-METEO PARAMETERS
        # ----------------------------------------------------

        params = {

            "latitude":
                latitude,

            "longitude":
                longitude,

            "current":
                ",".join([

                    "temperature_2m",

                    "relative_humidity_2m",

                    "apparent_temperature",

                    "precipitation",

                    "rain",

                    "weather_code",

                    "wind_speed_10m",

                    "wind_direction_10m"

                ]),

            "timezone":
                "auto"

        }


        # ----------------------------------------------------
        # REQUEST WEATHER
        # ----------------------------------------------------

        response = requests.get(

            OPEN_METEO_URL,

            params=params,

            timeout=(10, 60),

            headers={

                "User-Agent":
                    "SpaceDisasterSystem/1.0"

            }

        )


        response.raise_for_status()


        data = response.json()


        current = data.get(
            "current",
            {}
        )


        # ----------------------------------------------------
        # CREATE WEATHER OBJECT
        # ----------------------------------------------------

        weather_data = {

            "type":
                "weather",

            "latitude":
                latitude,

            "longitude":
                longitude,

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
                    "precipitation"
                ),

            "rain":
                current.get(
                    "rain"
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

            "timezone":
                data.get(
                    "timezone"
                ),

            "source":
                "Open-Meteo"

        }


        print(
            "✅ Weather received:"
        )

        print(
            weather_data
        )


        return jsonify({

            "success":
                True,

            "source":
                "Open-Meteo",

            "data":
                weather_data

        })


    except Exception as e:

        print(
            "❌ Weather error:",
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e),

            "data":
                None

        }), 500


# ============================================================
# COMBINED DISASTERS
# ============================================================

@app.route("/api/disasters")
def disasters():

    try:

        print(
            "\n===================================="
        )

        print(
            "🌍 FETCHING ALL DISASTER DATA"
        )

        print(
            "===================================="
        )


        # ----------------------------------------------------
        # FIRE
        # ----------------------------------------------------

        fire_result = fire_events()


        if isinstance(
            fire_result,
            tuple
        ):

            fire_response = fire_result[0]

        else:

            fire_response = fire_result


        fire_data = fire_response.get_json()


        fire_events_data = fire_data.get(
            "events",
            []
        ) if fire_data else []


        # ----------------------------------------------------
        # EARTHQUAKES
        # ----------------------------------------------------

        earthquake_result = earthquakes()


        if isinstance(
            earthquake_result,
            tuple
        ):

            earthquake_response = (
                earthquake_result[0]
            )

        else:

            earthquake_response = (
                earthquake_result
            )


        earthquake_data = (
            earthquake_response.get_json()
        )


        earthquake_events = (
            earthquake_data.get(
                "events",
                []
            )
            if earthquake_data
            else []
        )


        # ----------------------------------------------------
        # CYCLONES
        # ----------------------------------------------------

        cyclone_result = cyclones()


        if isinstance(
            cyclone_result,
            tuple
        ):

            cyclone_response = (
                cyclone_result[0]
            )

        else:

            cyclone_response = (
                cyclone_result
            )


        cyclone_data = (
            cyclone_response.get_json()
        )


        cyclone_events = (
            cyclone_data.get(
                "events",
                []
            )
            if cyclone_data
            else []
        )


        # ----------------------------------------------------
        # WEATHER
        # ----------------------------------------------------

        weather_result = weather()


        if isinstance(
            weather_result,
            tuple
        ):

            weather_response = (
                weather_result[0]
            )

        else:

            weather_response = (
                weather_result
            )


        weather_data = (
            weather_response.get_json()
        )


        weather_info = (
            weather_data.get("data")
            if weather_data
            else None
        )


        # ----------------------------------------------------
        # COMBINE
        # ----------------------------------------------------

        all_disasters = []


        for event in fire_events_data:

            event = event.copy()

            event["disaster_type"] = "FIRE"

            all_disasters.append(
                event
            )


        for event in earthquake_events:

            event = event.copy()

            event["disaster_type"] = "EARTHQUAKE"

            all_disasters.append(
                event
            )


        for event in cyclone_events:

            event = event.copy()

            event["disaster_type"] = "CYCLONE"

            all_disasters.append(
                event
            )


        print(
            "\n🌍 TOTAL DISASTER EVENTS:",
            len(all_disasters)
        )


        return jsonify({

            "success": True,

            "counts": {

                "fires":
                    len(fire_events_data),

                "earthquakes":
                    len(earthquake_events),

                "cyclones":
                    len(cyclone_events)

            },

            "fires":
                fire_events_data,

            "earthquakes":
                earthquake_events,

            "cyclones":
                cyclone_events,

            "weather":
                weather_info,

            "disasters":
                all_disasters

        })


    except Exception as e:

        print(
            "\n❌ DISASTER API ERROR:"
        )

        print(str(e))


        return jsonify({

            "success": False,

            "error": str(e),

            "fires": [],

            "earthquakes": [],

            "cyclones": [],

            "disasters": [],

            "weather": None

        }), 500


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "\n===================================="
    )

    print(
        "🚀 SPACE DISASTER SYSTEM"
    )

    print(
        "===================================="
    )

    print(
        "Server: http://localhost:5000"
    )

    print(
        "FIRMS:",
        "Configured"
        if FIRMS_MAP_KEY
        else "NOT CONFIGURED"
    )

    print(
        "\nAvailable APIs:"
    )

    print(
        "  GET /api/fire-events"
    )

    print(
        "  GET /api/earthquakes"
    )

    print(
        "  GET /api/cyclones"
    )

    print(
        "  GET /api/weather"
    )

    print(
        "  GET /api/disasters"
    )

    print(
        "  GET /api/health"
    )

    print(
        "\n====================================\n"
    )


    app.run(

        host="0.0.0.0",

        port=int(os.environ.get("PORT", 5000)),

        debug=True

    )