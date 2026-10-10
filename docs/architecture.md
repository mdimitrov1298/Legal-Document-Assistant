# Архитектура на прототипа Legal Document Assistant

> Документ за **Глава 4** и приложението към дипломната работа.  
> Описва текущата реализация в хранилището `mdimitrov1298/legal` (клон `feat/prototype-skeleton`).  
> Кратка техническа бележка на английски: [`ARCHITECTURE.md`](../ARCHITECTURE.md) в корена на проекта.  
> Инструкции за стартиране: [`README.md`](../README.md).

---

## 1. Цел и обхват

Прототипът е **локална** система за работа с текстове по „дела“ (казусни документи) с поток:

**качване → индексиране (chunk + embeddings + Chroma) → резюме → проверка на твърдение**

| В обхвата | Извън обхвата |
|-----------|----------------|
| Извличане на текст от PDF/TXT (**само български** казусни документи) | Правна интерпретация |
| RAG резюме с цитати към chunk-ове | Изграждане на правни хронологии / „timelines“ като анализ |
| Проверка на фактическо твърдение (supported / denied / inconclusive) с директни цитати | Правна класификация на дела |
| Локален LLM чрез Ollama | Правни заключения / съвети |
| Локално съхранение на данни по казуса | Облачни LLM API за съдържанието на документите |

Език на казусните материали: **български** (PDF/TXT). Английски документи по дела не се поддържат като целеви вход.

Целева машина: около **16 GB RAM** (без допускане за висока VRAM). По подразбиране генеративният модел е `qwen2.5:7b` (`OLLAMA_MODEL`).

---

## 2. Компоненти на системата

### 2.1. Общ изглед

```
┌─────────────────────┐     HTTP /api/*      ┌──────────────────────────┐
│  React + Vite + TS  │ ──────────────────►  │  FastAPI (uvicorn)       │
│  (frontend :5173)   │ ◄──────────────────  │  backend/app             │
└─────────────────────┘   JSON / multipart   └────────────┬─────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────┐
                    ▼                                     ▼                     ▼
           ┌────────────────┐                  ┌──────────────────┐   ┌─────────────────┐
           │  Файлово       │                  │  Chroma          │   │  Ollama         │
           │  хранилище     │                  │  PersistentClient│   │  :11434         │
           │  data/uploads  │                  │  data/chroma     │   │  /api/generate  │
           │  cases_index   │                  │  (векторен индекс│   │  (/api/embeddings│
           └────────────────┘                  │   по case_id)    │   │   по избор)     │
                                               └──────────────────┘   └─────────────────┘
```

### 2.2. Frontend (React + Vite + TypeScript)

- Минимален UI за целия поток: създаване на казус, качване на PDF/TXT, ingest, summarize, verify.
- Vite проксира `/api` към backend на порт `8000`.
- Статус панел показва: дали API е онлайн, дали **Ollama е достижим**, кой е **активният модел** (`OLLAMA_MODEL`), дали моделът е изтеглен (`ollama_model_present`), както и настройките за embeddings.

### 2.3. Backend (FastAPI)

Приложението е организирано в `backend/app/`:

| Модул | Роля |
|-------|------|
| `main.py` | FastAPI приложение, CORS |
| `config.py` | Настройки от `.env` (pydantic-settings) |
| `api/routes.py` | HTTP крайни точки `/api/...` |
| `models/schemas.py` | Договори за заявки/отговори |
| `services/storage.py` | Казуси + качени файлове на диск |
| `services/documents.py` | Извличане на текст (pypdf / TXT) |
| `services/chunking.py` | Припокриващи се текстови chunk-ове |
| `services/embeddings.py` | MiniLM / Ollama nomic / hash stub |
| `services/vectorstore.py` | Персистентен Chroma по казус |
| `services/ollama_client.py` | Интерфейс към Ollama + stub при недостъпност |
| `services/pipeline.py` | Оркестрация: ingest → summarize → verify |

### 2.4. Chroma (локален векторен склад)

- Използва се `chromadb.PersistentClient` с път `CHROMA_PATH` (по подразбиране `./data/chroma`).
- По една колекция на казус (`case_{id_без_тирета}`).
- Векторите и текстовете на chunk-овете се записват на диск и **оцеляват рестарт** на API процеса.
- Ingest **не изисква** Ollama, когато embeddings са чрез sentence-transformers (или hash stub).

### 2.5. Ollama (локален LLM)

- Единственият runtime за генерация върху съдържанието на документите.
- По подразбиране: `OLLAMA_MODEL=qwen2.5:7b`.
- Извикване: `POST {OLLAMA_BASE_URL}/api/generate` (`stream: false`), с опционален `system` prompt.
- При грешка / timeout / празен отговор и `OLLAMA_STUB_ON_UNAVAILABLE=true`: връщат се **структурирани stub** отговори (`stubbed: true`), за да остане API/UI използваеми.
- Health: `GET /api/tags` за reachability и списък на инсталираните модели.

### 2.6. Embeddings

Конфигурират се с `EMBEDDING_BACKEND` + `EMBEDDING_MODEL`:

| Backend | Типичен модел | Изисква Ollama? | Бележка |
|---------|---------------|-----------------|---------|
| `sentence-transformers` (**по подразбиране**) | `sentence-transformers/all-MiniLM-L6-v2` на **CPU** | Не | ~малък модел; съвместим с 7B Ollama на ~16 GB |
| `ollama` (опционално) | `nomic-embed-text` чрез `POST /api/embeddings` | Да | Алтернатива; при неуспех → fallback към hash stub |
| `hash_stub` | n/a | Не | Детерминиран stub за CI / офлайн |

---

## 3. Тръбопровод (pipeline)

### 3.1. Upload (качване)

1. `POST /api/cases` — създава казус (метаданни в `data/cases_index.json`).
2. `POST /api/cases/{id}/documents` — multipart PDF или TXT → файлът се записва в `data/uploads/{case_id}/`.

Поддържани формати: `.pdf`, `.txt` (и близки текстови типове). **Казусните документи са само на български език** — английски case materials не са в обхвата на прототипа.

### 3.2. Ingest (chunk → embed → store)

`POST /api/cases/{id}/ingest`:

1. Извличане на plain text (`documents.py`).
2. Разбиване на припокриващи се chunk-ове (`CHUNK_SIZE` / `CHUNK_OVERLAP`).
3. Изчисление на embeddings според избрания backend.
4. `upsert` в персистентната Chroma колекция за казуса.
5. Маркиране на казуса като `ingested`.

Отговорът включва брой chunk-ове, `embedding_backend`, `chroma_path`, флаг `persisted`.

### 3.3. Summarize (резюме с цитати)

`POST /api/cases/{id}/summarize`:

1. Retrieval: top-k chunk-ове от Chroma (заявка на база заглавието / ключови факти).
2. Промпт към Ollama: фактическо резюме **само** по предоставените откъси; JSON с `summary` + `citation_indices`.
3. Отговор към клиента: `summary`, `citations[]` (`document_id`, `document_filename`, `chunk_id`, `quote`, `relevance`), `stubbed`, `model`.

При недостъпен Ollama: stub резюме, изградено от извлечените chunk-ове, със същите цитати (данните остават локални).

### 3.4. Verify (проверка на твърдение)

`POST /api/cases/{id}/verify` с `{ "claim": "...", "top_k": 5 }`:

1. Retrieval по текста на твърдението.
2. Ollama връща JSON: `verdict` ∈ {`supported`, `denied`, `inconclusive`}, `rationale`, индекси на подкрепящи/отричащи цитати.
3. Отговор: `supporting_quotes`, `denying_quotes`, плюс `retrieved_quotes` (всички извлечени chunk-ове като доказателствен контекст).

Цитатите са **директни откъси** от индексираните документи (не свободно измислен текст от модела като „източник“).

### 3.5. Диаграма на потока

```
[UI] upload PDF/TXT
        │
        ▼
[storage] ──► data/uploads + cases_index.json
        │
        ▼ ingest
[extract] → [chunk] → [embed] → [Chroma persist]
        │
        ├──────────► summarize: retrieve → Ollama → summary + citations
        │
        └──────────► verify:    retrieve → Ollama → verdict + quotes
```

---

## 4. HTTP API (актуален набор)

| Метод | Път | Описание |
|-------|-----|----------|
| `GET` | `/api/health` | Статус; Ollama reachability; активен модел; списък модели; embeddings |
| `POST` | `/api/cases` | Нов казус |
| `GET` | `/api/cases` | Списък казуси |
| `GET` | `/api/cases/{id}` | Детайли за казус |
| `POST` | `/api/cases/{id}/documents` | Качване на документ |
| `POST` | `/api/cases/{id}/ingest` | Индексиране |
| `POST` | `/api/cases/{id}/summarize` | Резюме + цитати |
| `POST` | `/api/cases/{id}/verify` | Проверка на твърдение |

Интерактивна документация при стартиран backend: `http://127.0.0.1:8000/docs`.

---

## 5. Променливи на средата

Шаблон: [`.env.example`](../.env.example). Зареждат се чрез `backend/app/config.py` (препоръчително стартиране на API от **корена** на хранилището, за да се резолвнат относителните пътища `./data`).

### 5.1. Ollama / генерация

| Променлива | Подразбиране | Значение |
|------------|--------------|----------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Базов URL на локалния Ollama HTTP API |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Активен генеративен модел (трябва да е `ollama pull`-нат) |
| `OLLAMA_STUB_ON_UNAVAILABLE` | `true` | Stub при недостъпен Ollama / timeout / грешка |
| `OLLAMA_HEALTH_TIMEOUT` | `3.0` | Timeout за `/api/tags` (секунди) |
| `OLLAMA_GENERATE_TIMEOUT` | `120.0` | Timeout за `/api/generate` (7B на CPU може да е бавен) |

### 5.2. Embeddings и chunking

| Променлива | Подразбиране | Значение |
|------------|--------------|----------|
| `EMBEDDING_BACKEND` | `sentence-transformers` | `sentence-transformers` \| `ollama` \| `hash_stub` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Идентификатор на модела за избрания backend |
| `EMBEDDING_DEVICE` | `cpu` | Устройство за sentence-transformers |
| `CHUNK_SIZE` | `800` | Размер на chunk (символи) |
| `CHUNK_OVERLAP` | `120` | Припокриване между chunk-ове |

### 5.3. Съхранение и API

| Променлива | Подразбиране | Значение |
|------------|--------------|----------|
| `DATA_DIR` | `./data` | Индекс на казуси и runtime данни |
| `CHROMA_PATH` | `./data/chroma` | Персистентен векторен склад (gitignore) |
| `UPLOAD_DIR` | `./data/uploads` | Качени файлове (gitignore) |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Слушане на HTTP сървъра |
| `CORS_ORIGINS` | Vite localhost URL-и | Разрешени origin-и за браузъра |

Примерни демо файлове (синтетични, не реални съдебни актове): [`samples/`](../samples/).

---

## 6. Ограничения и дизайн решения

### 6.1. Локални данни

- Съдържанието на казусните документи **не се изпраща** към облачни LLM API.
- Генерацията минава само през локален Ollama.
- Файловете и Chroma индексът остават под `data/` на машината на потребителя.

### 6.2. Поведение при недостъпен Ollama

- **Ingest** с подразбиращите embeddings (MiniLM / hash stub) продължава да работи.
- **Summarize / verify** връщат структурирани stub отговори с `stubbed: true`, като цитатите към извлечените chunk-ове се запазват, доколкото има индексирани данни.
- UI показва ясно дали Ollama е reachable и кой модел е активен.

### 6.3. Без правна интерпретация и заключения

Системните промптове и UI текстовете изрично ограничават модела:

- да резюмира / проверява **само** факти от предоставените откъси;
- да **не** дава правни съвети, класификации или правни заключения;
- да **не** изгражда правни хронологии като аналитичен продукт.

Прототипът е изследователски/учебен инструмент, **не** продукт за юридически съвети.

### 6.4. Памет (~16 GB)

- Един 7B (или подобен) Ollama модел наведнъж.
- Embeddings по подразбиране на CPU (MiniLM), за да остане запас за LLM.
- Не се зарежда втори голям LLM само за embeddings, освен ако изрично не се избере `EMBEDDING_BACKEND=ollama` (тогава embeddings моделът също се обслужва от Ollama).

---

## 7. Структура на хранилището (обобщение)

```
legal/
├── docs/architecture.md     ← този документ (Глава 4 / приложение)
├── ARCHITECTURE.md          ← кратка EN бележка за разработчици
├── README.md                ← локално стартиране
├── .env.example
├── samples/                 ← синтетични демо документи **само на български**
├── data/                    ← runtime (gitignore)
├── backend/app/             ← FastAPI + services
└── frontend/                ← React + Vite + TypeScript
```

---

## 8. Заключение (за главата)

Архитектурата следва класически **локален RAG** шаблон: уеб UI → REST API → персистентен векторен индекс + локален LLM. Разделението между **ingest без Ollama** (MiniLM) и **generate чрез Ollama** позволява индексиране и демонстрация дори когато генеративният модел временно липсва, при запазване на изискването данните по казуса да останат на локалната машина и без претенция за правни заключения.
