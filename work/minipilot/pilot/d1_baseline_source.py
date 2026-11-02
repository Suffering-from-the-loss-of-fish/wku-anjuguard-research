"""Unmodified method snapshot from AnjuGuard.
Source: services/backend/app/assessment_service.py
Commit: df281277215a1b55fd74dc8e43203e3954081976
Original complete source SHA256: 800f60cb80f0e3457f06c8d9bb501cbff2cd595f4cf21d9eeb76c70d7c0b9431
Attribution and license: see distribution THIRD_PARTY_NOTICES.
Only the two original methods are included; method bodies are unchanged.
"""

class AssessmentService:
    def _merge_cross_frame_candidates(self, candidates: list[dict], media: list[dict]) -> list[dict]:
        """Conservatively merge the same risk across adjacent frames from one source."""
        media_by_id = {item["media_id"]: item for item in media}
        merged: list[dict] = []
        for candidate in sorted(candidates, key=lambda item: float(item.get("confidence", 0)), reverse=True):
            candidate = dict(candidate)
            candidate["evidence_media_ids"] = [candidate["media_id"]]
            match = next((item for item in merged if self._same_physical_risk(item, candidate, media_by_id)), None)
            if match is None:
                merged.append(candidate)
                continue
            match["evidence_media_ids"].append(candidate["media_id"])
            if candidate["evidence"] not in match["evidence"]:
                match["evidence"] = f"{match['evidence']}；另一个画面也观察到相同位置的候选"[:240]
        return merged

    @staticmethod
    def _same_physical_risk(left: dict, right: dict, media_by_id: dict[str, dict]) -> bool:
        if left["risk_code"] != right["risk_code"]:
            return False
        left_media = media_by_id.get(left["media_id"], {})
        right_media = media_by_id.get(right["media_id"], {})
        source_id = left_media.get("source_id")
        if not source_id or source_id != right_media.get("source_id"):
            return False
        left_time, right_time = left_media.get("captured_at_ms"), right_media.get("captured_at_ms")
        if isinstance(left_time, int) and isinstance(right_time, int) and abs(left_time - right_time) > 8_000:
            return False
        left_region, right_region = left.get("region"), right.get("region")
        if not left_region or not right_region or left_region.get("type") != "bbox" or right_region.get("type") != "bbox":
            return False
        x1, y1 = max(left_region["x"], right_region["x"]), max(left_region["y"], right_region["y"])
        x2 = min(left_region["x"] + left_region["width"], right_region["x"] + right_region["width"])
        y2 = min(left_region["y"] + left_region["height"], right_region["y"] + right_region["height"])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        union = left_region["width"] * left_region["height"] + right_region["width"] * right_region["height"] - intersection
        return union > 0 and intersection / union >= 0.35

