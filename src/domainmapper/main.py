"""MyDomainMapper - main entry point."""
import argparse
import asyncio
import os
import sys
from typing import Dict, List, Optional, Set, Tuple

import dns.asyncresolver
from colorama import Fore, Style, init

from .config import Config, load_config
from .formatter import aggregate_ips, format_lines, write_output
from .resolver import (build_semaphores, get_cloudflare_ips,
                       load_service_domains, resolve_service)
from .services import Service, get_categories, load_services, search_services

init(autoreset=True)

# Force UTF-8 output on Windows (Python 3.7+ supports reconfigure)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- Color helpers ------------------------------------------------------------
def _y(t): return f"{Fore.YELLOW}{t}{Style.RESET_ALL}"
def _g(t): return f"{Fore.GREEN}{t}{Style.RESET_ALL}"
def _c(t): return f"{Fore.CYAN}{t}{Style.RESET_ALL}"
def _r(t): return f"{Fore.RED}{t}{Style.RESET_ALL}"
def _b(t): return f"{Fore.BLUE}{t}{Style.RESET_ALL}"

BANNER = f"""{Fore.CYAN}
  +==============================================+
  |        MyDomainMapper  v1.0.0                |
  |  DNS -> IP resolver  |  100+ сервисов         |
  +==============================================+{Style.RESET_ALL}"""

# --- DNS server list ----------------------------------------------------------
BUILTIN_DNS: Dict[str, List[str]] = {
    'Google Public DNS':  ['8.8.8.8', '8.8.4.4'],
    'Quad9':              ['9.9.9.9', '149.112.112.112'],
    'Cloudflare DNS':     ['1.1.1.1', '1.0.0.1'],
    'OpenDNS':            ['208.67.222.222', '208.67.220.220'],
    'AdGuard DNS':        ['94.140.14.14', '94.140.15.15'],
    'DNS.Watch':          ['84.200.69.80', '84.200.70.40'],
    'CleanBrowsing':      ['185.228.168.9', '185.228.169.9'],
    'Alternate DNS':      ['76.76.19.19', '76.223.122.150'],
    'Control D':          ['76.76.2.0', '76.76.10.0'],
    'Yandex DNS':         ['77.88.8.8', '77.88.8.1'],
}

CATEGORY_LABELS = {
    'media':       'Медиа / стриминг',
    'social':      'Соцсети',
    'communication': 'Мессенджеры',
    'gaming':      'Игры',
    'tech':        'Технологии / облако',
    'ai':          'ИИ-сервисы',
    'design':      'Дизайн',
    'productivity': 'Продуктивность',
    'education':   'Образование',
    'commerce':    'Торговля',
    'finance':     'Финансы',
    'privacy':     'Приватность',
    'torrents':    'Торренты',
    'ru':          '[RU] Российские сервисы',
    'iot':         'IoT / умный дом',
    'fitness':     'Спорт / фитнес',
    'storage':     'Файловые хранилища',
    'adult':       'Для взрослых',
    'other':       'Прочее',
    'custom':      'Пользовательский список',
}


# --- User prompts -------------------------------------------------------------

def prompt_services(services: Dict[str, Service], custom_domains: List[str]) -> List[Service]:
    """Interactive service selection with search and category browsing."""
    all_svcs = list(services.values())

    while True:
        print(f"\n{_y('=== Выбор сервисов ===')}")
        print(f"  {_g('0')}  -- Выбрать ВСЕ сервисы")
        print(f"  {_g('s')}  -- Поиск по имени / ключевому слову")
        print(f"  {_g('c')}  -- Просмотр по категориям")
        print(f"  {_g('#')}  -- Ввести номера через пробел")
        if custom_domains:
            print(f"  {_g('x')}  -- Мой список (custom-dns-list.txt)")

        print(f"\n{_c('Все сервисы ({} шт.):'.format(len(all_svcs)))}")
        for i, svc in enumerate(all_svcs, 1):
            marker = '+' if svc.has_domains() else '.'
            print(f"  {_g(str(i)):>5}. {marker} {svc.name:<30}  [{svc.category}]")

        choice = input(f"\n{_y('Ваш выбор')} [0/s/c/номера]: ").strip().lower()

        if choice == '0':
            return all_svcs

        if choice == 's':
            selected = _search_prompt(services)
            if selected is not None:
                return selected
            continue

        if choice == 'c':
            selected = _category_prompt(services)
            if selected is not None:
                return selected
            continue

        if choice == 'x' and custom_domains:
            from .services import Service as Svc
            custom = services.get('Custom') or Svc(name='Custom', category='custom')
            custom.domains = custom_domains
            return [custom]

        # numeric selection
        parts = choice.replace(',', ' ').split()
        result = []
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(all_svcs):
                    result.append(all_svcs[idx])
        if result:
            return result

        print(_r("Неверный ввод, попробуйте ещё раз."))


def _search_prompt(services: Dict[str, Service]) -> Optional[List[Service]]:
    while True:
        query = input(f"\n{_g('Введите название или часть названия')} (Enter -- назад): ").strip()
        if not query:
            return None

        hits = search_services(query, services, max_results=15, cutoff=0.35)
        if not hits:
            print(_r(f"Ничего не найдено по запросу «{query}». Попробуйте ещё."))
            continue

        print(f"\n{_c('Найдено:')} {len(hits)} результатов")
        for i, (svc, score) in enumerate(hits, 1):
            mark = '+' if svc.has_domains() else '.'
            pct = int(score * 100)
            print(f"  {_g(str(i)):>5}. {mark} {svc.name:<30} [{svc.category}]  {pct}%")

        choice = input(f"\nВыберите {_g('номера')} (0 -- новый поиск): ").strip()
        if choice == '0' or not choice:
            continue

        result = []
        for p in choice.replace(',', ' ').split():
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(hits):
                    result.append(hits[idx][0])
        if result:
            return result


def _category_prompt(services: Dict[str, Service]) -> Optional[List[Service]]:
    cats = get_categories(services)
    print(f"\n{_c('Категории:')}")
    for i, cat in enumerate(cats, 1):
        label = CATEGORY_LABELS.get(cat, cat)
        count = sum(1 for s in services.values() if s.category == cat)
        print(f"  {_g(str(i)):>5}. {label}  ({count} шт.)")

    choice = input(f"\nВыберите {_g('номер')} категории (Enter -- назад): ").strip()
    if not choice or not choice.isdigit():
        return None

    idx = int(choice) - 1
    if 0 <= idx < len(cats):
        cat_svcs = [s for s in services.values() if s.category == cats[idx]]
        print(f"\n{_c('Сервисы категории «{}»:'.format(CATEGORY_LABELS.get(cats[idx], cats[idx])))}")
        for i, svc in enumerate(cat_svcs, 1):
            mark = '+' if svc.has_domains() else '.'
            print(f"  {_g(str(i)):>5}. {mark} {svc.name}")

        nums = input(f"\nВыберите {_g('номера')} (0 -- все в категории, Enter -- назад): ").strip()
        if not nums:
            return None
        if nums == '0':
            return cat_svcs
        result = []
        for p in nums.replace(',', ' ').split():
            if p.isdigit():
                idx2 = int(p) - 1
                if 0 <= idx2 < len(cat_svcs):
                    result.append(cat_svcs[idx2])
        return result or None

    return None


def prompt_dns_servers(cfg: Config) -> List[Tuple[str, List[str]]]:
    """Select DNS servers to use."""
    system_dns = dns.asyncresolver.Resolver().nameservers
    options: List[Tuple[str, List[str]]] = [('Системный DNS', system_dns)] + list(BUILTIN_DNS.items())

    if cfg.dns_server_indices:
        if 0 in cfg.dns_server_indices:
            return options
        result = []
        for idx in cfg.dns_server_indices:
            if 1 <= idx <= len(options):
                result.append(options[idx - 1])
        return result

    print(f"\n{_y('=== DNS серверы ===')}")
    print(f"  {_g('0')}. Использовать все")
    for i, (name, ips) in enumerate(options, 1):
        print(f"  {_g(str(i)):>4}. {name:<22} {', '.join(ips)}")

    while True:
        choice = input(f"\nВыберите {_g('номера')} через пробел [0 -- все]: ").strip()
        if not choice:
            continue
        parts = choice.split()
        if '0' in parts:
            return options
        result = []
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(options):
                    result.append(options[idx])
        if result:
            return result


_BATCH_MODE = False


def _is_interactive() -> bool:
    if _BATCH_MODE:
        return False
    return sys.stdin.isatty()


def prompt_cloudflare(cfg: Config) -> bool:
    if cfg.cloudflare in ('yes', 'y'):
        return True
    if cfg.cloudflare in ('no', 'n'):
        return False
    if not _is_interactive():
        return False  # default: keep cloudflare IPs in non-interactive mode
    ans = input(f"\n{_y('Исключить IP Cloudflare из результатов?')}  [{_g('yes')}/{_g('Enter -- нет')}]: ").strip().lower()
    return ans in ('yes', 'y')


def prompt_subnet(cfg: Config) -> str:
    if cfg.subnet:
        return cfg.subnet
    if not _is_interactive():
        return '32'
    ans = input(f"""
{_y('Агрегировать IP-адреса в подсети?')}
  {_g('16')}   -> /16  (255.255.0.0)
  {_g('24')}   -> /24  (255.255.255.0)
  {_g('mix')}  -> /24 + /32 смешанный режим
  {_g('Enter')} -> не агрегировать (/32)
Выбор: """).strip().lower()
    return ans if ans in ('16', '24', 'mix') else '32'


def prompt_filetype(cfg: Config, subnet: str, service_comment: str) -> Tuple[str, str, str, str]:
    """Return (filetype, gateway, ken_gateway, listname)."""
    filetype = cfg.filetype
    gateway = cfg.gateway
    ken_gateway = cfg.keenetic
    listname = cfg.listname

    suffix = f"/{subnet}"

    if not filetype and not _is_interactive():
        filetype = 'ip'

    if not filetype:
        filetype = input(f"""
{_y('Формат вывода:')}
  {_g('ip')}        -- только IP
  {_g('cidr')}      -- IP{suffix}
  {_g('win')}       -- route add IP mask МАСКА ШЛЮЗ
  {_g('unix')}      -- ip route IP{suffix} ШЛЮЗ
  {_g('keenetic')}  -- ip route IP{suffix} ШЛЮЗ auto !{service_comment}
  {_g('mikrotik')}  -- /ip/firewall/address-list add ...
  {_g('ovpn')}      -- push "route IP МАСКА"
  {_g('wireguard')} -- IP{suffix}, IP{suffix}, ...
  {_g('Enter')}     -- только IP
Ваш выбор: """).strip().lower()

    if filetype in ('win', 'unix') and not gateway:
        gateway = input(f"Укажите {_g('IP шлюза')} или {_g('имя интерфейса')}: ").strip()

    if filetype == 'keenetic' and not ken_gateway:
        ken_gateway = input(f"Укажите {_g('IP шлюза')} [и через пробел {_g('имя интерфейса')}]: ").strip()

    if filetype == 'mikrotik' and not listname:
        listname = input(f"Введите {_g('LIST_NAME')} для Mikrotik firewall: ").strip()

    return filetype, gateway, ken_gateway, listname


# --- Main ---------------------------------------------------------------------

async def run(cfg: Config):
    print(BANNER)

    if cfg.cfginfo and any([cfg.service, cfg.dns_server_indices, cfg.cloudflare,
                             cfg.filetype, cfg.subnet]):
        print(f"\n{_y('Конфигурация из config.ini:')}")
        if cfg.service:
            print(f"  Сервисы:     {cfg.service}")
        if cfg.dns_server_indices:
            print(f"  DNS серверы: {cfg.dns_server_indices}")
        if cfg.filetype:
            print(f"  Формат:      {cfg.filetype}")

    # Load services registry
    try:
        services = load_services()
    except FileNotFoundError:
        print(_r("[!] services.json не найден. Запустите из директории проекта."))
        sys.exit(1)

    # Load custom-dns-list.txt if present
    custom_domains: List[str] = []
    custom_file = os.path.join(os.getcwd(), 'custom-dns-list.txt')
    if os.path.exists(custom_file):
        with open(custom_file, 'r', encoding='utf-8-sig') as f:
            custom_domains = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        if custom_domains:
            print(f"{_c('[+] custom-dns-list.txt:')} {len(custom_domains)} доменов загружено")

    # Select services
    if cfg.service.lower() == 'all':
        selected = list(services.values())
    elif cfg.service:
        names = [n.strip() for n in cfg.service.split(',')]
        selected = []
        for name in names:
            hits = search_services(name, services, max_results=1, cutoff=0.5)
            if hits:
                selected.append(hits[0][0])
            else:
                print(_r(f"[!] Сервис не найден: {name}"))
    else:
        selected = prompt_services(services, custom_domains)

    if not selected:
        print(_r("Сервисы не выбраны. Выход."))
        sys.exit(0)

    print(f"\n{_c('Выбрано сервисов:')} {len(selected)}")
    for s in selected:
        mark = '+' if s.has_domains() else '!'
        print(f"  {mark} {s.name}")

    # DNS servers
    dns_servers = prompt_dns_servers(cfg)
    print(f"\n{_c('DNS серверы:')} {', '.join(n for n, _ in dns_servers)}")

    # Cloudflare filter
    exclude_cf = prompt_cloudflare(cfg)
    cloudflare_ips: Set[str] = set()
    if exclude_cf:
        print(f"{_y('[~] Загружаю IP Cloudflare...')}")
        cloudflare_ips = await get_cloudflare_ips()
        print(f"{_c('[+] Загружено IP Cloudflare:')} {len(cloudflare_ips)}")

    # Resolve
    semaphores = build_semaphores(dns_servers, cfg.threads)
    global_seen: Set[str] = set()
    all_ips: Set[str] = set()
    stats = {'total': 0, 'null': 0, 'cloudflare': 0}

    for svc in selected:
        if svc.category == 'custom' or svc.name == 'Custom':
            domains = custom_domains
        else:
            domains = await load_service_domains(svc)

        if not domains:
            print(f"{_r('[!]')} {svc.name}: домены не найдены, пропускаю.")
            continue

        ips = await resolve_service(
            svc, domains, dns_servers,
            exclude_cf, cloudflare_ips,
            global_seen, semaphores, stats,
        )
        all_ips.update(ips)

    print(f"\n{_y('=== Итоги резолвинга ===')}")
    print(f"  Обработано DNS-имён:  {stats['total']}")
    print(f"  Уникальных IP найдено: {_g(str(len(all_ips)))}")
    if exclude_cf:
        print(f"  Исключено Cloudflare:  {stats['cloudflare']}")
    print(f"  Исключено заглушек:    {stats['null']}")

    if not all_ips:
        print(_r("\n[!] Ни одного IP не получено. Проверьте соединение и DNS."))
        sys.exit(1)

    # Aggregation
    subnet = prompt_subnet(cfg)
    aggregated = aggregate_ips(all_ips, subnet)
    if subnet != '32':
        print(f"{_c(f'[+] После агрегации /{subnet}:')} {len(aggregated)} записей")

    # Format and write
    service_comment = ','.join(''.join(w.capitalize() for w in s.name.split()) for s in selected)
    filetype, gateway, ken_gateway, listname = prompt_filetype(cfg, subnet, service_comment)

    lines = format_lines(
        aggregated, subnet, filetype or 'ip',
        gateway=gateway, ken_gateway=ken_gateway,
        list_name=listname, service_comment=service_comment,
    )

    filename = cfg.filename or 'resolved-ips.txt'
    write_output(lines, filename)
    print(f"\n{_g('+ Готово!')} Сохранено в: {_c(filename)}  ({len(lines)} строк)")

    if cfg.run:
        print(f"\n{_y('[~] Выполняю команду:')} {cfg.run}")
        os.system(cfg.run)

    if os.name == 'nt' and _is_interactive():
        input(f"\nНажмите {_g('Enter')} для выхода...")


def main():
    parser = argparse.ArgumentParser(
        description='MyDomainMapper -- DNS -> IP резолвер для 100+ сервисов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Примеры:
  mydomainmapper                     # интерактивный режим
  mydomainmapper -s telegram,discord # выбрать сервисы сразу
  mydomainmapper -s all -f win -g 192.168.1.1
  mydomainmapper -c my_config.ini""",
    )
    parser.add_argument('-c', '--config', default='config.ini',
                        help='Путь к конфигурационному файлу (по умолчанию: config.ini)')
    parser.add_argument('-s', '--service',
                        help='Сервис(ы) через запятую или "all". Пример: -s telegram,discord')
    parser.add_argument('-f', '--filetype',
                        choices=['ip', 'cidr', 'win', 'unix', 'keenetic', 'mikrotik', 'ovpn', 'wireguard'],
                        help='Формат вывода')
    parser.add_argument('-g', '--gateway',
                        help='IP шлюза (для win/unix форматов)')
    parser.add_argument('-o', '--output', default='',
                        help='Имя выходного файла')
    parser.add_argument('--subnet', choices=['16', '24', 'mix'],
                        help='Агрегация подсетей')
    parser.add_argument('--dns', default='',
                        help='Индексы DNS серверов через пробел (0 -- все)')
    parser.add_argument('--no-cloudflare', action='store_true',
                        help='Исключить IP Cloudflare')
    parser.add_argument('--batch', action='store_true',
                        help='Без интерактивных вопросов, использовать значения по умолчанию')
    parser.add_argument('--search', metavar='QUERY',
                        help='Найти сервис по имени и выйти')

    args = parser.parse_args()

    # Handle --search separately (no network needed)
    if args.search:
        try:
            svcs = load_services()
        except FileNotFoundError:
            print('services.json не найден')
            sys.exit(1)
        hits = search_services(args.search, svcs, max_results=20, cutoff=0.3)
        if not hits:
            print(f"Ничего не найдено по запросу: {args.search}")
        else:
            print(f"Результаты поиска «{args.search}»:")
            for svc, score in hits:
                mark = '+' if svc.has_domains() else '.'
                print(f"  {mark} {svc.name:<35} [{svc.category}]  {int(score*100)}%")
        sys.exit(0)

    cfg = load_config(args.config)

    # CLI args override config
    if args.service:
        cfg.service = args.service
    if args.filetype:
        cfg.filetype = args.filetype
    if args.gateway:
        cfg.gateway = args.gateway
    if args.output:
        cfg.filename = args.output
    if args.subnet:
        cfg.subnet = args.subnet
    if args.dns:
        try:
            cfg.dns_server_indices = list(map(int, args.dns.split()))
        except ValueError:
            pass
    if args.no_cloudflare:
        cfg.cloudflare = 'yes'

    # Auto-batch mode: if service is specified via CLI with output format, skip interactive prompts
    _BATCH = args.batch or bool(args.service and args.filetype)

    # Monkey-patch _is_interactive to respect batch flag
    import domainmapper.main as _m
    _m._BATCH_MODE = _BATCH

    asyncio.run(run(cfg))


if __name__ == '__main__':
    main()
