"""
Knowledge Vault — Abstract chunker with section-aware splitting.

Handles both structured PubMed abstracts (with section headers like
BACKGROUND/METHODS/RESULTS/CONCLUSIONS) and unstructured abstracts.
"""

import re

# Section header patterns for structured PubMed abstracts
SECTION_RE = re.compile(
    r'(?:^|\n)\s*'
    r'(BACKGROUND|INTRODUCTION|CONTEXT|'
    r'METHODS?|MATERIALS?\s+AND\s+METHODS?|MATERIALS?\s*&\s*METHODS?|EXPERIMENTAL|'
    r'RESULTS?|FINDINGS|'
    r'CONCLUSIONS?|DISCUSSION|SUMMARY|SIGNIFICANCE)'
    r'\s*[:\.\-]\s*',
    re.IGNORECASE
)

SECTION_MAP = {
    'BACKGROUND': 'background',
    'INTRODUCTION': 'background',
    'CONTEXT': 'background',
    'METHOD': 'methods',
    'METHODS': 'methods',
    'MATERIALS AND METHODS': 'methods',
    'MATERIALS & METHODS': 'methods',
    'MATERIALS AND METHOD': 'methods',
    'MATERIAL AND METHODS': 'methods',
    'EXPERIMENTAL': 'methods',
    'RESULT': 'results',
    'RESULTS': 'results',
    'FINDINGS': 'results',
    'CONCLUSION': 'conclusions',
    'CONCLUSIONS': 'conclusions',
    'DISCUSSION': 'conclusions',
    'SUMMARY': 'conclusions',
    'SIGNIFICANCE': 'conclusions',
}


def _normalize_section(header: str) -> str:
    """Map a raw section header to a normalized section name."""
    key = re.sub(r'\s+', ' ', header.strip().upper())
    return SECTION_MAP.get(key, 'full')


def _token_count(text: str) -> int:
    """Approximate token count using whitespace splitting."""
    return len(text.split())


def chunk_abstract(abstract_text: str) -> list[dict]:
    """Parse abstract into section-aware chunks.

    Returns list of dicts: {"section": str, "text": str, "token_count": int}

    For structured abstracts (with section headers), splits into sections.
    For unstructured (99.7% of data), returns single chunk with section="full".
    """
    if not abstract_text or len(abstract_text.strip()) < 20:
        return []

    text = abstract_text.strip()

    # Find all section header matches
    matches = list(SECTION_RE.finditer(text))

    if len(matches) < 2:
        # Unstructured abstract — return as single chunk
        return [{
            "section": "full",
            "text": text,
            "token_count": _token_count(text),
        }]

    # Structured abstract — split into sections
    sections: dict[str, list[str]] = {}

    # Text before first section header (if any)
    preamble = text[:matches[0].start()].strip()
    if preamble:
        sections.setdefault('background', []).append(preamble)

    # Extract each section
    for i, match in enumerate(matches):
        header = match.group(1)
        section_name = _normalize_section(header)

        # Section text runs from end of this header to start of next header (or end of text)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()

        if section_text:
            sections.setdefault(section_name, []).append(section_text)

    # Build chunk list — concatenate multiple texts for same section
    chunks = []
    for section_name, texts in sections.items():
        combined = ' '.join(texts)
        if combined.strip():
            chunks.append({
                "section": section_name,
                "text": combined.strip(),
                "token_count": _token_count(combined),
            })

    return chunks if chunks else [{
        "section": "full",
        "text": text,
        "token_count": _token_count(text),
    }]
