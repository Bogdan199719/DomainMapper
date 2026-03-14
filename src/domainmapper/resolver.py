"""Async DNS resolver for MyDomainMapper."""
import asyncio
import ipaddress
from asyncio import Semaphore
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import dns.asyncresolver
import httpx
from colorama import Fore, Style

from .services import Service


async def fetch_domains(url: str) -> List[str]:
    """Download a domain list from a URL."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            lines = [line.strip() for line in resp.text.splitlines()]
            return [l for l in lines if l and not l.startswith('#')]
    except Exception as e:
        print(f"{Fore.RED}[!] Ошибка загрузки {url}: {e}{Style.RESET_ALL}")
        return []


async def load_service_domains(svc: Service) -> List[str]:
    """Get all domain names for a service (from URLs + inline list)."""
    domains: Set[str] = set(svc.domains)

    if svc.domain_sources:
        tasks = [fetch_domains(url) for url in svc.domain_sources]
        results = await asyncio.gather(*tasks)
        for batch in results:
            domains.update(batch)

    return [d for d in sorted(domains) if d]


async def get_cloudflare_ips() -> Set[str]:
    """Fetch Cloudflare's published IPv4 ranges and expand to individual IPs."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://www.cloudflare.com/ips-v4/")
            resp.raise_for_status()
            ips: Set[str] = set()
            for line in resp.text.splitlines():
                line = line.strip()
                if '/' in line:
                    try:
                        net = ipaddress.ip_network(line, strict=False)
                        for ip in net:
                            ips.add(str(ip))
                    except ValueError:
                        pass
            return ips
    except Exception as e:
        print(f"{Fore.YELLOW}[!] Не удалось загрузить IP Cloudflare: {e}{Style.RESET_ALL}")
        return set()


async def _resolve_single(
    domain: str,
    resolver: dns.asyncresolver.Resolver,
    semaphore: Semaphore,
    server_name: str,
    exclude_ips: Set[str],
    exclude_cloudflare: bool,
    cloudflare_ips: Set[str],
    stats: Dict,
) -> List[str]:
    async with semaphore:
        stats['total'] += 1
        try:
            answer = await resolver.resolve(domain, 'A')
            result = []
            for rr in answer:
                ip = rr.address
                if ip in ('127.0.0.1', '0.0.0.0') or ip in resolver.nameservers:
                    stats['null'] += 1
                elif exclude_cloudflare and ip in cloudflare_ips:
                    stats['cloudflare'] += 1
                elif ip in exclude_ips:
                    pass  # already seen globally
                else:
                    result.append(ip)
                    print(f"  {Fore.BLUE}{domain}{Style.RESET_ALL} -> {Fore.GREEN}{ip}{Style.RESET_ALL}  [{server_name}]")
            return result
        except Exception:
            print(f"  {Fore.RED}[x] {domain}{Style.RESET_ALL}  [{server_name}]")
            return []


async def resolve_service(
    svc: Service,
    domains: List[str],
    dns_servers: List[Tuple[str, List[str]]],
    exclude_cloudflare: bool,
    cloudflare_ips: Set[str],
    global_seen: Set[str],
    semaphores: Dict[str, Semaphore],
    stats: Dict,
) -> Set[str]:
    """Resolve all domains for one service across all DNS servers."""
    print(f"\n{Fore.YELLOW}>> Обрабатываю: {svc.name}  ({len(domains)} доменов){Style.RESET_ALL}")

    tasks = []
    for server_name, server_ips in dns_servers:
        res = dns.asyncresolver.Resolver()
        res.nameservers = server_ips
        for domain in domains:
            tasks.append(
                _resolve_single(domain, res, semaphores[server_name], server_name,
                                global_seen, exclude_cloudflare, cloudflare_ips, stats)
            )

    results = await asyncio.gather(*tasks)

    service_ips: Set[str] = set()
    for batch in results:
        for ip in batch:
            if ip not in global_seen:
                service_ips.add(ip)
                global_seen.add(ip)

    print(f"  {Fore.CYAN}-> Найдено уникальных IP: {len(service_ips)}{Style.RESET_ALL}")
    return service_ips


def build_semaphores(dns_servers: List[Tuple[str, List[str]]], limit: int) -> Dict[str, Semaphore]:
    return {name: Semaphore(limit) for name, _ in dns_servers}
