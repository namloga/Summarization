# Суммаризация отзывов (Frontend + Backend)

Проект для суммаризации отзывов на русском языке.  
Пользователь может ввести текст вручную или загрузить CSV‑файл с отзывами, а система вернёт краткую сводку.

## Структура проекта

```text
Summarization/
├── backend/   # API и модель ruT5 для суммаризации
├── frontend/  # Веб-интерфейс (HTML/CSS/JS)
└── DEPLOY.md  # Инструкция по деплою
```

### Backend (папка `backend/`)

- Написан на **FastAPI**.
- Использует модель **ruT5** для суммаризации текста.
- Основные возможности:
  - `POST /summarize` — суммаризация текста или списка текстов.
  - `POST /summarize-file` — суммаризация отзывов из CSV/JSON.
  - `GET /health` — проверка, что сервис работает.

Запуск локально:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python -m src.main
```

### Frontend (папка `frontend/`)

Простой веб‑интерфейс на чистом HTML/CSS/JS:

- Поле для ввода текста и кнопка «Суммаризовать».
- Загрузка CSV‑файла с отзывами.
- Отображение результата и количества слов.

Запуск локально:

```bash
cd frontend
python serve.py
```

После запуска:

- Frontend: `http://localhost:5500`
- Backend должен быть запущен на `http://localhost:8000`.

Настройка URL backend — в `frontend/config.js`:

```javascript
const API_CONFIG = {
  BASE_URL: "http://localhost:8000", // заменить на URL продакшн-backend при деплое
  ENDPOINTS: {
    HEALTH: "/health",
    SUMMARIZE: "/summarize",
    SUMMARIZE_FILE: "/summarize-file",
  },
};
```

### Деплой

Краткая инструкция по деплою backend и frontend находится в файле `DEPLOY.md`.
