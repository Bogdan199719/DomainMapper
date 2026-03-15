"""Async DNS resolver for MyDomainMapper."""
import asyncio
import ipaddress
from asyncio import Semaphore
from typing import Dict, List, Set, Tuple

import dns.asyncresolver
import httpx
from colorama import Fore, Style

from .services import Service


async def fetch_domains(url: str) -> List[str]:
    """Download a domain list from a URL."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            lines = [line.strip() for line in response.text.splitlines()]
            return [line for line in lines if line and not line.startswith("#")]
    except Exception as error:
        print(f"{Fore.RED}[!] Ошибка загрузки {url}: {error}{Style.RESET_ALL}")
        return []


async def load_service_domains(service: Service) -> List[str]:
    """Get all domain names for a service."""
    domains: Set[str] = set(service.domains)

    if service.domain_sources:
        tasks = [fetch_domains(url) for url in service.domain_sources]
        results = await asyncio.gather(*tasks)
        for batch in results:
            domains.update(batch)

    return [domain for domain in sorted(domains) if domain]


async def get_cloudflare_ips() -> Set[str]:
    """Fetch Cloudflare IPv4 ranges and expand them to individual IPs."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://www.cloudflare.com/ips-v4/")
            response.raise_for_status()
            ips: Set[str] = set()
            for line in response.text.splitlines():
                line = line.strip()
                if "/" not in line:
                    continue
                try:
                    network = ipaddress.ip_network(line, strict=False)
                except ValueError:
                    continue
                for ip in network:
                    ips.add(str(ip))
            return ips
    except Exception as error:
        print(f"{Fore.YELLOW}[!] Не удалось загрузить IP Cloudflare: {error}{Style.RESET_ALL}")
        return set()


async def _resolve_single(
    domain: str,
    resolver: dns.asyncresolver.Resolver,
    semaphore: Semaphore,
    server_name: str,
    exclude_ips: Set[str],
    exclude_cloudflare: bool,
    cloudflare_ips: Set[str],
    stats: Dict[str, int],
    verbose: bool,
) -> List[str]:
    async with semaphore:
        stats["total"] += 1
        try:
            answer = await resolver.resolve(domain, "A")
            result = []
            for record in answer:
                ip = record.address
                if ip in ("127.0.0.1", "0.0.0.0") or ip in resolver.nameservers:
                    stats["null"] += 1
                elif exclude_cloudflare and ip in cloudflare_ips:
                    stats["cloudflare"] += 1
                elif ip in exclude_ips:
                    pass
                else:
                    result.append(ip)
                    if verbose:
                        print(f"  {Fore.BLUE}{domain}{Style.RESET_ALL} -> {Fore.GREEN}{ip}{Style.RESET_ALL}  [{server_name}]")
            if result:
                stats["resolved"] += 1
            elif verbose:
                print(f"  {Fore.YELLOW}[-] {domain}{Style.RESET_ALL}  [{server_name}]")
            return result
        except Exception:
            stats["errors"] += 1
            if verbose:
                print(f"  {Fore.RED}[x] {domain}{Style.RESET_ALL}  [{server_name}]")
            return []


async def resolve_service(
    service: Service,
    domains: List[str],
    dns_servers: List[Tuple[str, List[str]]],
    exclude_cloudflare: bool,
    cloudflare_ips: Set[str],
    global_seen: Set[str],
    semaphores: Dict[str, Semaphore],
    stats: Dict[str, int],
    verbose: bool = False,
) -> Set[str]:
    """Resolve all domains for one service across all DNS servers."""
    print(f"\n{Fore.YELLOW}>> Обрабатываю: {service.name} ({len(domains)} доменов){Style.RESET_ALL}")

    start_total = stats.get("total", 0)
    start_resolved = stats.get("resolved", 0)
    start_errors = stats.get("errors", 0)

    tasks = []
    for server_name, server_ips in dns_servers:
        resolver = dns.asyncresolver.Resolver()
        resolver.nameservers = server_ips
        for domain in domains:
            tasks.append(
                _resolve_single(
                    domain,
                    resolver,
                    semaphores[server_name],
                    server_name,
                    global_seen,
                    exclude_cloudflare,
                    cloudflare_ips,
                    stats,
                    verbose,
                )
            )

    results = await asyncio.gather(*tasks)

    service_ips: Set[str] = set()
    for batch in results:
        for ip in batch:
            if ip not in global_seen:
                service_ips.add(ip)
                global_seen.add(ip)

    attempts = stats["total"] - start_total
    resolved = stats["resolved"] - start_resolved
    errors = stats["errors"] - start_errors
    print(
        f"  {Fore.CYAN}-> Уникальных IP: {len(service_ips)}{Style.RESET_ALL}"
        f" | успешных ответов: {resolved}"
        f" | ошибок: {errors}"
        f" | попыток: {attempts}"
    )
    return service_ips


def build_semaphores(dns_servers: List[Tuple[str, List[str]]], limit: int) -> Dict[str, Semaphore]:
    return {name: Semaphore(limit) for name, _ in dns_servers}
