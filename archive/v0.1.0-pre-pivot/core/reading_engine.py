"""
core/reading_engine.py

Context-driven reading recommendations for both tracks.
BUSINESS TRACK: APQC PCF -> best practice reading
SCIENTIFIC TRACK: TE/biofab literature + ChromaDB similarity
"""

import json
from pathlib import Path
from types import SimpleNamespace


class ReadingEngine:

    def __init__(self):
        self.apqc = self._load_json("data/knowledge/apqc_pcf_biofab.json")
        self.te_reading = self._load_json("data/knowledge/te_biofab_reading.json")
        self._signal_index = self._build_signal_index()
        self._topic_index = self._build_topic_index()

    def _load_json(self, path):
        p = Path(path)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {}

    def _build_signal_index(self):
        """Build {pi_signal: [process_elements]} index."""
        index = {}
        for cat in self.apqc.get("categories", []):
            for subcat in cat.get("subcategories", []):
                for pe in subcat.get("process_elements", []):
                    for signal in pe.get("pi_signals", []):
                        index.setdefault(signal, []).append({
                            "process_element": pe,
                            "subcategory": subcat["name"],
                            "category": cat["name"],
                            "pcf_id": pe["id"],
                        })
        return index

    def _build_topic_index(self):
        """Build {topic: [reading_entries]} from TE/biofab DB."""
        index = {}
        for collection in self.te_reading.get("collections", []):
            for entry in collection.get("entries", []):
                for topic in entry.get("topics", []):
                    index.setdefault(topic, []).append({
                        **entry,
                        "collection": collection["name"],
                    })
        return index

    def get_business_reading(self, pi_signals, company_context=None,
                             max_results=5):
        """
        Given PI signals, return ranked APQC-mapped best practice reading.
        """
        results = {}

        for signal in (pi_signals or []):
            for match in self._signal_index.get(signal, []):
                pe = match["process_element"]
                pe_id = pe["id"]

                if pe_id not in results:
                    results[pe_id] = {
                        "pcf_id": pe_id,
                        "pcf_name": pe["name"],
                        "pcf_category": match["category"],
                        "pcf_subcategory": match["subcategory"],
                        "stromalytix_mapping": pe.get("stromalytix_mapping"),
                        "best_practice_summary": pe.get("best_practice_summary", ""),
                        "key_metrics": pe.get("key_metrics", []),
                        "reading": pe.get("reading", []),
                        "triggered_by": [signal],
                        "relevance_score": 1.0,
                    }
                else:
                    results[pe_id]["triggered_by"].append(signal)
                    results[pe_id]["relevance_score"] += 0.5

        ranked = sorted(results.values(),
                        key=lambda x: x["relevance_score"], reverse=True)
        return ranked[:max_results]

    def get_scientific_reading(self, profile=None, variance_report=None,
                               level_filter=None, max_results=8):
        """
        Given construct profile, return relevant TE/biofab reading.
        """
        scores = {}
        profile = profile or SimpleNamespace()

        method_map = {
            "bioprinting": "bioprinting",
            "organ_on_chip": "organ_on_chip",
            "ooc": "organ_on_chip",
            "organoid": "organoids",
            "acoustic_aggregation": "acoustic_aggregation",
            "acoustic": "acoustic_aggregation",
            "scaffold_free": "scaffold_free",
        }

        method = getattr(profile, "biofab_method", None)
        if method:
            coll_id = method_map.get(method)
            for coll in self.te_reading.get("collections", []):
                if coll["id"] == coll_id:
                    for entry in coll["entries"]:
                        eid = entry["id"]
                        scores.setdefault(eid, {
                            "entry": entry, "collection": coll["name"],
                            "match_reasons": [], "relevance_score": 0.0,
                        })
                        scores[eid]["relevance_score"] += 2.0
                        scores[eid]["match_reasons"].append(
                            f"matches biofab method: {method}")

        # Always include foundations
        for coll in self.te_reading.get("collections", []):
            if coll["id"] == "foundations":
                for entry in coll["entries"]:
                    eid = entry["id"]
                    scores.setdefault(eid, {
                        "entry": entry, "collection": coll["name"],
                        "match_reasons": [], "relevance_score": 0.0,
                    })
                    scores[eid]["relevance_score"] += 0.5
                    scores[eid]["match_reasons"].append("foundational reference")

        # Topic matching from profile keywords
        tissue = getattr(profile, "target_tissue", "") or ""
        scaffold = getattr(profile, "scaffold_material", "") or ""
        combined = f"{tissue} {scaffold}".lower()

        keyword_topics = {
            "vascular": "vascularization",
            "gelma": "gelma",
            "matrigel": "matrigel",
            "shear": "shear_stress",
            "tumor": "tumor_model",
            "cardiac": "mechanosensing",
            "stiffness": "stiffness",
        }

        for kw, topic in keyword_topics.items():
            if kw in combined:
                for entry_info in self._topic_index.get(topic, []):
                    eid = entry_info["id"]
                    scores.setdefault(eid, {
                        "entry": entry_info, "collection": entry_info.get("collection", ""),
                        "match_reasons": [], "relevance_score": 0.0,
                    })
                    scores[eid]["relevance_score"] += 1.0
                    scores[eid]["match_reasons"].append(f"keyword: {kw}")

        if level_filter:
            scores = {k: v for k, v in scores.items()
                      if v["entry"].get("level") in level_filter}

        ranked = sorted(scores.values(),
                        key=lambda x: x["relevance_score"], reverse=True)
        return ranked[:max_results]

    def get_contextual_reading(self, profile=None, pi_signals=None,
                                company_context=None, variance_report=None,
                                level_filter=None):
        """Master method: returns both tracks unified."""
        biz = self.get_business_reading(pi_signals or [], company_context)
        sci = self.get_scientific_reading(profile, variance_report, level_filter)

        signals_str = ", ".join(pi_signals or []) or "no active PI signals"
        method_str = getattr(profile, "biofab_method", "unknown") if profile else "unknown"

        return {
            "business_track": biz,
            "scientific_track": sci,
            "context_summary": (
                f"Business track triggered by: {signals_str}. "
                f"Scientific track matched to: {method_str} method."
            ),
            "total_results": len(biz) + len(sci),
        }

    def search(self, query, max_results=5):
        """Free-text search across both databases."""
        query_lower = query.lower()
        words = query_lower.split()
        results = []

        for coll in self.te_reading.get("collections", []):
            for entry in coll.get("entries", []):
                searchable = (
                    entry.get("title", "") + " " +
                    entry.get("note", "") + " " +
                    " ".join(entry.get("topics", []))
                ).lower()
                if any(w in searchable for w in words):
                    results.append({
                        "track": "scientific",
                        "entry": entry,
                        "collection": coll["name"],
                    })

        for cat in self.apqc.get("categories", []):
            for subcat in cat.get("subcategories", []):
                for pe in subcat.get("process_elements", []):
                    searchable = (
                        pe.get("name", "") + " " +
                        pe.get("best_practice_summary", "")
                    ).lower()
                    if any(w in searchable for w in words):
                        results.append({
                            "track": "business",
                            "pcf_id": pe["id"],
                            "name": pe["name"],
                            "summary": pe.get("best_practice_summary", ""),
                            "reading": pe.get("reading", []),
                        })

        return results[:max_results]
