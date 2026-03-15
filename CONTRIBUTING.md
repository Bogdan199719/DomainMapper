# Contributing

## Добавление нового сервиса

Новая запись добавляется в `services.json`.

Пример:

```json
"Notion": {
  "aliases": ["notion", "ноушн"],
  "category": "productivity",
  "domains": ["notion.so", "notion.site", "api.notion.com"]
}
```

Поддерживаемые поля:

- `aliases`
- `category`
- `domain_sources`
- `domains`
- `description`

## Проверка

После изменений проверьте:

```bash
python -m domainmapper --search notion
```

И при необходимости реальный запуск:

```bash
python -m domainmapper -s notion -f ip --quality smart --batch
```
