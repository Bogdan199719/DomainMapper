"""Configuration management for MyDomainMapper."""
import configparser
import os
from dataclasses import dataclass, field
from typing import List

DEFAULT_VALUES = {
    'service': '',
    'dnsserver': '',
    'cloudflare': '',
    'subnet': '',
    'filename': 'resolved-ips.txt',
    'threads': '20',
    'filetype': '',
    'gateway': '',
    'keenetic': '',
    'listname': '',
    'cfginfo': 'yes',
    'run': '',
    'localplatform': 'no',
    'localdns': 'yes',
}


@dataclass
class Config:
    service: str = ''
    dns_server_indices: List[int] = field(default_factory=list)
    cloudflare: str = ''
    subnet: str = ''
    filename: str = 'resolved-ips.txt'
    threads: int = 20
    filetype: str = ''
    gateway: str = ''
    keenetic: str = ''
    listname: str = ''
    cfginfo: bool = True
    run: str = ''
    localplatform: bool = False
    localdns: bool = True


def load_config(cfg_file: str = 'config.ini') -> Config:
    parser = configparser.ConfigParser()
    parser.read_dict({'DomainMapper': DEFAULT_VALUES})

    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, 'r', encoding='utf-8-sig') as f:
                parser.read_file(f)
        except Exception as e:
            print(f"[!] Ошибка чтения конфига {cfg_file}: {e}")

    s = parser['DomainMapper']

    raw_dns = s.get('dnsserver', '').strip()
    dns_indices: List[int] = []
    if raw_dns:
        try:
            dns_indices = list(map(int, raw_dns.split()))
        except ValueError:
            pass

    def flag(key: str, default: bool = False) -> bool:
        val = s.get(key, '').strip().lower()
        if val in ('yes', 'y'):
            return True
        if val in ('no', 'n'):
            return False
        return default

    return Config(
        service=s.get('service', '').strip(),
        dns_server_indices=dns_indices,
        cloudflare=s.get('cloudflare', '').strip(),
        subnet=s.get('subnet', '').strip(),
        filename=s.get('filename', 'resolved-ips.txt').strip() or 'resolved-ips.txt',
        threads=int(s.get('threads', '20').strip() or '20'),
        filetype=s.get('filetype', '').strip(),
        gateway=s.get('gateway', '').strip(),
        keenetic=s.get('keenetic', '').strip(),
        listname=s.get('listname', '').strip(),
        cfginfo=flag('cfginfo', default=True),
        run=s.get('run', '').strip(),
        localplatform=flag('localplatform', default=False),
        localdns=flag('localdns', default=True),
    )
