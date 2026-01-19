import re
from typing import Dict, Any


class PhoneExtractorMEI:
    """Extract phone-like strings from raw HTML/text."""

    def is_enabled(self) -> bool:
        return True

    def get_priority(self) -> int:
        return 60

    def search(self, raw_text: str, content_type: str, search_data: Dict[str, Any]) -> Dict[str, Any]:
        # Very permissive phone pattern (international-ish)
        phones = set(re.findall(r"(\+?\d[\d\-\.\s\(\)]{6,}\d)", raw_text))
        cleaned = {p.strip() for p in phones}
        findings = [{"type": "phone", "value": p} for p in cleaned]
        return {"findings": findings}
