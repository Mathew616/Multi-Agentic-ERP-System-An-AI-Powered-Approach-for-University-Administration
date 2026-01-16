import re
from datetime import datetime

class ValidatorAgent:
    def __init__(self):
        print("[Validator Agent] Initialized ✅")

    def validate_field(self, key, value):
        """Individual field validation logic"""
        if not value or (isinstance(value, str) and not value.strip()):
            return f"Missing {key}"

        if key == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except Exception:
                return "Invalid date format (expected YYYY-MM-DD)"

        if key == "department" and len(value) < 2:
            return "Invalid department name"

        if key == "category" and len(value) < 3:
            return "Invalid category"

        if key == "event_name" and len(value.split()) < 3:
            return "Event name too short"

        return None

    def process(self, data):
        """Validate all event details before saving"""
        event = data.get("event", {})
        entities = data.get("entities", {})

        errors = []

        # ✅ Core fields (must be present)
        required_fields = ["event_name", "department", "category", "date"]
        for field in required_fields:
            err = self.validate_field(field, event.get(field))
            if err:
                errors.append(err)

        # ✅ Optional fields — warn if missing, but don't block validation
        optional_fields = ["venue", "organizer", "abstract"]
        for field in optional_fields:
            val = entities.get(field)
            if not val:
                print(f"[Validator] ⚠ Optional field '{field}' missing (not blocking).")

        # Determine overall status
        status = "ok" if not errors else "needs_review"

        return {
            "status": status,
            "errors": errors,
            "validated_fields": event,
            "missing": [e for e in errors if "Missing" in e],
        }
