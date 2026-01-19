import re
from typing import Dict, Any


class ImageExtractorMEI:
    """Extract image URLs from raw HTML/text."""

    def is_enabled(self) -> bool:
        return True

    def get_priority(self) -> int:
        return 80

    def search(self, raw_text: str, content_type: str, search_data: Dict[str, Any]) -> Dict[str, Any]:
        imgs = set(re.findall(r"https?://[^\s'\"]+\.(?:png|jpg|jpeg|gif|bmp)", raw_text, re.IGNORECASE))
        findings = [{"type": "image", "value": u} for u in imgs]
        return {"findings": findings}
