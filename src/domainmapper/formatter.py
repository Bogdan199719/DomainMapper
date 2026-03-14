"""Output format generators for MyDomainMapper."""
import ipaddress
from typing import Callable, List, Set


# ─── Subnet aggregation ───────────────────────────────────────────────────────

def aggregate_ips(ips: Set[str], mode: str) -> Set[str]:
    """
    Aggregate a set of IP addresses.
    mode: '16' → /16, '24' → /24, 'mix' → /24 for groups + /32 singles, '32' → no change
    """
    if mode not in ('16', '24', 'mix'):
        return ips

    if mode in ('16', '24'):
        prefix = int(mode)
        result = set()
        for ip in ips:
            try:
                net = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
                result.add(str(net.network_address))
            except ValueError:
                result.add(ip)
        return result

    # mix: group by /24, if >1 host → use /24 base, else keep /32
    groups: dict = {}
    for ip in ips:
        key = '.'.join(ip.split('.')[:3])
        groups.setdefault(key, []).append(ip)

    result = set()
    for key, group in groups.items():
        if len(group) > 1:
            result.add(f"{key}.0")   # /24 base
        else:
            result.add(group[0])     # /32
    return result


# ─── Formatters ───────────────────────────────────────────────────────────────

def _net_mask(mode: str) -> str:
    return {
        '16': '255.255.0.0',
        '24': '255.255.255.0',
        'mix': '',       # handled per-IP in mix formatters
        '32': '255.255.255.255',
    }.get(mode, '255.255.255.255')


def _cidr_suffix(ip: str, mode: str) -> str:
    if mode == 'mix':
        return '/24' if ip.endswith('.0') else '/32'
    return f"/{mode}"


def _mask_for_mix(ip: str) -> str:
    return '255.255.255.0' if ip.endswith('.0') else '255.255.255.255'


def format_lines(
    ips: Set[str],
    mode: str,
    filetype: str,
    gateway: str = '',
    ken_gateway: str = '',
    list_name: str = '',
    service_comment: str = '',
) -> List[str]:
    """Convert a set of IPs to formatted routing lines."""
    sorted_ips = sorted(ips, key=lambda ip: tuple(int(x) for x in ip.split('.')))
    mask = _net_mask(mode)
    lines = []

    for ip in sorted_ips:
        cidr = _cidr_suffix(ip, mode)
        mix_mask = _mask_for_mix(ip) if mode == 'mix' else mask

        if filetype == 'win':
            line = f"route add {ip} mask {mix_mask if mode == 'mix' else mask} {gateway}"
        elif filetype == 'unix':
            line = f"ip route {ip}{cidr} {gateway}"
        elif filetype == 'keenetic':
            line = f"ip route {ip}{cidr} {ken_gateway} auto !{service_comment}"
        elif filetype == 'cidr':
            line = f"{ip}{cidr}"
        elif filetype == 'mikrotik':
            line = f'/ip/firewall/address-list add list={list_name} comment="{service_comment}" address={ip}{cidr}'
        elif filetype == 'ovpn':
            ovpn_mask = mix_mask if mode == 'mix' else mask
            line = f'push "route {ip} {ovpn_mask}"'
        elif filetype == 'wireguard':
            lines.append(f"{ip}{cidr}")
            continue
        else:  # plain ip
            line = ip
        lines.append(line)

    if filetype == 'wireguard':
        return [', '.join(lines)]

    return lines


def write_output(lines: List[str], filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        if lines:
            f.write('\n')
