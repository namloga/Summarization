# Деплой приложения «Суммаризация отзывов»

Инструкция по деплою **backend** (FastAPI + модель суммаризации) и **frontend** (веб-интерфейс) в продакшн-среду.

---

## Обзор

| Компонент | Технологии | Рекомендуемый деплой |
|------------|-----------|-------------|
| Backend    | FastAPI, uvicorn, PyTorch + ruT5 | **Render** (Web Service) или **Railway** |
| Frontend   | Статический HTML/CSS/JS | **Vercel**, **Netlify** или **Render Static** |

**Важно:** Backend требует достаточно RAM (≈ 2GB+) из-за ruT5 и PyTorch. На Render free tier сервис может «засыпать» после ~15 минут простоя; первый запрос после этого будет медленным (cold start).

---

## 1. Деплой backend (Render)

### Шаг 1: Загрузить код в GitHub

Убедитесь, что репозиторий имеет структуру:

```
Summarization/
├── backend/
│   ├── src/
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── index.html
│   ├── config.js
│   └── ...
└── DEPLOY.md
```

### Шаг 2: Создать Web Service на Render

1. Зайдите на [render.com](https://render.com) → зарегистрируйтесь / войдите.
2. **New** → **Web Service**.
3. Подключите GitHub-репозиторий (выберите **Summarization**).
4. Настройте:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python -m src.main`
   - **Environment:** добавьте переменные:
     - `PORT` — Render задаёт автоматически, вручную не требуется.
     - `RELOAD` = `0` (отключить auto-reload).
     - (Опционально) **большие файлы/много отзывов:** `SUMMARIZATION_MAX_FILE_ITEMS=5000`, `SUMMARIZATION_MAX_FILE_MB=50` — если нужно обрабатывать больше записей/крупные файлы; при долгих запросах может потребоваться увеличить таймаут (например, Render 300s).
5. Выберите инстанс (рекомендуется **Starter** и выше из‑за тяжёлой модели). На free tier может не хватить RAM.
6. **Create Web Service**. Дождитесь сборки и запуска; скопируйте URL вида `https://xxx.onrender.com`.

---

## 2. Деплой frontend (Vercel или Netlify)

### Способ A: Vercel

1. Зайдите на [vercel.com](https://vercel.com) → импортируйте GitHub‑репозиторий.
2. **Root Directory:** `frontend`.
3. **Framework Preset:** Other (static).
4. **Build:** оставить пустым (нужен только деплой статических файлов).
5. **Output Directory:** `.` или по умолчанию.
6. Deploy → получите URL вида `https://xxx.vercel.app`.

**Изменить URL backend:** после того как backend получил URL (например, `https://your-api.onrender.com`):

- В репозитории измените `frontend/config.js`: замените `'http://localhost:8000'` на `'https://your-api.onrender.com'` (в fallback‑значении, либо задайте `window.API_BASE_URL` до загрузки `config.js`).
- Commit + push → Vercel автоматически перезадеплоит.

### Способ B: Netlify

1. Зайдите на [netlify.com](https://netlify.com) → **Add new site** → **Import from Git**.
2. Выберите репозиторий; **Base directory:** `frontend`.
3. **Build command:** оставить пустым. **Publish directory:** `frontend` (или `/`, если base уже `frontend`).
4. Deploy. Затем измените `frontend/config.js`, как выше, и сделайте push.

### Способ C: Render (Static Site)

1. **New** → **Static Site**.
2. Репозиторий: тот же; **Root Directory:** `frontend`.
3. **Publish directory:** `.` (или `frontend`, если root — корень репозитория).
4. Deploy; затем измените `config.js`, чтобы он указывал на URL backend на Render.

---

## 3. Настроить frontend на backend

После того как backend запущен и у него есть URL (например, `https://summarization-api.onrender.com`):

**Способ 1 — изменить напрямую:** в `frontend/config.js`:

```javascript
BASE_URL: 'https://summarization-api.onrender.com',
```

(Если вы используете механизм `window.API_BASE_URL`, можно сделать production‑URL значением по умолчанию вместо `'http://localhost:8000'`.)

**Способ 2 — переопределить при деплое:** в `frontend/index.html` добавьте **перед** `<script src="config.js">`:

```html
<script>window.API_BASE_URL = 'https://your-backend-url.onrender.com';</script>
```

После этого перезадеплойте frontend.

---

## 4. Проверка после деплоя

1. **Backend:** откройте `https://your-backend.onrender.com/health` → должен вернуться JSON `{"status":"ok",...}`.
2. **Backend docs:** `https://your-backend.onrender.com/docs`.
3. **Frontend:** откройте URL Vercel/Netlify/Render → введите текст → **Суммаризовать** → проверьте результат (первый запрос может быть медленным из‑за cold start + загрузки модели).

---

## 5. Примечания

- **CORS:** backend настроен с `allow_origins=["*"]`, поэтому frontend с другого домена сможет вызывать API.
- **Cold start (Render free):** сервис «засыпает» после ~15 минут простоя; первый запрос потом может занять 30–60 секунд.
- **RAM:** если backend падает по out of memory, увеличьте инстанс (Starter и выше) или рассмотрите более лёгкую модель (переменная `SUMMARIZATION_MODEL` в backend).

Если вы выберете конкретную платформу (только Render, только Railway и т. п.), можно упростить шаги под один конкретный сценарий деплоя.
