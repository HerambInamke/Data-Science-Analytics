"""Zone register for Pune Ganesh Visarjan (REQ §5).

Centroids and attributes are approximate and hand-curated; they must be checked
against PMC / police announcements before any demo that claims accuracy.
"""
import math

# proc_start / peak: hour index on the event timeline (0 = 06:00, 23 = 05:00 next day)
ZONES = [
    dict(zone_id="Z01", name="Central Pune (Shaniwar Wada / Budhwar Peth)", zone_type="market", lat=18.5190, lon=73.8560,
         capacity_persons=60000, proc_start=4, peak=14, immersion_dist_km=0.8, shop_density=0.9, stalls=120, waste_points=4, toilets=10),
    dict(zone_id="Z02", name="Laxmi Road / Tilak Road corridor", zone_type="market", lat=18.5110, lon=73.8510,
         capacity_persons=80000, proc_start=4, peak=15, immersion_dist_km=1.5, shop_density=1.0, stalls=150, waste_points=5, toilets=12),
    dict(zone_id="Z03", name="FC Road / Deccan", zone_type="market", lat=18.5200, lon=73.8410,
         capacity_persons=40000, proc_start=6, peak=15, immersion_dist_km=1.2, shop_density=0.7, stalls=80, waste_points=3, toilets=8),
    dict(zone_id="Z04", name="Mula-Mutha riverfront ghats", zone_type="ghat", lat=18.5250, lon=73.8490,
         capacity_persons=50000, proc_start=8, peak=16, immersion_dist_km=0.1, shop_density=0.3, stalls=60, waste_points=3, toilets=8),
    dict(zone_id="Z05", name="Sangam Bridge area", zone_type="ghat", lat=18.5300, lon=73.8580,
         capacity_persons=35000, proc_start=8, peak=17, immersion_dist_km=0.1, shop_density=0.2, stalls=40, waste_points=2, toilets=6),
    dict(zone_id="Z06", name="Camp / MG Road market", zone_type="market", lat=18.5155, lon=73.8790,
         capacity_persons=30000, proc_start=6, peak=13, immersion_dist_km=2.5, shop_density=0.8, stalls=70, waste_points=3, toilets=6),
    dict(zone_id="Z07", name="Kothrud / Karve Road corridor", zone_type="residential", lat=18.5050, lon=73.8150,
         capacity_persons=25000, proc_start=5, peak=12, immersion_dist_km=1.8, shop_density=0.5, stalls=40, waste_points=3, toilets=5),
    dict(zone_id="Z08", name="Hadapsar / Magarpatta corridor", zone_type="residential", lat=18.5100, lon=73.9250,
         capacity_persons=25000, proc_start=5, peak=12, immersion_dist_km=2.0, shop_density=0.4, stalls=35, waste_points=3, toilets=5),
    dict(zone_id="Z09", name="Swargate / Katraj approach roads", zone_type="transit", lat=18.4900, lon=73.8600,
         capacity_persons=30000, proc_start=4, peak=13, immersion_dist_km=3.0, shop_density=0.5, stalls=45, waste_points=2, toilets=5),
    dict(zone_id="Z10", name="Pune Station / Sadhu Vaswani", zone_type="transit", lat=18.5285, lon=73.8740,
         capacity_persons=30000, proc_start=4, peak=14, immersion_dist_km=1.6, shop_density=0.5, stalls=40, waste_points=2, toilets=5),
]
ZONE_BY_ID = {z["zone_id"]: z for z in ZONES}
ZONE_TYPES = ["market", "ghat", "residential", "transit"]


def _km(a, b):
    return math.hypot((a["lat"] - b["lat"]) * 111, (a["lon"] - b["lon"]) * 105)


def neighbours(zone_id, k=2):
    z = ZONE_BY_ID[zone_id]
    return sorted((o["zone_id"] for o in ZONES if o["zone_id"] != zone_id), key=lambda i: _km(z, ZONE_BY_ID[i]))[:k]


def geojson():
    # shortcut: hexagons around centroids stand in for real zone boundaries; replace with PMC ward/OSM polygons.
    feats = []
    for z in ZONES:
        r = 0.0045
        ring = [[z["lon"] + r * math.cos(math.radians(a)), z["lat"] + r * math.sin(math.radians(a))] for a in range(0, 361, 60)]
        props = {k: v for k, v in z.items() if k not in ("lat", "lon")}
        feats.append({"type": "Feature", "id": int(z["zone_id"][1:]), "properties": props,
                      "geometry": {"type": "Polygon", "coordinates": [ring]}})
    return {"type": "FeatureCollection", "features": feats}
