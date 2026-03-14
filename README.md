<div align="center">

# 🌐 MyDomainMapper

**DNS → IP resolver для маршрутизации трафика по сервисам**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Services](https://img.shields.io/badge/Сервисов-175%2B-orange)](#-поддерживаемые-сервисы)
[![Formats](https://img.shields.io/badge/Форматов-8-purple)](#-форматы-вывода)

Инструмент для автоматического разрешения доменных имён популярных сервисов в IP-адреса и генерации готовых конфигураций для роутеров и VPN-клиентов.

[Установка](#-установка) · [Использование](#-использование) · [Сервисы](#-поддерживаемые-сервисы) · [Форматы](#-форматы-вывода) · [Конфигурация](#-конфигурация)

</div>

---

## ✨ Возможности

- 🔍 **Умный поиск** — нечёткий поиск сервисов по имени на русском и английском
- 🌍 **175+ сервисов** — от Telegram и YouTube до Госуслуг и Яндекса
- ⚡ **Асинхронный DNS** — параллельные запросы к нескольким DNS-серверам одновременно
- 📦 **8 форматов вывода** — Windows route, Linux ip route, Keenetic, Mikrotik, OpenVPN, WireGuard, CIDR
- 🗂️ **Категории** — Игры, ИИ, Медиа, Соцсети, Российские сервисы и др.
- 🔧 **Гибкая конфигурация** — через `config.ini` или аргументы командной строки
- 🚫 **Фильтрация Cloudflare** — опциональное исключение IP Cloudflare из результатов
- 📐 **Агрегация подсетей** — /16, /24 или смешанный /24+/32 режим

---

## 🚀 Установка

### Требования

- Python **3.8+**
- pip

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Bogdan199719/DomainMapper.git
cd DomainMapper

# 2. Установить зависимости
pip install -e .

# 3. Запустить
mydomainmapper
```

### Зависимости

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| `dnspython` | ≥ 2.4 | Асинхронный DNS-резолвинг |
| `httpx` | ≥ 0.25 | Загрузка списков доменов по HTTP |
| `colorama` | ≥ 0.4 | Цветной вывод в терминале |

---

## 📖 Использование

### Интерактивный режим

```bash
mydomainmapper
```

Запустит пошаговое меню: выбор сервисов → DNS-серверы → формат вывода.

```
  +=============================================+
  |        MyDomainMapper  v1.0.0               |
  |  DNS -> IP resolver  |  100+ сервисов        |
  +=============================================+

=== Выбор сервисов ===
  0  - Выбрать ВСЕ сервисы
  s  - Поиск по имени / ключевому слову
  c  - Просмотр по категориям
  #  - Ввести номера через пробел
```

### CLI режим

```bash
# Базовый синтаксис
mydomainmapper -s <сервис> -f <формат> [опции]
```

#### Примеры

```bash
# Telegram → CIDR /24
mydomainmapper -s telegram -f cidr --subnet 24 -o telegram.txt

# Discord → Windows route через Cloudflare DNS
mydomainmapper -s discord --dns 4 -f win -g 192.168.1.1 -o discord.txt

# Несколько сервисов → Keenetic CLI
mydomainmapper -s "youtube,netflix,spotify" -f keenetic -g 192.168.1.1

# Все AI-сервисы (через меню категорий)
mydomainmapper

# Поиск сервиса без запуска
mydomainmapper --search telegram
mydomainmapper --search яндекс

# Через Google DNS, агрегация /24
mydomainmapper -s youtube --dns 2 --subnet 24 -f cidr -o youtube-ips.txt

# Все сервисы → WireGuard AllowedIPs
mydomainmapper -s all -f wireguard --subnet 24 -o allowed-ips.txt
```

### Поиск сервисов

```bash
# Поиск возвращает список совпадений с процентом релевантности
mydomainmapper --search discord
```

```
Результаты поиска «discord»:
  + Discord                             [communication]  100%
  + Cisco                               [tech]            66%
  + SoundCloud                          [media]           47%
  ...
```

### Аргументы командной строки

| Аргумент | Описание | Пример |
|----------|----------|--------|
| `-s`, `--service` | Сервис(ы) через запятую или `all` | `-s telegram,discord` |
| `-f`, `--filetype` | Формат вывода | `-f win` |
| `-g`, `--gateway` | IP шлюза (для win/unix) | `-g 192.168.1.1` |
| `-o`, `--output` | Имя выходного файла | `-o routes.txt` |
| `--subnet` | Агрегация: `16`, `24`, `mix` | `--subnet 24` |
| `--dns` | Индексы DNS серверов (0=все) | `--dns 2 4` |
| `--no-cloudflare` | Исключить IP Cloudflare | |
| `--batch` | Без интерактивных вопросов | |
| `--search` | Поиск сервиса и выход | `--search netflix` |
| `-c`, `--config` | Путь к конфиг-файлу | `-c my.ini` |

---

## 📡 DNS серверы

| № | Название | IP адреса |
|---|---------|-----------|
| 1 | Системный DNS | (автоопределение) |
| 2 | Google Public DNS | `8.8.8.8`, `8.8.4.4` |
| 3 | Quad9 | `9.9.9.9`, `149.112.112.112` |
| 4 | Cloudflare DNS | `1.1.1.1`, `1.0.0.1` |
| 5 | OpenDNS | `208.67.222.222`, `208.67.220.220` |
| 6 | AdGuard DNS | `94.140.14.14`, `94.140.15.15` |
| 7 | DNS.Watch | `84.200.69.80`, `84.200.70.40` |
| 8 | CleanBrowsing | `185.228.168.9`, `185.228.169.9` |
| 9 | Alternate DNS | `76.76.19.19`, `76.223.122.150` |
| 10 | Control D | `76.76.2.0`, `76.76.10.0` |
| 11 | Yandex DNS | `77.88.8.8`, `77.88.8.1` |

Использование нескольких DNS-серверов одновременно повышает полноту результатов.

---

## 📤 Форматы вывода

| Формат | Ключ | Пример строки |
|--------|------|---------------|
| Только IP | `ip` | `149.154.167.99` |
| CIDR | `cidr` | `149.154.167.0/24` |
| Windows route | `win` | `route add 149.154.167.0 mask 255.255.255.0 192.168.1.1` |
| Linux ip route | `unix` | `ip route 149.154.167.0/24 192.168.1.1` |
| Keenetic CLI | `keenetic` | `ip route 149.154.167.0/24 192.168.1.1 auto !Telegram` |
| Mikrotik | `mikrotik` | `/ip/firewall/address-list add list=MyList comment="Telegram" address=149.154.167.0/24` |
| OpenVPN | `ovpn` | `push "route 149.154.167.0 255.255.255.0"` |
| WireGuard | `wireguard` | `149.154.167.0/24, 91.108.4.0/24, ...` |

### Агрегация подсетей

| Режим | Описание | Пример |
|-------|----------|--------|
| `/32` (по умолчанию) | Без агрегации, точные IP | `149.154.167.99/32` |
| `/24` | Группировка до /24 подсети | `149.154.167.0/24` |
| `/16` | Группировка до /16 подсети | `149.154.0.0/16` |
| `mix` | /24 для групп + /32 для одиночных | `149.154.167.0/24`, `8.47.69.6/32` |

---

## 🗂️ Поддерживаемые сервисы

175+ сервисов, разбитых по категориям. Поиск работает по имени, псевдонимам и на русском языке.

<details>
<summary><b>🤖 ИИ-сервисы (10)</b></summary>

| Сервис | Псевдонимы |
|--------|-----------|
| ChatGPT / OpenAI | `chatgpt`, `openai`, `чатгпт` |
| Claude / Anthropic | `claude`, `anthropic`, `клод` |
| Gemini / Bard | `gemini`, `bard`, `гемини` |
| Copilot | `copilot`, `github copilot` |
| Grok | `grok`, `xai` |
| DeepL | `deepl`, `дипл` |
| Manus | `manus` |
| Windsurf / Codeium IDE | `windsurf`, `codeium ide` |
| Codeium | `codeium` |
| Trae.ai | `trae` |

</details>

<details>
<summary><b>🎮 Игры (23)</b></summary>

Steam, Epic Games, EA / Origin, Blizzard / Battle.net, Ubisoft, Xbox, Nintendo, Roblox, PUBG, CS-2, BrawlStars, Clash Royale, Hay Day, Squad Busters, Supercell, Warzone, World of Tanks, Raid Shadow Legends, Battlefield5, Demonware, Throne and Liberty, Bethesda, GGSel

</details>

<details>
<summary><b>📺 Медиа и стриминг (22)</b></summary>

YouTube, Netflix, Spotify, Tidal, SoundCloud, Twitch, HDRezka, Anilibria, AnimeGo, Bato.to, Lampa, LostFilm, Medium, VideoCDN, BigFanGroup, DW, IMDB, The Movie DB, The TV DB, MyAnimeList, Pixiv, Meduza

</details>

<details>
<summary><b>💬 Мессенджеры (7)</b></summary>

Telegram, Discord, Signal, Viber, WhatsApp, Element / Matrix, Zoom

</details>

<details>
<summary><b>📱 Соцсети (10)</b></summary>

Facebook, Instagram, Twitter / X, TikTok, LinkedIn, Pinterest, Snapchat, Meta, Boosty, Hornet

</details>

<details>
<summary><b>💻 Технологии и облако (23)</b></summary>

Google, Bing, Microsoft, Outlook, Apple, Facetime, Adobe, GitHub, JetBrains, Cloudflare, Fastly, Akamai, AWS, Hetzner, Intel, Nvidia, Lenovo, Dell, Cisco, Autodesk, AnyDesk, Ubiquiti, eWeLink / Home Connect

</details>

<details>
<summary><b>🇷🇺 Российские сервисы (40)</b></summary>

Яндекс, VK, Ozon, Wildberries, Rutube, Sberbank, Tinkoff, Mail.ru, Госуслуги, Kinopoisk, IVI, Okko, Kion, Smotrim, Wink, VKPlay, Dzen, Habr, 4pda, RZD, Aeroflot, Nalog.ru, Mos.ru, Gosuslugi, RT, MVideo, CIAN, Dom.ru, Tinkoff, и другие...

</details>

<details>
<summary><b>🛒 Торговля и финансы (12)</b></summary>

Patreon, Etsy, eBay, AliExpress, Allegro, Airbnb, Binance, Bestchange, Coinglass, Mouser, Tari Wallet, WeTransfer

</details>

<details>
<summary><b>🎨 Дизайн и продуктивность (9)</b></summary>

Canva, Figma, Miro, Envato, Logo, Notion, Lucid, Udemy, Duolingo

</details>

<details>
<summary><b>🔒 Приватность и торренты (6)</b></summary>

ProtonMail, Tuta, Tor, Rutracker, Rutor, NNMClub

</details>

---

## ⚙️ Конфигурация

Все параметры можно задать в файле `config.ini`:

```ini
[DomainMapper]

# Сервисы: пусто = интерактивный выбор, all = все, или через запятую
service =

# DNS серверы (номера через пробел, 0 = все)
# 2=Google  3=Quad9  4=Cloudflare  6=AdGuard  11=Yandex
dnsserver =

# Исключить IP Cloudflare: yes / no / пусто
cloudflare =

# Агрегация: 16 / 24 / mix / пусто
subnet =

# Выходной файл
filename = resolved-ips.txt

# Параллельных запросов к одному DNS
threads = 20

# Формат: ip / cidr / win / unix / keenetic / mikrotik / ovpn / wireguard
filetype =

# Шлюз для win/unix/keenetic форматов
gateway =

# Имя списка для Mikrotik
listname =

# Команда после завершения (автоматизация)
run =
```

### Примеры `config.ini`

**Для роутера Keenetic:**
```ini
[DomainMapper]
service = telegram,youtube,discord
dnsserver = 2 4
cloudflare = no
subnet = 24
filename = keenetic-routes.txt
filetype = keenetic
keenetic = 192.168.1.1 Home
```

**Для Mikrotik:**
```ini
[DomainMapper]
service = all
dnsserver = 0
subnet = 24
filetype = mikrotik
listname = VPN_Services
filename = mikrotik-list.txt
```

**Для WireGuard:**
```ini
[DomainMapper]
service = telegram,signal,protonmail
dnsserver = 2 3 4
subnet = 24
filetype = wireguard
filename = wg-allowed-ips.txt
```

---

## 📁 Свой список доменов

Добавьте произвольные домены в файл `custom-dns-list.txt` (один домен на строку):

```
# Мои домены
myservice.example.com
api.myapp.ru
cdn.custom-site.net
```

Затем выберите **"Custom"** в меню сервисов или используйте `-s custom`.

---

## 🏗️ Архитектура

```
src/domainmapper/
├── main.py        # CLI, интерактивное меню, оркестрация
├── resolver.py    # Асинхронный DNS-резолвер (asyncio + dnspython)
├── services.py    # Реестр сервисов, нечёткий поиск
├── formatter.py   # Генераторы форматов вывода, агрегация подсетей
└── config.py      # Загрузка и валидация config.ini
```

```
services.json      # База 175+ сервисов (имена, псевдонимы, домены, источники)
config.ini         # Пользовательская конфигурация
custom-dns-list.txt # Пользовательские домены
```

---

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку: `git checkout -b feature/new-service`
3. Добавьте сервис в `services.json`:

```json
"MyService": {
  "aliases": ["myservice", "мойсервис"],
  "category": "tech",
  "domain_sources": ["https://example.com/domains.txt"],
  "domains": ["myservice.com", "api.myservice.com"]
}
```

4. Создайте Pull Request

### Категории сервисов

`media` · `social` · `communication` · `gaming` · `tech` · `ai` · `design` · `productivity` · `education` · `commerce` · `finance` · `privacy` · `torrents` · `ru` · `iot` · `fitness` · `storage` · `other`

---

## 📜 Лицензия

[MIT License](LICENSE) — свободное использование, модификация и распространение.

---

<div align="center">

Сделано с ❤️ | [GitHub](https://github.com/Bogdan199719/DomainMapper) | [Issues](https://github.com/Bogdan199719/DomainMapper/issues)

</div>
