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
from .history import (
    filter_selected_services,
    load_history,
    save_history,
    update_history_for_services,
)
from .resolver import build_semaphores, get_cloudflare_ips, load_service_domains, resolve_service
from .services import Service, get_categories, load_services, search_services

init(autoreset=True)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _y(text: str) -> str:
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"


def _g(text: str) -> str:
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}"


def _c(text: str) -> str:
    return f"{Fore.CYAN}{text}{Style.RESET_ALL}"


def _r(text: str) -> str:
    return f"{Fore.RED}{text}{Style.RESET_ALL}"


BANNER = f"""{Fore.CYAN}
  +======================================================+
  |              MyDomainMapper  v1.0.0                  |
  |  DNS -> IP resolver для сервисов и маршрутизации     |
  +======================================================+{Style.RESET_ALL}"""

BUILTIN_DNS: Dict[str, List[str]] = {
    "Google Public DNS": ["8.8.8.8", "8.8.4.4"],
    "Quad9": ["9.9.9.9", "149.112.112.112"],
    "Cloudflare DNS": ["1.1.1.1", "1.0.0.1"],
    "OpenDNS": ["208.67.222.222", "208.67.220.220"],
    "AdGuard DNS": ["94.140.14.14", "94.140.15.15"],
    "DNS.Watch": ["84.200.69.80", "84.200.70.40"],
    "CleanBrowsing": ["185.228.168.9", "185.228.169.9"],
    "Alternate DNS": ["76.76.19.19", "76.223.122.150"],
    "Control D": ["76.76.2.0", "76.76.10.0"],
    "Yandex DNS": ["77.88.8.8", "77.88.8.1"],
}

CATEGORY_LABELS = {
    "media": "Медиа и стриминг",
    "social": "Соцсети",
    "communication": "Мессенджеры",
    "gaming": "Игры",
    "tech": "Технологии и облако",
    "ai": "ИИ-сервисы",
    "design": "Дизайн",
    "productivity": "Продуктивность",
    "education": "Образование",
    "commerce": "Торговля",
    "finance": "Финансы",
    "privacy": "Приватность",
    "torrents": "Торренты",
    "ru": "[RU] Российские сервисы",
    "iot": "IoT и умный дом",
    "fitness": "Спорт и фитнес",
    "storage": "Файловые хранилища",
    "adult": "Для взрослых",
    "other": "Прочее",
    "custom": "Пользовательский список",
}

FILETYPE_OPTIONS = [
    ("ip", "Только IP", "Простой список IP-адресов"),
    ("cidr", "CIDR", "Список IP и подсетей в формате CIDR"),
    ("win", "Windows route", "Готовые команды route add"),
    ("keeneticfile", "Keenetic import", "Файл route add ... 0.0.0.0 для импорта в Keenetic"),
    ("unix", "Linux ip route", "Готовые команды ip route"),
    ("keenetic", "Keenetic CLI", "Маршруты для командной строки Keenetic"),
    ("mikrotik", "Mikrotik", "address-list для Mikrotik"),
    ("ovpn", "OpenVPN", "Строки push route"),
    ("wireguard", "WireGuard", "Строка AllowedIPs"),
]

QUALITY_OPTIONS = [
    ("live", "Как раньше", "Только IP, найденные сейчас"),
    ("smart", "Рекомендуемый", "Проверенные IP + новые IP из текущего запуска"),
    ("stable", "Самый осторожный", "Только IP, которые уже подтверждались раньше"),
]

_BATCH_MODE = False


def _is_interactive() -> bool:
    if _BATCH_MODE:
        return False
    return sys.stdin.isatty()


def _match_services_by_name(raw: str, services: Dict[str, Service]) -> List[Service]:
    selected: List[Service] = []
    seen: Set[str] = set()
    for chunk in [part.strip() for part in raw.split(",") if part.strip()]:
        hits = search_services(chunk, services, max_results=1, cutoff=0.5)
        if hits:
            svc = hits[0][0]
            if svc.name not in seen:
                selected.append(svc)
                seen.add(svc.name)
    return selected


def _full_list_prompt(all_services: List[Service]) -> Optional[List[Service]]:
    print(f"\n{_c('Все сервисы:')} {len(all_services)} шт.")
    for index, svc in enumerate(all_services, 1):
        marker = "+" if svc.has_domains() else "."
        print(f"  {_g(str(index)):>4}. {marker} {svc.name:<30} [{svc.category}]")

    choice = input(f"\nВведите {_g('номера')} через пробел (Enter -- назад, 0 -- все): ").strip()
    if not choice:
        return None
    if choice == "0":
        return all_services

    result = []
    for part in choice.replace(",", " ").split():
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(all_services):
                result.append(all_services[idx])
    return result or None


def _search_prompt(services: Dict[str, Service]) -> Optional[List[Service]]:
    while True:
        query = input(f"\n{_g('Введите название сервиса')} (Enter -- назад): ").strip()
        if not query:
            return None

        hits = search_services(query, services, max_results=15, cutoff=0.35)
        if not hits:
            print(_r(f"По запросу «{query}» ничего не найдено."))
            continue

        print(f"\n{_c('Найдено:')} {len(hits)}")
        for index, (svc, score) in enumerate(hits, 1):
            marker = "+" if svc.has_domains() else "."
            print(f"  {_g(str(index)):>4}. {marker} {svc.name:<30} [{svc.category}] {int(score * 100)}%")

        choice = input(f"\nВыберите {_g('номера')} (0 -- новый поиск): ").strip()
        if not choice or choice == "0":
            continue

        result = []
        for part in choice.replace(",", " ").split():
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(hits):
                    result.append(hits[idx][0])
        if result:
            return result


def _category_prompt(services: Dict[str, Service]) -> Optional[List[Service]]:
    categories = get_categories(services)
    while True:
        print(f"\n{_c('Категории:')}")
        for index, category in enumerate(categories, 1):
            label = CATEGORY_LABELS.get(category, category)
            count = sum(1 for svc in services.values() if svc.category == category)
            print(f"  {_g(str(index)):>4}. {label:<30} ({count} шт.)")

        choice = input(f"\nВыберите {_g('номер')} категории (Enter -- назад): ").strip()
        if not choice:
            return None
        if not choice.isdigit():
            print(_r("Нужно ввести номер категории."))
            continue

        idx = int(choice) - 1
        if not (0 <= idx < len(categories)):
            print(_r("Такой категории нет."))
            continue

        category = categories[idx]
        category_services = [svc for svc in services.values() if svc.category == category]
        print(f"\n{_c('Сервисы категории:')} {CATEGORY_LABELS.get(category, category)}")
        for sub_index, svc in enumerate(category_services, 1):
            marker = "+" if svc.has_domains() else "."
            print(f"  {_g(str(sub_index)):>4}. {marker} {svc.name}")

        selection = input(f"\nВведите {_g('номера')} (0 -- все, Enter -- назад): ").strip()
        if not selection:
            continue
        if selection == "0":
            return category_services

        result = []
        for part in selection.replace(",", " ").split():
            if part.isdigit():
                sub_idx = int(part) - 1
                if 0 <= sub_idx < len(category_services):
                    result.append(category_services[sub_idx])
        if result:
            return result
        print(_r("Не удалось выбрать сервисы, попробуйте ещё раз."))


def prompt_services(services: Dict[str, Service], custom_domains: List[str]) -> List[Service]:
    all_services = list(services.values())
    while True:
        print(f"\n{_y('=== Выбор сервисов ===')}")
        print(f"  {_g('1')} -- Быстрый поиск по названию")
        print(f"  {_g('2')} -- Выбор по категориям")
        print(f"  {_g('3')} -- Полный список сервисов")
        print(f"  {_g('4')} -- Все сервисы")
        if custom_domains:
            print(f"  {_g('5')} -- Мой список из custom-dns-list.txt")
        print(f"\n{_c('Подсказка:')} можно сразу написать название, например: telegram, discord")

        choice = input(f"\n{_y('Ваш выбор')} [1-5 или название]: ").strip()
        lowered = choice.lower()

        if lowered == "1":
            selected = _search_prompt(services)
            if selected is not None:
                return selected
            continue
        if lowered == "2":
            selected = _category_prompt(services)
            if selected is not None:
                return selected
            continue
        if lowered == "3":
            selected = _full_list_prompt(all_services)
            if selected is not None:
                return selected
            continue
        if lowered == "4":
            return all_services
        if lowered == "5" and custom_domains:
            custom = services.get("Custom") or Service(name="Custom", category="custom")
            custom.domains = custom_domains
            return [custom]

        direct = _match_services_by_name(choice, services)
        if direct:
            return direct

        print(_r("Неверный ввод, попробуйте ещё раз."))


def prompt_dns_servers(cfg: Config) -> List[Tuple[str, List[str]]]:
    system_dns = dns.asyncresolver.Resolver().nameservers
    options: List[Tuple[str, List[str]]] = [("Системный DNS", system_dns)] + list(BUILTIN_DNS.items())

    if cfg.dns_server_indices:
        if 0 in cfg.dns_server_indices:
            return options
        result = []
        for idx in cfg.dns_server_indices:
            if 1 <= idx <= len(options):
                result.append(options[idx - 1])
        return result

    if not _is_interactive():
        picked = []
        for idx in (0, 1, 3):
            if idx < len(options):
                picked.append(options[idx])
        return picked

    print(f"\n{_y('=== DNS серверы ===')}")
    print(f"  {_g('1')} -- Рекомендуемый набор (системный + Google + Cloudflare)")
    print(f"  {_g('2')} -- Только системный DNS")
    print(f"  {_g('3')} -- Выбрать вручную")

    while True:
        choice = input(f"\nВаш выбор [1-3, Enter -- 1]: ").strip()
        if not choice or choice == "1":
            picked = []
            for idx in (0, 1, 3):
                if idx < len(options):
                    picked.append(options[idx])
            return picked
        if choice == "2":
            return [options[0]]
        if choice == "3":
            print(f"\n{_c('Доступные DNS серверы:')}")
            print(f"  {_g('0')}. Все доступные")
            for index, (name, ips) in enumerate(options, 1):
                print(f"  {_g(str(index)):>4}. {name:<22} {', '.join(ips)}")

            manual = input(f"\nВведите {_g('номера')} через пробел: ").strip()
            if not manual:
                continue
            parts = manual.split()
            if "0" in parts:
                return options

            result = []
            for part in parts:
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(options):
                        result.append(options[idx])
            if result:
                return result
        print(_r("Неверный выбор, попробуйте ещё раз."))


def prompt_cloudflare(cfg: Config) -> bool:
    if cfg.cloudflare in ("yes", "y"):
        return True
    if cfg.cloudflare in ("no", "n"):
        return False
    if not _is_interactive():
        return False

    answer = input(
        f"\n{_y('Убирать IP Cloudflare из результата?')} "
        f"[{_g('yes')}/{_g('Enter -- нет')}]: "
    ).strip().lower()
    return answer in ("yes", "y")


def prompt_quality(cfg: Config) -> str:
    if cfg.quality in {"live", "smart", "stable"}:
        return cfg.quality
    if not _is_interactive():
        return "live"

    print(f"\n{_y('Режим списка адресов:')}")
    for index, (key, title, description) in enumerate(QUALITY_OPTIONS, 1):
        recommended = " (рекомендуется)" if key == "smart" else ""
        print(f"  {_g(str(index))} -- {title}{recommended}")
        print(f"      {description}")
    print(f"\n{_c('Если не уверены, выбирайте 2.')}")

    choice = input(f"\nВаш выбор [1-3, Enter -- 2]: ").strip()
    mapping = {"1": "live", "2": "smart", "3": "stable"}
    return mapping.get(choice, "smart")


def prompt_subnet(cfg: Config) -> str:
    if cfg.subnet:
        return cfg.subnet
    if not _is_interactive():
        return "32"

    choice = input(
        f"""
{_y('Как сохранить адреса?')}
  {_g('1')} -> Точные IP (/32, по умолчанию)
  {_g('2')} -> Подсети /24
  {_g('3')} -> Подсети /16
  {_g('4')} -> Смешанный режим /24 + /32
Ваш выбор [1-4, Enter -- 1]: """
    ).strip()
    mapping = {"1": "32", "2": "24", "3": "16", "4": "mix"}
    return mapping.get(choice, "32")


def prompt_filetype(cfg: Config, subnet: str, service_comment: str) -> Tuple[str, str, str, str]:
    filetype = cfg.filetype
    gateway = cfg.gateway
    ken_gateway = cfg.keenetic
    listname = cfg.listname

    if not filetype and not _is_interactive():
        filetype = "ip"

    if not filetype:
        print(f"\n{_y('Формат вывода:')}")
        for index, (key, title, description) in enumerate(FILETYPE_OPTIONS, 1):
            extra = f" /{subnet}" if key in {"cidr", "unix", "keenetic", "wireguard"} else ""
            print(f"  {_g(str(index))}. {title:<18} ({key}) {description}{extra}")

        choice = input(f"\nВаш выбор [1-9, Enter -- 1]: ").strip().lower()
        if not choice:
            filetype = "ip"
        elif choice.isdigit() and 1 <= int(choice) <= len(FILETYPE_OPTIONS):
            filetype = FILETYPE_OPTIONS[int(choice) - 1][0]
        else:
            filetype = choice

    if filetype in ("win", "unix") and not gateway:
        gateway = input(f"Укажите {_g('IP шлюза')} или {_g('имя интерфейса')}: ").strip()
    if filetype == "keenetic" and not ken_gateway:
        ken_gateway = input(f"Укажите {_g('IP шлюза')} [и через пробел {_g('имя интерфейса')}]: ").strip()
    if filetype == "mikrotik" and not listname:
        listname = input(f"Введите {_g('LIST_NAME')} для Mikrotik: ").strip()

    return filetype or "ip", gateway, ken_gateway, listname


def suggest_output_filename(cfg: Config, selected: List[Service], filetype: str) -> str:
    if cfg.filename and cfg.filename != "resolved-ips.txt":
        return cfg.filename

    parts = []
    for svc in selected[:3]:
        normalized = "".join(ch.lower() for ch in svc.name if ch.isalnum())
        if normalized:
            parts.append(normalized)
    base = "-".join(parts) or "resolved"
    if len(selected) > 3:
        base += f"-plus{len(selected) - 3}"
    return f"{base}-{filetype}.txt"


async def run(cfg: Config) -> None:
    print(BANNER)

    if cfg.cfginfo and any([cfg.service, cfg.dns_server_indices, cfg.cloudflare, cfg.filetype, cfg.subnet, cfg.quality]):
        print(f"\n{_y('Параметры из config.ini:')}")
        if cfg.service:
            print(f"  Сервисы: {cfg.service}")
        if cfg.dns_server_indices:
            print(f"  DNS:     {cfg.dns_server_indices}")
        if cfg.filetype:
            print(f"  Формат:  {cfg.filetype}")
        if cfg.quality:
            print(f"  Режим:   {cfg.quality}")

    try:
        services = load_services()
    except FileNotFoundError:
        print(_r("[!] services.json не найден. Запустите программу из папки проекта."))
        sys.exit(1)

    custom_domains: List[str] = []
    custom_file = os.path.join(os.getcwd(), "custom-dns-list.txt")
    if os.path.exists(custom_file):
        with open(custom_file, "r", encoding="utf-8-sig") as file:
            custom_domains = [line.strip() for line in file if line.strip() and not line.startswith("#")]
        if custom_domains:
            print(f"{_c('[+] custom-dns-list.txt:')} загружено {len(custom_domains)} доменов")

    if cfg.service.lower() == "all":
        selected = list(services.values())
    elif cfg.service:
        selected = _match_services_by_name(cfg.service, services)
        missing = [name.strip() for name in cfg.service.split(",") if name.strip()]
        found_names = {svc.name for svc in selected}
        for name in missing:
            hits = search_services(name, services, max_results=1, cutoff=0.5)
            if not hits or hits[0][0].name not in found_names:
                print(_r(f"[!] Сервис не найден: {name}"))
    else:
        selected = prompt_services(services, custom_domains)

    if not selected:
        print(_r("Сервисы не выбраны. Выход."))
        sys.exit(0)

    print(f"\n{_c('Выбрано сервисов:')} {len(selected)}")
    for svc in selected:
        marker = "+" if svc.has_domains() else "!"
        print(f"  {marker} {svc.name}")

    dns_servers = prompt_dns_servers(cfg)
    print(f"\n{_c('DNS серверы:')} {', '.join(name for name, _ in dns_servers)}")

    exclude_cf = prompt_cloudflare(cfg)
    cloudflare_ips: Set[str] = set()
    if exclude_cf:
        print(f"{_y('[~] Загружаю IP Cloudflare...')}")
        cloudflare_ips = await get_cloudflare_ips()
        print(f"{_c('[+] Загружено IP Cloudflare:')} {len(cloudflare_ips)}")

    semaphores = build_semaphores(dns_servers, cfg.threads)
    global_seen: Set[str] = set()
    current_ips: Set[str] = set()
    service_ips: Dict[str, Set[str]] = {}
    stats = {"total": 0, "null": 0, "cloudflare": 0, "resolved": 0, "errors": 0}

    for svc in selected:
        if svc.category == "custom" or svc.name == "Custom":
            domains = custom_domains
        else:
            domains = await load_service_domains(svc)

        if not domains:
            print(f"{_r('[!]')} {svc.name}: домены не найдены, пропускаю.")
            service_ips[svc.name] = set()
            continue

        ips = await resolve_service(
            svc,
            domains,
            dns_servers,
            exclude_cf,
            cloudflare_ips,
            global_seen,
            semaphores,
            stats,
            verbose=cfg.verbose,
        )
        service_ips[svc.name] = set(ips)
        current_ips.update(ips)

    print(f"\n{_y('=== Итоги резолвинга ===')}")
    print(f"  Обработано DNS-имён:  {stats['total']}")
    print(f"  Успешных ответов:     {stats['resolved']}")
    print(f"  Ошибок DNS:           {stats['errors']}")
    print(f"  Уникальных IP найдено: {_g(str(len(current_ips)))}")
    if exclude_cf:
        print(f"  Исключено Cloudflare:  {stats['cloudflare']}")
    print(f"  Исключено заглушек:    {stats['null']}")

    if not current_ips:
        print(_r("\n[!] Не удалось получить ни одного IP. Проверьте соединение и DNS."))
        sys.exit(1)

    quality = prompt_quality(cfg)
    history = load_history(os.getcwd())
    update_history_for_services(history, service_ips)
    selected_ips, quality_notes, fallback_used = filter_selected_services(history, service_ips, quality)
    save_history(os.getcwd(), history)

    if quality != "live":
        print(f"\n{_c('Режим качества:')} {quality}")
        for note in quality_notes:
            print(f"  - {note}")
        if fallback_used and quality == "stable":
            print(f"  {_y('[~] Для части сервисов ещё нет истории. Использую IP из текущего запуска.')}")

    if not selected_ips:
        print(_r("\n[!] После фильтрации список пуст. Попробуйте режим live или smart."))
        sys.exit(1)

    subnet = prompt_subnet(cfg)
    aggregated = aggregate_ips(selected_ips, subnet)
    if subnet != "32":
        print(f"{_c(f'[+] После агрегации /{subnet}:')} {len(aggregated)} записей")

    service_comment = ",".join("".join(word.capitalize() for word in svc.name.split()) for svc in selected)
    filetype, gateway, ken_gateway, listname = prompt_filetype(cfg, subnet, service_comment)

    lines = format_lines(
        aggregated,
        subnet,
        filetype,
        gateway=gateway,
        ken_gateway=ken_gateway,
        list_name=listname,
        service_comment=service_comment,
    )

    filename = suggest_output_filename(cfg, selected, filetype)
    write_output(lines, filename)
    print(f"\n{_g('+ Готово!')} Сохранено в {_c(filename)} ({len(lines)} строк)")

    if cfg.run:
        print(f"\n{_y('[~] Выполняю команду:')} {cfg.run}")
        os.system(cfg.run)

    if os.name == "nt" and _is_interactive():
        input(f"\nНажмите {_g('Enter')} для выхода...")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MyDomainMapper -- DNS -> IP резолвер для сервисов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Примеры:
  mydomainmapper
  mydomainmapper -s telegram,discord --quality smart
  mydomainmapper -s all -f keeneticfile --subnet 24 --quality stable
  mydomainmapper --search youtube""",
    )
    parser.add_argument("-c", "--config", default="config.ini", help="Путь к config.ini")
    parser.add_argument("-s", "--service", help='Сервис или список через запятую, либо "all"')
    parser.add_argument(
        "-f",
        "--filetype",
        choices=["ip", "cidr", "win", "keeneticfile", "unix", "keenetic", "mikrotik", "ovpn", "wireguard"],
        help="Формат вывода",
    )
    parser.add_argument("-g", "--gateway", help="IP шлюза для win/unix")
    parser.add_argument("-o", "--output", default="", help="Имя выходного файла")
    parser.add_argument("--subnet", choices=["16", "24", "mix"], help="Агрегация подсетей")
    parser.add_argument("--dns", default="", help="Индексы DNS через пробел (0 -- все)")
    parser.add_argument("--no-cloudflare", action="store_true", help="Исключить IP Cloudflare")
    parser.add_argument("--batch", action="store_true", help="Не задавать интерактивных вопросов")
    parser.add_argument("--verbose", action="store_true", help="Показывать подробный вывод по каждому домену")
    parser.add_argument("--quality", choices=["live", "smart", "stable"], help="Качество итогового списка")
    parser.add_argument("--search", metavar="QUERY", help="Найти сервис по имени и выйти")

    args = parser.parse_args()

    if args.search:
        try:
            services = load_services()
        except FileNotFoundError:
            print("services.json не найден")
            sys.exit(1)

        hits = search_services(args.search, services, max_results=20, cutoff=0.3)
        if not hits:
            print(f"По запросу ничего не найдено: {args.search}")
        else:
            print(f"Результаты поиска «{args.search}»:")
            for svc, score in hits:
                marker = "+" if svc.has_domains() else "."
                print(f"  {marker} {svc.name:<35} [{svc.category}] {int(score * 100)}%")
        sys.exit(0)

    cfg = load_config(args.config)

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
        cfg.cloudflare = "yes"
    if args.verbose:
        cfg.verbose = True
    if args.quality:
        cfg.quality = args.quality

    global _BATCH_MODE
    _BATCH_MODE = args.batch or bool(args.service and args.filetype)

    asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
