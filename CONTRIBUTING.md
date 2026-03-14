# Как добавить новый сервис

## Структура записи в `services.json`

```json
"Название сервиса": {
  "aliases": ["псевдоним1", "псевдоним2", "на русском"],
  "category": "категория",
  "domain_sources": ["https://ссылка/на/список/доменов.txt"],
  "domains": ["domain.com", "api.domain.com"],
  "description": "Краткое описание (опционально)"
}
```

### Поля

| Поле | Обязательное | Описание |
|------|:---:|---------|
| `aliases` | ✓ | Псевдонимы для поиска (строчные) |
| `category` | ✓ | Категория из списка ниже |
| `domain_sources` | — | URL-ы для скачивания списков доменов |
| `domains` | — | Встроенный список доменов |
| `description` | — | Описание сервиса |

> Можно использовать `domain_sources`, `domains` или оба вместе — они объединяются.

### Категории

| Ключ | Описание |
|------|---------|
| `media` | Видео, музыка, стриминг |
| `social` | Социальные сети |
| `communication` | Мессенджеры |
| `gaming` | Игры, игровые платформы |
| `tech` | Технологии, облачные сервисы |
| `ai` | Искусственный интеллект |
| `design` | Дизайн, графика |
| `productivity` | Продуктивность, офис |
| `education` | Образование |
| `commerce` | Торговля, маркетплейсы |
| `finance` | Финансы, криптовалюты |
| `privacy` | Приватность, VPN |
| `torrents` | Торрент-трекеры |
| `ru` | Российские сервисы |
| `iot` | IoT, умный дом |
| `fitness` | Спорт, фитнес |
| `storage` | Файловые хранилища |
| `other` | Прочее |

## Пример: добавить Notion

```json
"Notion": {
  "aliases": ["notion", "ноушн"],
  "category": "productivity",
  "domains": ["notion.so", "notion.site", "api.notion.com"]
}
```

## Пример: сервис с внешним списком доменов

```json
"MyService": {
  "aliases": ["myservice", "мойсервис"],
  "category": "tech",
  "domain_sources": [
    "https://raw.githubusercontent.com/example/repo/main/domains.txt"
  ],
  "domains": ["myservice.com"]
}
```

## Порядок внесения изменений

1. Форкните репозиторий
2. Отредактируйте `services.json`
3. Проверьте: `mydomainmapper --search <название>`
4. Создайте Pull Request с описанием добавленного сервиса
