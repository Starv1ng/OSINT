import re
from typing import Dict, Any


class UsernameExtractorMEI:
    """Extract social-style usernames (e.g., @user) from raw HTML/text."""

    def is_enabled(self) -> bool:
        return True

    def get_priority(self) -> int:
        return 70

    def search(self, raw_text: str, content_type: str, search_data: Dict[str, Any]) -> Dict[str, Any]:
        usernames = set(re.findall(r"@([A-Za-z0-9_]{2,30})", raw_text))
        findings = [{"type": "username", "value": u} for u in usernames]
        return {"findings": findings}
