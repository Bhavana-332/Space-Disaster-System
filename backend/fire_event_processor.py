import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN


# ============================================================
# CONFIGURATION
# ============================================================

# Maximum distance between two FIRMS detections
# belonging to the same fire cluster.
CLUSTER_RADIUS_KM = 2.0

# Minimum number of detections for DBSCAN.
#
# We use 1 because we don't want to discard individual
# FIRMS detections. A single detection will still become
# its own fire event.
MIN_SAMPLES = 1

# Earth's radius in kilometers.
EARTH_RADIUS_KM = 6371.0088


# ============================================================
# 1. CLEAN FIRMS DATA
# ============================================================

def clean_firms_data(df):

    print("\n📡 FIRMS columns received:")
    print(df.columns.tolist())

    # Normalize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # FIRMS sometimes uses different names
    column_mapping = {
        "lat": "latitude",
        "lon": "longitude",
        "bright_ti4": "brightness",
        "bright_ti5": "brightness_day",
        "bright_ti4": "brightness",
        "confidence": "confidence",
        "acq_date": "acq_date",
        "acq_time": "acq_time"
    }

    df = df.rename(columns=column_mapping)

    print("\n🔄 Normalized columns:")
    print(df.columns.tolist())

    # Only require columns actually needed by the processor
    required_columns = [
        "latitude",
        "longitude",
        "brightness",
        "confidence"
    ]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"Missing required column: {col}. "
                f"Available columns: {df.columns.tolist()}"
            )

    # Optional FIRMS fields
    if "brightness_day" not in df.columns:
        df["brightness_day"] = df["brightness"]

    if "acq_date" not in df.columns:
        df["acq_date"] = ""

    if "acq_time" not in df.columns:
        df["acq_time"] = ""

    # Convert numeric fields
    numeric_columns = [
        "latitude",
        "longitude",
        "brightness",
        "brightness_day"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # Remove invalid coordinates
    df = df[
        df["latitude"].between(-90, 90) &
        df["longitude"].between(-180, 180)
    ]

    # Remove rows without coordinates
    df = df.dropna(
        subset=[
            "latitude",
            "longitude"
        ]
    )

    # Normalize confidence
    df["confidence"] = (
        df["confidence"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    return df.reset_index(drop=True)

    # --------------------------------------------------------
    # Remove invalid coordinates
    # --------------------------------------------------------

    df = df[
        df["latitude"].between(-90, 90)
        &
        df["longitude"].between(-180, 180)
    ]

    # --------------------------------------------------------
    # Remove rows without coordinates
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "latitude",
            "longitude"
        ]
    )

    # --------------------------------------------------------
    # Normalize confidence
    # --------------------------------------------------------

    df["confidence"] = (
        df["confidence"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

    # --------------------------------------------------------
    # Normalize acquisition time
    # --------------------------------------------------------

    df["acq_time"] = (
        df["acq_time"]
        .astype(str)
        .str.zfill(4)
    )

    # Reset index
    df = df.reset_index(drop=True)

    print(
        f"Valid FIRMS detections: {len(df)}"
    )

    return df


# ============================================================
# 2. SPATIAL CLUSTERING
# ============================================================

def cluster_fire_detections(
    df,
    radius_km=CLUSTER_RADIUS_KM,
    min_samples=MIN_SAMPLES
):

    print("\n[2] Performing spatial clustering...")

    df = df.copy()

    # Handle empty dataframe
    if df.empty:

        df["cluster_id"] = []

        return df

    # --------------------------------------------------------
    # Convert latitude/longitude to radians
    # --------------------------------------------------------

    coordinates = np.radians(
        df[
            [
                "latitude",
                "longitude"
            ]
        ].values
    )

    # --------------------------------------------------------
    # Convert kilometers to radians
    # --------------------------------------------------------

    epsilon = radius_km / EARTH_RADIUS_KM

    # --------------------------------------------------------
    # DBSCAN
    # --------------------------------------------------------

    clustering = DBSCAN(
        eps=epsilon,
        min_samples=min_samples,
        metric="haversine"
    )

    labels = clustering.fit_predict(
        coordinates
    )

    df["cluster_id"] = labels

    # --------------------------------------------------------
    # DBSCAN uses -1 for noise.
    #
    # We don't want to throw away a FIRMS detection.
    # Every noise point becomes an individual fire event.
    # --------------------------------------------------------

    next_cluster_id = (
        int(df["cluster_id"].max()) + 1
        if len(df) > 0
        else 0
    )

    for index in df.index:

        if df.loc[index, "cluster_id"] == -1:

            df.loc[
                index,
                "cluster_id"
            ] = next_cluster_id

            next_cluster_id += 1

    df["cluster_id"] = (
        df["cluster_id"]
        .astype(int)
    )

    number_of_clusters = (
        df["cluster_id"]
        .nunique()
    )

    print(
        f"Clusters detected: "
        f"{number_of_clusters}"
    )

    return df


# ============================================================
# 3. CONFIDENCE SCORE
# ============================================================

def confidence_score(confidence):

    confidence = (
        str(confidence)
        .lower()
        .strip()
    )

    # FIRMS confidence values:
    #
    # h = high
    # n = nominal
    # l = low

    if confidence == "h":

        return 100

    elif confidence == "n":

        return 60

    elif confidence == "l":

        return 30

    # Unknown confidence
    return 50


# ============================================================
# 4. BRIGHTNESS SCORE
# ============================================================

def brightness_score(brightness):

    if pd.isna(brightness):

        return 0

    brightness = float(brightness)

    # Approximate scoring based on
    # VIIRS brightness temperature.

    if brightness >= 360:

        return 100

    elif brightness >= 340:

        return 85

    elif brightness >= 320:

        return 70

    elif brightness >= 300:

        return 50

    elif brightness >= 280:

        return 30

    else:

        return 10


# ============================================================
# 5. CLUSTER SIZE SCORE
# ============================================================

def cluster_size_score(
    number_of_detections
):

    if number_of_detections >= 20:

        return 100

    elif number_of_detections >= 10:

        return 85

    elif number_of_detections >= 5:

        return 70

    elif number_of_detections >= 3:

        return 55

    elif number_of_detections == 2:

        return 40

    # Single detection
    return 20


# ============================================================
# 6. FIRE RISK SCORE
# ============================================================

def calculate_risk_score(
    brightness,
    confidence,
    detection_count
):

    # ------------------------------------
    # Individual components
    # ------------------------------------

    brightness_component = brightness_score(
        brightness
    )

    confidence_component = confidence_score(
        confidence
    )

    cluster_component = cluster_size_score(
        detection_count
    )

    # ------------------------------------
    # Weighted risk calculation
    #
    # Brightness     = 40%
    # Confidence     = 30%
    # Cluster size   = 30%
    # ------------------------------------

    risk_score = (

        brightness_component * 0.40

        +

        confidence_component * 0.30

        +

        cluster_component * 0.30
    )

    return round(
        risk_score,
        2
    )


# ============================================================
# 7. RISK LEVEL
# ============================================================

def risk_level(score):

    if score >= 80:

        return "CRITICAL"

    elif score >= 60:

        return "HIGH"

    elif score >= 40:

        return "MODERATE"

    else:

        return "LOW"


# ============================================================
# 8. CREATE FIRE EVENTS
# ============================================================

def create_fire_events(df):

    print("\n[3] Creating fire events...")

    events = []

    # Handle empty dataframe
    if df.empty:

        return pd.DataFrame()

    # --------------------------------------------------------
    # Group detections by cluster
    # --------------------------------------------------------

    grouped = df.groupby(
        "cluster_id"
    )

    # Confidence priority
    confidence_priority = {

        "h": 3,

        "n": 2,

        "l": 1
    }

    # --------------------------------------------------------
    # Process each cluster
    # --------------------------------------------------------

    for cluster_id, cluster in grouped:

        # Number of FIRMS detections
        detection_count = len(
            cluster
        )

        # ----------------------------------------------------
        # Cluster center
        # ----------------------------------------------------

        center_latitude = (
            cluster["latitude"].mean()
        )

        center_longitude = (
            cluster["longitude"].mean()
        )

        # ----------------------------------------------------
        # Brightness
        # ----------------------------------------------------

        max_brightness = (
            cluster["brightness"].max()
        )

        average_brightness = (
            cluster["brightness"].mean()
        )

        # ----------------------------------------------------
        # Highest confidence
        # ----------------------------------------------------

        cluster_confidences = (
            cluster["confidence"]
            .tolist()
        )

        highest_confidence = max(
            cluster_confidences,
            key=lambda x:
                confidence_priority.get(
                    x,
                    0
                )
        )

        # ----------------------------------------------------
        # Calculate risk
        # ----------------------------------------------------

        score = calculate_risk_score(

            max_brightness,

            highest_confidence,

            detection_count
        )

        level = risk_level(
            score
        )

        # ----------------------------------------------------
        # Acquisition information
        # ----------------------------------------------------

        acq_date = (
            cluster["acq_date"]
            .iloc[0]
        )

        acq_time = (
            cluster["acq_time"]
            .iloc[0]
        )

        # ----------------------------------------------------
        # Create fire event
        # ----------------------------------------------------

        events.append({

            "fire_event_id":
                f"FIRE-{int(cluster_id):04d}",

            "latitude":
                round(
                    center_latitude,
                    6
                ),

            "longitude":
                round(
                    center_longitude,
                    6
                ),

            "detections":
                detection_count,

            "max_brightness":
                round(
                    max_brightness,
                    2
                ),

            "average_brightness":
                round(
                    average_brightness,
                    2
                ),

            "confidence":
                highest_confidence,

            "risk_score":
                score,

            "risk_level":
                level,

            "status":
                "NOW",

            "acq_date":
                acq_date,

            "acq_time":
                acq_time,

            "source":
                "NASA FIRMS"
        })

    # --------------------------------------------------------
    # Convert to DataFrame
    # --------------------------------------------------------

    events_df = pd.DataFrame(
        events
    )

    print(
        f"Fire events generated: "
        f"{len(events_df)}"
    )

    return events_df


# ============================================================
# 9. COMPLETE FIRMS PIPELINE
# ============================================================

def process_firms_data(df):

    print("\n")
    print("==========================================")
    print("      NASA FIRMS FIRE EVENT PROCESSOR")
    print("==========================================")

    print(
        f"\nRaw detections: {len(df)}"
    )

    # --------------------------------------------------------
    # STEP 1: CLEAN DATA
    # --------------------------------------------------------

    df = clean_firms_data(
        df
    )

    # --------------------------------------------------------
    # STEP 2: CLUSTER DETECTIONS
    # --------------------------------------------------------

    clustered_df = cluster_fire_detections(

        df,

        radius_km=CLUSTER_RADIUS_KM,

        min_samples=MIN_SAMPLES
    )

    # --------------------------------------------------------
    # STEP 3: CREATE FIRE EVENTS
    # --------------------------------------------------------

    events = create_fire_events(
        clustered_df
    )

    return (
        clustered_df,
        events
    )


# ============================================================
# 10. TEST WITH NASA FIRMS DATA
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # These are actual FIRMS-style detections from the data
    # you provided.
    #
    # These five detections are geographically close and
    # should be grouped into a cluster.
    # --------------------------------------------------------

    data = [

        {
            "latitude": 20.57731,
            "longitude": -101.17217,
            "confidence": "h",
            "brightness": 367,
            "brightness_day": 287.47,
            "acq_date": "2026-08-19",
            "acq_time": "915"
        },

        {
            "latitude": 20.58106,
            "longitude": -101.16315,
            "confidence": "n",
            "brightness": 295.79,
            "brightness_day": 283.52,
            "acq_date": "2026-08-19",
            "acq_time": "915"
        },

        {
            "latitude": 20.58275,
            "longitude": -101.17079,
            "confidence": "n",
            "brightness": 312.14,
            "brightness_day": 284.49,
            "acq_date": "2026-08-19",
            "acq_time": "915"
        },

        {
            "latitude": 20.58360,
            "longitude": -101.17461,
            "confidence": "n",
            "brightness": 298.51,
            "brightness_day": 286.20,
            "acq_date": "2026-08-19",
            "acq_time": "915"
        },

        {
            "latitude": 20.57646,
            "longitude": -101.16833,
            "confidence": "n",
            "brightness": 317.39,
            "brightness_day": 283.77,
            "acq_date": "2026-08-19",
            "acq_time": "915"
        }
    ]

    # --------------------------------------------------------
    # Convert list into DataFrame
    # --------------------------------------------------------

    df = pd.DataFrame(
        data
    )

    # --------------------------------------------------------
    # Run complete pipeline
    # --------------------------------------------------------

    clustered_df, events = process_firms_data(
        df
    )

    # ========================================================
    # DISPLAY CLUSTERED DETECTIONS
    # ========================================================

    print("\n")
    print("==========================================")
    print("        CLUSTERED FIRMS DETECTIONS")
    print("==========================================")

    if not clustered_df.empty:

        print(
            clustered_df[
                [
                    "latitude",
                    "longitude",
                    "brightness",
                    "confidence",
                    "cluster_id"
                ]
            ].to_string(
                index=False
            )
        )

    # ========================================================
    # DISPLAY FINAL FIRE EVENTS
    # ========================================================

    print("\n")
    print("==========================================")
    print("             FIRE EVENTS")
    print("==========================================")

    if not events.empty:

        print(
            events[
                [
                    "fire_event_id",
                    "latitude",
                    "longitude",
                    "detections",
                    "max_brightness",
                    "average_brightness",
                    "confidence",
                    "risk_score",
                    "risk_level",
                    "status",
                    "source"
                ]
            ].to_string(
                index=False
            )
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n")
    print("==========================================")
    print("                 SUMMARY")
    print("==========================================")

    print(
        f"Raw detections     : {len(df)}"
    )

    print(
        f"Valid detections   : {len(clustered_df)}"
    )

    print(
        f"Fire clusters      : "
        f"{clustered_df['cluster_id'].nunique()}"
    )

    print(
        f"Fire events        : {len(events)}"
    )

    if not events.empty:

        print("\nRisk distribution:")

        print(
            events[
                "risk_level"
            ].value_counts()
            .to_string()
        )

    print("\n==========================================")
    print("          PROCESSING COMPLETE")
    print("==========================================")