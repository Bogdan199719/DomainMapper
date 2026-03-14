"""Service registry with fuzzy search for MyDomainMapper."""
import json
import os
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES_FILE = os.path.join(BASE_DIR, 'services.json')


@dataclass
class Service:
    name: str
    aliases: List[str] = field(default_factory=list)
    category: str = 'global'
    domain_sources: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    description: str = ''

    def all_search_terms(self) -> List[str]:
        return [self.name.lower()] + [a.lower() for a in self.aliases]

    def has_domains(self) -> bool:
        return bool(self.domain_sources or self.domains)


def load_services(services_file: str = None) -> Dict[str, Service]:
    """Load service registry from services.json."""
    path = services_file or SERVICES_FILE
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return {
        name: Service(
            name=name,
            aliases=info.get('aliases', []),
            category=info.get('category', 'global'),
            domain_sources=info.get('domain_sources', []),
            domains=info.get('domains', []),
            description=info.get('description', ''),
        )
        for name, info in data.get('services', {}).items()
    }


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def search_services(
    query: str,
    services: Dict[str, Service],
    max_results: int = 10,
    cutoff: float = 0.4,
) -> List[Tuple[Service, float]]:
    """
    Fuzzy search services by name or alias.
    Returns list of (Service, score) tuples sorted by score descending.
    """
    q = query.lower().strip()
    if not q:
        return []

    scored: Dict[str, float] = {}

    for svc in services.values():
        best = 0.0
        for term in svc.all_search_terms():
            # Exact match
            if term == q:
                best = 1.0
                break
            # Prefix / substring match
            if term.startswith(q) or q in term:
                score = 0.85 + 0.15 * (len(q) / max(len(term), 1))
                best = max(best, score)
                continue
            # Fuzzy similarity
            sim = _similarity(q, term)
            best = max(best, sim)

        if best >= cutoff:
            scored[svc.name] = best

    results = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    return [(services[name], score) for name, score in results[:max_results]]


def filter_by_category(services: Dict[str, Service], category: str) -> Dict[str, Service]:
    """Return only services of a given category."""
    return {name: svc for name, svc in services.items() if svc.category == category}


def get_categories(services: Dict[str, Service]) -> List[str]:
    """Return sorted list of unique categories."""
    return sorted(set(svc.category for svc in services.values()))
