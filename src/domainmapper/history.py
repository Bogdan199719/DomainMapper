"""History-based IP quality filters for MyDomainMapper."""
import json
import os
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Set, Tuple

CACHE_FILE = ".mydomainmapper-history.json"
MAX_MISSES = 2
MIN_STABLE_HITS = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_history(base_dir: str) -> Dict:
    path = os.path.join(base_dir, CACHE_FILE)
    if not os.path.exists(path):
        return {"version": 1, "services": {}}
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return {"version": 1, "services": {}}
    if not isinstance(data, dict):
        return {"version": 1, "services": {}}
    data.setdefault("version", 1)
    data.setdefault("services", {})
    return data


def save_history(base_dir: str, history: Dict) -> None:
    path = os.path.join(base_dir, CACHE_FILE)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2, sort_keys=True)


def update_service_history(history: Dict, service_name: str, current_ips: Set[str]) -> None:
    services = history.setdefault("services", {})
    service_entry = services.setdefault(service_name, {"ips": {}})
    ip_entries = service_entry.setdefault("ips", {})
    current_time = utc_now()

    for ip, meta in list(ip_entries.items()):
        if ip in current_ips:
            meta["hits"] = int(meta.get("hits", 0)) + 1
            meta["misses"] = 0
            meta["last_seen"] = current_time
        else:
            meta["misses"] = int(meta.get("misses", 0)) + 1
        meta.setdefault("first_seen", current_time)

    for ip in current_ips:
        if ip in ip_entries:
            continue
        ip_entries[ip] = {
            "first_seen": current_time,
            "last_seen": current_time,
            "hits": 1,
            "misses": 0,
        }

    # Drop very weak stale IPs so cache does not grow forever.
    for ip, meta in list(ip_entries.items()):
        hits = int(meta.get("hits", 0))
        misses = int(meta.get("misses", 0))
        if (hits <= 1 and misses > 5) or misses > 20:
            del ip_entries[ip]


def summarize_service_quality(history: Dict, service_name: str, current_ips: Set[str]) -> Dict[str, int]:
    ip_entries = history.get("services", {}).get(service_name, {}).get("ips", {})
    stable = 0
    retained = 0
    new = 0
    for ip, meta in ip_entries.items():
        hits = int(meta.get("hits", 0))
        misses = int(meta.get("misses", 0))
        if hits >= MIN_STABLE_HITS and misses <= MAX_MISSES:
            if ip in current_ips:
                stable += 1
            else:
                retained += 1
        elif ip in current_ips:
            new += 1
    return {"stable": stable, "retained": retained, "new": new}


def select_service_ips(history: Dict, service_name: str, current_ips: Set[str], quality: str) -> Tuple[Set[str], Dict[str, int], bool]:
    ip_entries = history.get("services", {}).get(service_name, {}).get("ips", {})
    stable_ips = {
        ip
        for ip, meta in ip_entries.items()
        if int(meta.get("hits", 0)) >= MIN_STABLE_HITS and int(meta.get("misses", 0)) <= MAX_MISSES
    }
    retained_ips = {ip for ip in stable_ips if ip not in current_ips}

    fallback_used = False
    if quality == "live":
        selected = set(current_ips)
    elif quality == "stable":
        selected = set(stable_ips)
        if not selected:
            selected = set(current_ips)
            fallback_used = True
    else:  # smart
        selected = set(current_ips) | stable_ips

    summary = {
        "stable": len(stable_ips & current_ips),
        "retained": len(retained_ips),
        "new": len([ip for ip in current_ips if ip not in stable_ips]),
    }
    return selected, summary, fallback_used


def update_history_for_services(history: Dict, service_ips: Dict[str, Set[str]]) -> None:
    for service_name, ips in service_ips.items():
        update_service_history(history, service_name, ips)


def filter_selected_services(history: Dict, service_ips: Dict[str, Set[str]], quality: str) -> Tuple[Set[str], List[str], bool]:
    result: Set[str] = set()
    notes: List[str] = []
    fallback_used = False
    for service_name, ips in service_ips.items():
        selected, summary, used_fallback = select_service_ips(history, service_name, ips, quality)
        result.update(selected)
        if quality != "live":
            notes.append(
                f"{service_name}: проверенных {summary['stable']}, новых {summary['new']}, сохранено из истории {summary['retained']}"
            )
        fallback_used = fallback_used or used_fallback
    return result, notes, fallback_used
