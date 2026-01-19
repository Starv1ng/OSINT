import re
from typing import Dict, Any


class EmailExtractorMEI:
    """Extract emails from raw HTML/text."""

    def is_enabled(self) -> bool:
        return True

    def get_priority(self) -> int:
        return 50

    def search(self, raw_text: str, content_type: str, search_data: Dict[str, Any]) -> Dict[str, Any]:
        # Find emails using a permissive regex
        emails = set(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", raw_text))
        findings = [{"type": "email", "value": e} for e in emails]
        return {"findings": findings}
