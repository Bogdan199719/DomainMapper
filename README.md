# MyDomainMapper

CLI-инструмент для получения IP-адресов популярных сервисов и подготовки списков маршрутов для VPN, роутеров и split-tunnel сценариев.

Проект ориентирован на простой пользовательский поток:
- выбрать сервис;
- выбрать режим списка адресов;
- выбрать формат вывода;
- получить готовый файл.

## Что умеет

- поиск по 175+ сервисам;
- пошаговый CLI без обязательного знания аргументов;
- несколько DNS-резолверов;
- фильтр Cloudflare;
- режимы качества списка:
  - `Как раньше` — только IP текущего запуска;
  - `Рекомендуемый` — проверенные IP из истории + новые IP;
  - `Самый осторожный` — только подтвержденные IP;
- история IP между запусками в `.mydomainmapper-history.json`;
- форматы вывода:
  - `ip`
  - `cidr`
  - `win`
  - `keeneticfile`
  - `unix`
  - `keenetic`
  - `mikrotik`
  - `ovpn`
  - `wireguard`

## Запуск

### Windows

Двойной клик по [Запустить.bat](./Запустить.bat).

### Python

```bash
pip install -e .
mydomainmapper
```

Или без установки:

```bash
set PYTHONPATH=src
python -m domainmapper
```

## Примеры

Поиск сервиса:

```bash
python -m domainmapper --search telegram
```

Обычный список IP:

```bash
python -m domainmapper -s telegram -f ip --quality smart --batch
```

Файл для импорта в Keenetic:

```bash
python -m domainmapper -s telegram -f keeneticfile --subnet 24 --quality smart --batch
```

Строгий список только из подтвержденных IP:

```bash
python -m domainmapper -s discord -f ip --quality stable --batch
```

## Режимы качества

- `live` — только IP, найденные сейчас.
- `smart` — рекомендуемый режим: подтвержденные IP + новые IP из текущего запуска.
- `stable` — только IP, которые подтверждались в нескольких запусках.

Если не уверены, используйте `smart`.

## Формат `keeneticfile`

Этот формат делает файл вида:

```txt
route add 149.154.167.0 mask 255.255.255.0 0.0.0.0
route add 95.161.64.99 mask 255.255.255.255 0.0.0.0
```

Он подходит для сценария, где шлюз выбирается уже на стороне Keenetic при импорте.

## Конфиг

Основные настройки находятся в [config.ini](./config.ini):

- `service`
- `dnsserver`
- `cloudflare`
- `quality`
- `subnet`
- `filename`
- `filetype`
- `gateway`
- `keenetic`
- `listname`
- `threads`
- `cfginfo`
- `verbose`
- `run`

## Структура проекта

- `src/domainmapper/main.py` — CLI и основной сценарий.
- `src/domainmapper/resolver.py` — DNS-резолв.
- `src/domainmapper/history.py` — история IP и режимы качества.
- `src/domainmapper/formatter.py` — форматы вывода.
- `services.json` — база сервисов и доменов.

## Лицензия

MIT, см. [LICENSE](./LICENSE).
