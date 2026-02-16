# Backend суммаризации отзывов

Этот backend принимает отзывы (текст или CSV/JSON) и возвращает краткую сводку на русском языке.  
API написан на **FastAPI**, для суммаризации используется модель **ruT5**.

## Что умеет backend

- Принимать один длинный текст и возвращать его краткую сводку.
- Принимать список текстов и возвращать сводку для каждого.
- Принимать файл CSV/JSON с отзывами и возвращать:
  - одну общую сводку (объединённые отзывы),
  - либо сводку по каждой записи (в зависимости от параметров).
- Проверять статус сервиса (endpoint `/health`).

## Как запустить локально

Требования: **Python 3.10+**, желательно отдельное виртуальное окружение.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux/macOS

pip install -r requirements.txt
python -m src.main             # API: http://localhost:8000
```

После запуска backend будет доступен по адресу:

- API: `http://localhost:8000`
- Документация Swagger: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Основные endpoints

- `GET /health` — проверка, что сервис запущен.
- `POST /summarize` — суммаризация текста или списка текстов.
- `POST /summarize-file` — суммаризация отзывов из файла CSV/JSON.

Форматы запросов и ответов можно посмотреть в `/docs` (Swagger UI).

## Структура backend

```text
backend/
├── src/
│   ├── api/          # FastAPI: роуты и схема (Pydantic-модели)
│   ├── preprocessing # Загрузка и очистка данных из CSV/JSON
│   ├── summarizer    # Pipeline суммаризации, ruT5-модель
│   └── main.py       # Точка входа (uvicorn)
├── data/             # Примеры файлов с отзывами (CSV/JSON)
├── tests/            # Тесты API и pipeline
└── requirements.txt  # Зависимости Python
```
