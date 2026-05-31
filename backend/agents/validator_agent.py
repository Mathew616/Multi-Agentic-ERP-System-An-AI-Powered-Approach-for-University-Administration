# backend/agents/validator_agent.py
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional

"""
ValidatorAgent — simple, robust validation for extracted event data.

Improvements:
- Accepts date strings or date objects
- Validates doc_type (Certificate/Report) with default
- Returns normalized fields and separates errors vs warnings
"""

ALLOWED_DOC_TYPES = {"Report", "Certificate"}
DEFAULT_DOC_TYPE = "Report"


class ValidatorAgent:
    def __init__(self):
        print("[Validator Agent] Initialized ✅")

    def _is_blank(self, v: Any) -> bool:
        return v is None or (isinstance(v, str) and not v.strip())

    def _normalize_str(self, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    def validate_field(self, key: str, value: Any) -> Optional[str]:
        """Return error message string or None if valid."""
        if self._is_blank(value):
            return f"Missing {key}"

        if key == "date":
            # Accept date object or ISO string
            if isinstance(value, (datetime, date)):
                return None
            if isinstance(value, str):
                try:
                    # allow fuzzy parsing but require resulting date
                    parsed = datetime.fromisoformat(value)
                    return None
                except Exception:
                    try:
                        from dateutil import parser as dateparser
                        dateparser.parse(value, fuzzy=True)
                        return None
                    except Exception:
                        return "Invalid date format (expected YYYY-MM-DD or parsable date)"
            return "Invalid date type"

        if key == "department":
            v = self._normalize_str(value)
            if len(v) < 2:
                return "Invalid department name"

        if key == "category":
            v = self._normalize_str(value)
            if len(v) < 3:
                return "Invalid category"

        if key == "event_name":
            v = self._normalize_str(value)
            # allow short event names for certificates, but warn if extremely short
            if len(v.split()) < 2:
                return "Event name too short"

        if key == "doc_type":
            v = self._normalize_str(value).title()
            if v not in ALLOWED_DOC_TYPES:
                return f"Invalid doc_type (expected one of {sorted(ALLOWED_DOC_TYPES)})"

        return None

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the event payload.
        Input shape:
            { "event": {...}, "entities": {...} }

        Returns:
            {
              status: "ok" | "needs_review",
              errors: [ {field, message} ],
              warnings: [ {field, message} ],
              validated_fields: {... normalized ...},
              missing: [...]
            }
        """
        event = data.get("event", {}) or {}
        entities = data.get("entities", {}) or {}

        errors: List[Dict[str, str]] = []
        warnings: List[Dict[str, str]] = []

        # Ensure keys exist and normalize
        fields = {
            "event_name": self._normalize_str(event.get("event_name") or entities.get("event_name")),
            "department": self._normalize_str(event.get("department") or entities.get("department")),
            "category": self._normalize_str(event.get("category") or entities.get("category")),
            "date": event.get("date") or entities.get("date"),
            "venue": self._normalize_str(event.get("venue") or entities.get("venue")),
            "organizer": self._normalize_str(event.get("organizer") or entities.get("organizer")),
            "abstract": self._normalize_str(event.get("abstract") or entities.get("abstract")),
            "doc_type": self._normalize_str(event.get("doc_type") or entities.get("doc_type") or DEFAULT_DOC_TYPE)
        }

        # Required fields validation
        required_fields = ["event_name", "department", "category", "date"]
        for f in required_fields:
            msg = self.validate_field(f, fields.get(f))
            if msg:
                errors.append({"field": f, "message": msg})

        # Validate doc_type but treat as error if invalid (since you rely on it)
        dt_msg = self.validate_field("doc_type", fields.get("doc_type"))
        if dt_msg:
            errors.append({"field": "doc_type", "message": dt_msg})
        else:
            # normalize doc_type value
            fields["doc_type"] = fields["doc_type"].title()

        # Optional fields — warn if missing but not blocking
        optional_fields = ["venue", "organizer", "abstract"]
        for f in optional_fields:
            val = fields.get(f)
            if self._is_blank(val):
                warnings.append({"field": f, "message": f"Optional field '{f}' missing"})

        # Post-process date into ISO if possible
        date_val = fields.get("date")
        normalized_date = None
        if isinstance(date_val, (datetime, date)):
            normalized_date = date_val.date().isoformat() if isinstance(date_val, datetime) else date_val.isoformat()
            fields["date"] = normalized_date
        elif isinstance(date_val, str):
            try:
                # try strict ISO first
                normalized_date = datetime.fromisoformat(date_val).date().isoformat()
                fields["date"] = normalized_date
            except Exception:
                try:
                    from dateutil import parser as dateparser
                    normalized_date = dateparser.parse(date_val, fuzzy=True).date().isoformat()
                    fields["date"] = normalized_date
                except Exception:
                    # keep original string; validation above will have flagged it
                    fields["date"] = date_val

        status = "ok" if not errors else "needs_review"

        return {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "validated_fields": fields,
            "missing": [e["field"] for e in errors if "Missing" in e["message"]],
        }
