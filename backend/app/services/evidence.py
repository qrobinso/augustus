"""Keep claim provenance inspectable without equating a citation with truth."""
import re
from urllib.parse import urlparse


def _plain(text):
    if not isinstance(text, str):
        return ''
    return re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', text).strip()


def _whitespace(text):
    return ' '.join(text.split())


def attribute_claims(answers, sources, host_name):
    """Only retain evidence URLs and exact excerpts present in retrieved material.

    Supported denotes traceable attribution, not entailment or fact verification.
    Missing excerpts remain unverified rather than inheriting a host's whole bibliography.
    """
    retrieved = {s['url']: s for s in sources if isinstance(s, dict) and isinstance(s.get('url'), str)
                 and urlparse(s['url']).scheme in ('http', 'https')}
    claims = []
    for qa in answers if isinstance(answers, list) else []:
        if not isinstance(qa, dict):
            continue
        answer = _plain(qa.get('answer'))
        if not answer:
            continue
        evidence, seen = [], set()
        refs = qa.get('evidence', [])
        for ref in refs if isinstance(refs, list) else []:
            if not isinstance(ref, dict) or not isinstance(ref.get('url'), str):
                continue
            source = retrieved.get(ref['url'])
            quote = ref.get('excerpt')
            if not source or not isinstance(quote, str) or not 12 <= len(quote.strip()) <= 1500:
                continue
            text = source.get('content') or source.get('snippet') or ''
            key = (ref['url'], quote.strip())
            if _whitespace(quote) not in _whitespace(text) or key in seen:
                continue
            seen.add(key)
            evidence.append({'url': ref['url'], 'title': source.get('title') or source.get('name') or ref['url'],
                             'excerpt': quote.strip()})
        claims.append({'text': answer[:4000], 'sources': evidence,
                       'attribution': 'supported' if evidence else 'unverified', 'found_by': [host_name]})
    return claims


def collect_claims(host_research):
    """Combine each story's claims, retaining distinct evidence from different hosts."""
    combined = {}
    for research in host_research or []:
        structured = getattr(research, 'claims_by_story_index', {})
        for idx, facts in research.facts_by_story_index.items():
            claims = structured.get(idx)
            if claims is None:
                claims = attribute_claims([{'answer': f} for f in facts], [], research.host_name)
            combined.setdefault(idx, []).extend(claims)
    return combined
