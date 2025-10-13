#query.py

import sqlite3
import difflib
import logging

logger = logging.getLogger("rag_api")

def normalize(text: str) -> str:
    return text.strip().lower()

def query_entries(vendor, model, os_version, feature, db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    vendor = normalize(vendor)
    model = normalize(model)
    os_version = normalize(os_version)
    feature_input = normalize(feature)

    logger.info(f"Querying CLI examples for vendor='{vendor}', model='{model}', os_version='{os_version}', feature='{feature_input}'")

    cursor.execute("""
        SELECT * FROM cli_library
        WHERE lower(vendor) = ? AND lower(model) = ? AND lower(os_version) = ? AND lower(feature) = ?
    """, (vendor, model, os_version, feature_input))
    results = cursor.fetchall()

    if results:
        conn.close()
        return results

    # Fuzzy matching fallback
    cursor.execute("SELECT DISTINCT vendor FROM cli_library")
    vendors = [row[0].lower() for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT model FROM cli_library")
    models = [row[0].lower() for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT os_version FROM cli_library")
    os_versions = [row[0].lower() for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT feature FROM cli_library")
    features = [row[0] for row in cursor.fetchall()]

    best_vendor = difflib.get_close_matches(vendor, vendors, n=1)
    best_model = difflib.get_close_matches(model, models, n=1)
    best_os_version = difflib.get_close_matches(os_version, os_versions, n=1)

    feature_map = {f: f.split('_')[-1].lower() for f in features}
    stripped_features = list(feature_map.values())
    best_feature_match = difflib.get_close_matches(feature_input, stripped_features, n=1)

    best_feature = []
    if best_feature_match:
        for full, stripped in feature_map.items():
            if stripped == best_feature_match[0]:
                best_feature = [full]
                break

    logger.info("Fuzzy match candidates:")
    logger.info(f"Vendor match: {best_vendor}")
    logger.info(f"Model match: {best_model}")
    logger.info(f"OS version match: {best_os_version}")
    logger.info(f"Feature match: {best_feature}")

    if best_vendor and best_model and best_os_version and best_feature:
        fuzzy_vendor = best_vendor[0]
        fuzzy_model = best_model[0]
        fuzzy_os_version = best_os_version[0]
        fuzzy_feature = best_feature[0]
        cursor.execute("""
            SELECT * FROM cli_library
            WHERE lower(vendor) = ? AND lower(model) = ? AND lower(os_version) = ? AND feature = ?
        """, (fuzzy_vendor, fuzzy_model, fuzzy_os_version, fuzzy_feature))
        results = cursor.fetchall()

    if not results and best_vendor and best_feature:
        fuzzy_vendor = best_vendor[0]
        fuzzy_feature = best_feature[0]
        cursor.execute("""
            SELECT * FROM cli_library
            WHERE lower(vendor) = ? AND feature LIKE ?
        """, (fuzzy_vendor, f"%{fuzzy_feature}%"))
        results = cursor.fetchall()

    if not results and best_feature:
        fuzzy_feature = best_feature[0]
        cursor.execute("""
            SELECT * FROM cli_library
            WHERE feature LIKE ?
        """, (f"%{fuzzy_feature}%",))
        results = cursor.fetchall()

    conn.close()
    return results
    
    
from utils.database import score_feedback

def score_feedback(status):
    return {
        "pushed": 3,
        "pending": 2,
        "rejected": 1,
        "error": 0
    }.get(status, 0)

def query_weighted_entries(vendor, model, os_version, feature, db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sq.*, fl.status
        FROM staging_queue sq
        LEFT JOIN feedback_log fl ON sq.id = fl.request_id
        WHERE lower(sq.vendor) = ? AND lower(sq.model) = ? AND lower(sq.os_version) = ? AND lower(sq.feature) = ?
    """, (normalize(vendor), normalize(model), normalize(os_version), normalize(feature)))
    results = cursor.fetchall()
    conn.close()
    scored = sorted(results, key=lambda r: score_feedback(r[-1]), reverse=True)
    return scored