"""Social Signal Radar (FR-3, REQ §10.5): PII masking, gazetteer geocoding, TF-IDF + logistic regression classifier.

The labelled corpus and demo feed are synthetic (template posts); real text comes in through manual upload.
"""
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.pipeline import make_pipeline

from .zones import ZONES

CATEGORIES = ["ROUTE_BLOCKED", "TOO_CROWDED", "NO_DUSTBIN", "MEDICAL_HELP_NEEDED", "TRAFFIC_SLOW", "POSITIVE_EVENT", "OTHER"]
SIGNALS_LABEL = "synthetic social signals (template posts) unless uploaded"

# FR-3.3 gazetteer: lower-case landmark -> zone. shortcut: hand-picked names, extend from OSM place names.
GAZETTEER = {
    "shaniwar wada": "Z01", "budhwar peth": "Z01", "dagdusheth": "Z01", "kasba peth": "Z01", "mandai": "Z01",
    "laxmi road": "Z02", "tilak road": "Z02", "belbaug chowk": "Z02", "alka chowk": "Z02",
    "fc road": "Z03", "fergusson": "Z03", "deccan": "Z03", "jm road": "Z03",
    "ghat": "Z04", "mutha river": "Z04", "omkareshwar": "Z04", "riverfront": "Z04",
    "sangam bridge": "Z05", "sangam": "Z05", "wellesley bridge": "Z05",
    "camp": "Z06", "mg road": "Z06", "east street": "Z06",
    "kothrud": "Z07", "karve road": "Z07", "paud road": "Z07",
    "hadapsar": "Z08", "magarpatta": "Z08",
    "swargate": "Z09", "katraj": "Z09",
    "pune station": "Z10", "sadhu vaswani": "Z10", "railway station": "Z10",
}
_PLACES = sorted(GAZETTEER, key=len, reverse=True)  # longest match first: "sangam bridge" before "sangam"

_PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"), (re.compile(r"https?://\S+"), "[url]"),
        (re.compile(r"@\w+"), "[user]"), (re.compile(r"(?:\+91[\s-]?)?\b\d[\d\s-]{8,}\d\b"), "[phone]")]


def mask_pii(text):
    """FR-3.5: mask emails, URLs, handles and phone numbers before anything is stored."""
    for rx, sub in _PII:
        text = rx.sub(sub, text)
    return text


def geocode(text):
    t = text.lower()
    return next((GAZETTEER[p] for p in _PLACES if re.search(rf"\b{re.escape(p)}\b", t)), None)


TEMPLATES = {
    "ROUTE_BLOCKED": ["road closed near {p}, barricades everywhere", "{p} route blocked by police, no entry",
                      "cannot pass {p}, the road is shut", "procession stopped at {p}, way completely blocked",
                      "diversion at {p}, lane is closed till night"],
    "TOO_CROWDED": ["huge crowd at {p}, can't even move", "{p} is packed, too many people", "so much rush near {p} right now",
                    "stampede like situation at {p}, very crowded", "{p} jam packed with devotees, avoid"],
    "NO_DUSTBIN": ["garbage piling up at {p}, no dustbins", "no bins anywhere near {p}, plastic everywhere",
                   "{p} is filthy, waste not collected", "need more dustbins at {p}", "litter and flowers dumped all over {p}"],
    "MEDICAL_HELP_NEEDED": ["someone fainted at {p}, need ambulance", "medical help needed near {p} urgently",
                            "old man collapsed at {p}, call doctor", "injury at {p}, first aid required",
                            "ambulance stuck near {p}, patient needs help"],
    "TRAFFIC_SLOW": ["traffic crawling at {p}", "{p} bumper to bumper, 40 minutes for 1 km", "heavy traffic jam near {p}",
                     "vehicles not moving on {p}", "slow traffic all the way to {p}"],
    "POSITIVE_EVENT": ["beautiful procession at {p}, great vibes", "dhol tasha at {p} was amazing",
                       "well managed crowd at {p}, thanks police", "lovely decorations near {p}", "{p} visarjan was so peaceful"],
    "OTHER": ["anyone know the timings at {p}?", "lost my umbrella near {p}", "parking info for {p}?",
              "going to {p} tomorrow", "which bus goes to {p}"],
}


def synthetic_posts(n, seed, weights=None):
    """Template posts with a landmark, optional contact noise (masked on ingest) and the true zone/category."""
    rng = np.random.default_rng(seed)
    names = list(GAZETTEER)
    zw = np.array([weights.get(GAZETTEER[p], 1.0) for p in names]) if weights else np.ones(len(names))
    out = []
    for _ in range(n):
        cat = CATEGORIES[rng.integers(len(CATEGORIES))]
        place = names[rng.choice(len(names), p=zw / zw.sum())]
        text = TEMPLATES[cat][rng.integers(5)].format(p=place.title())
        if rng.random() < 0.15:
            text += f" call 98{rng.integers(10**7, 10**8)}"
        out.append({"text": text, "category": cat, "zone_id": GAZETTEER[place]})
    return out


def train_classifier(n=700, test=300):
    """REQ §10.5 baseline; evaluated per category on a held-out set of `test` labelled items."""
    posts = synthetic_posts(n, seed=11)
    tr, te = posts[:-test], posts[-test:]
    clf = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=1), LogisticRegression(max_iter=1000))
    clf.fit([mask_pii(p["text"]) for p in tr], [p["category"] for p in tr])
    pred = clf.predict([mask_pii(p["text"]) for p in te])
    prec, rec, f1, sup = precision_recall_fscore_support([p["category"] for p in te], pred, labels=CATEGORIES, zero_division=0)
    metrics = {c: {"precision": round(float(p), 3), "recall": round(float(r), 3), "f1": round(float(f), 3), "n": int(s)}
               for c, p, r, f, s in zip(CATEGORIES, prec, rec, f1, sup)}
    return clf, metrics


def ingest(clf, texts):
    """Mask, geocode and classify; only the masked text, zone and category are kept."""
    masked = [mask_pii(t)[:280] for t in texts]
    cats = clf.predict(masked) if masked else []
    return [{"zone_id": geocode(m), "category": c, "text": m} for m, c in zip(masked, cats)]


def demo_feed(clf):
    # posts more likely where more people are; shortcut: synthetic, replace with RSS / permitted API ingest
    weights = {z["zone_id"]: z["capacity_persons"] / 10000 for z in ZONES}
    return ingest(clf, [p["text"] for p in synthetic_posts(400, seed=23, weights=weights)])
