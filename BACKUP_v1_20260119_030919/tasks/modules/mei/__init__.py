"""MEI (Module Extractor of Indicators) package

Contains lightweight extractor modules that take raw HTML/text and
return structured indicators (emails, phones, usernames, images).
These are simple, best-effort implementations and can be replaced
with more advanced ML or parser-based extractors later.
"""

__all__ = [
    "email_extractor",
    "phone_extractor",
    "username_extractor",
    "image_extractor",
]
