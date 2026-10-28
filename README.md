# viewpie Layout Engine

> ## Авторство
>
> Проект **сгенерирован AI-ассистентом Qwen (Alibaba Cloud)**
> по техническому заданию пользователя как вспомогательный
> компонент для модифицированной версии [viewpie](https://github.com/snoack/viewpie).
>
> Проект не связан с автором оригинального viewpie
> (Sebastian Noack).
>
> ## Связанные проекты
>
> - [viewpie (оригинал)](https://github.com/snoack/viewpie)
>
> ## Лицензия
>
> GPL-3.0-or-later

Python-сервис (FastAPI) для валидации, нормализации и автогенерации
раскладок видеостены под жёсткое ограничение viewpie: **сетка обязана
быть квадратной** (N×N, N ∈ {3..8}).

Движок принимает произвольную текстовую сетку (`"1 1 2 3\n..."`),
приводит её к квадрату (дополнение точками `.`), проверяет, что каждая
камера занимает ровно прямоугольник (L-формы и «дырки» — ошибка),
и выдаёт готовый `viewpie.yaml`.

## Возможности

- **Парсинг** текстовых раскладок любой конфигурации (`parser.py`)
- **Нормализация** неквадратных сеток к N×N минимуму 3×3, максимуму 8×8 (`normalizer.py`)
- **Валидация** прямоугольности блоков, выхода за границы и пересечений (`validator.py`)
- **Авто-размещение** камер произвольных размеров жадным алгоритмом (`auto_placer.py`)
- **Генерация** полного `viewpie.yaml` (секции `display`, `feeds`, `panels`, `defaults`) (`generator.py`)
- **REST API** для всех операций + CRUD камер/панелей/настроек (`api_server.py`)
- **HTTP-клиент** к модифицированному viewpie-деемону с ретраями (`viewpie_client.py`)
- 94 теста, покрытие ядра ≈ 99%

## Быстрый старт

```bash
pip install .
uvicorn viewpie_layout_engine.api_server:app --host 0.0.0.0 --port 8000
```

Или через Docker:

```bash
docker build -t viewpie-layout-engine .
docker run -p 8000:8000 \
  -e VIEWPIE_BASE_URL=http://192.168.1.50:8080 \
  viewpie-layout-engine
```

Переменные окружения клиента viewpie:

| Переменная         | По умолчанию              | Описание                          |
|--------------------|---------------------------|-----------------------------------|
| `VIEWPIE_BASE_URL` | `http://127.0.0.1:8080`   | Базовый URL viewpie-демона        |
| `VIEWPIE_TIMEOUT`  | `5`                       | Таймаут запроса, сек              |
| `VIEWPIE_RETRIES`  | `3`                       | Попыток при 5xx                   |

## Примеры API

### Валидация раскладки

```bash
curl -s -X POST http://localhost:8000/api/layout/validate \
  -H 'Content-Type: application/json' \
  -d '{
    "panel_id": "main",
    "panel_name": "Main wall",
    "layout_text": "1 1 2 3\n1 1 4 5\n6 7 8 9\n10 11 12 13"
  }'
```

Ответ: `grid_size=4`, 13 блоков (камера `1` — блок 2×2), `errors: []`.

### Неквадратная сетка → автодополнение

Вход `"1 1 2 3\n4 5 6 7"` (2×4) нормализуется к 4×4:

```
1 1 2 3
4 5 6 7
. . . .
. . . .
```

В ответе появится предупреждение о дополнении пустыми ячейками.

### L-форма → ошибка

```json
{"layout_text": "1 1 2\n1 2 2\n3 4 5"}
```

→ HTTP 422 со структурированным JSON: блок `'1'` не является прямоугольником
(`InvalidBlockError`).

### Авто-размещение камер

```bash
curl -s -X POST http://localhost:8000/api/layout/auto \
  -H 'Content-Type: application/json' \
  -d '{
    "panel_id": "main",
    "grid_size": 4,
    "cameras": [
      {"name": "gate",  "width": 2, "height": 2},
      {"name": "yard",  "width": 1, "height": 1},
      {"name": "lobby", "width": 1, "height": 2}
    ]
  }'
```

Камеры сортируются по площади (убывание) и размещаются жадно
сверху-вниз, слева-направо. Если всё не помещается — `TooManyCamerasError`.

### Генерация и применение YAML

```bash
# только сгенерировать viewpie.yaml
curl -s -X POST http://localhost:8000/api/layout/generate ...

# сгенерировать и отправить в viewpie (applied=true)
curl -s -X POST http://localhost:8000/api/layout/apply ...
```

### Прочие эндпоинты

```
GET/POST/DELETE  /api/cameras[/{name}]
GET/POST/PUT/DELETE /api/panels[/{id}]
POST             /api/panels/{id}/activate
GET/PUT          /api/settings
GET              /api/status     # прокси к viewpie
GET              /health
```

Интерактивная документация: <http://localhost:8000/docs>.

## Использование как библиотеки

```python
from viewpie_layout_engine import parse_layout_text, normalize_to_square, validate_blocks

matrix, h, w = parse_layout_text("1 1 2 3\n4 5 6 7")
square, n = normalize_to_square(matrix, h, w)          # -> 4×4
blocks = validate_blocks(square, n)                    # -> {'1': Block(...), ...}
```

## Тесты

```bash
pip install -e ".[dev]"
pytest --cov=viewpie_layout_engine
```

## Структура проекта

```
viewpie_layout_engine/
├── models.py         # Pydantic v2 модели
├── exceptions.py     # Иерархия LayoutError
├── parser.py         # Парсинг текстовой сетки
├── normalizer.py     # Приведение к квадрату
├── validator.py      # Валидация блоков
├── auto_placer.py    # Автогенерация раскладок
├── generator.py      # Генерация viewpie.yaml
├── api_server.py     # FastAPI сервер
├── viewpie_client.py # HTTP-клиент к viewpie
└── tests/            # pytest, покрытие ≥ 90%
```

## Security

⚠️ **Проект сгенерирован AI (Qwen) и может содержать ошибки или
галлюцинации.** Перед использованием в production:

- Проведите код-ревью всеми разработчиками, причастными к эксплуатации.
- Запустите статический анализ: `ruff check .`, `mypy .`, `bandit -r .`
- Не выставляйте сервис наружу без аутентификации/Reverse-Proxy —
  API предполагает доверенную локальную сеть (Raspberry Pi).
- Логи сервиса не содержат URL потоков и иных конфиденциальных данных.
- Для репортов об уязвимостях используйте [Issues](https://github.com/).

## Лицензия

GPL-3.0-or-later. Оригинальный [viewpie](https://github.com/snoack/viewpie)
также распространяется под GPLv3+ и не аффилирован с этим проектом.
