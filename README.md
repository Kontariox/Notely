# Notely 🎓 — Automatyczne Przetwarzanie Nagrań Lekcji na Uporządkowane Notatki AI

**Notely** to kompletna, modularna i produkcyjna aplikacja w języku Python przeznaczona do automatycznego przekształcania nagrań audio i wideo z pojedynczych lekcji szkolnych oraz akademickich w przejrzyste, usystematyzowane notatki, zestawienia pojęć oraz harmonogram sprawdzianów i zadań z integracją z Google Calendar.

---

## 🌟 Kluczowe Funkcjonalności

1. **Obsługa audio i wideo**: Akceptuje formaty MP3, WAV, M4A, AAC, MP4, MOV, WEBM (automatyczna ekstrakcja i normalizacja strumienia audio do 16 kHz mono WAV przy użyciu FFmpeg).
2. **Elastyczna transkrypcja**:
   - **Whisper large-v3** (oficjalna biblioteka OpenAI),
   - **faster-whisper** (oparty o CTranslate2 — do 4x szybszy i znacznie oszczędniejszy pamięciowo).
   - Timestampy, segmenty wypowiedzi, automatyczne wykrywanie języka.
3. **Analiza AI oparta o NVIDIA NIM**:
   - Bezpieczny dla limitu **40 RPM** (Requests Per Minute) globalny mechanizm Sliding Window + Request Queue + Exponential Backoff z obsługą HTTP 429.
   - Pipeline chunkingu tekstu z zachowaniem granic zdań i segmentów.
   - Generowanie tematów, streszczeń, kluczowych pojęć, definicji, przykładów oraz sekcji specyficznych dla przedmiotu (wzory dla matematyki, motywy dla polskiego, procesy dla biologii).
   - Rygorystyczny zakaz halucynacji: AI nie dopowiada faktów spoza nagrania i oznacza niepewności.
4. **Wykrywanie wydarzeń i dat względnych**:
   - Ekstrakcja sprawdzianów, kartkówek, prac domowych, lektur, prezentacji i projektów z oceną pewności (`confidence`).
   - Zachowywanie i bezpieczne wyliczanie dat względnych (np. „za dwa tygodnie w piątek”, „w następny wtorek”) na podstawie daty lekcji.
5. **Opcjonalna integracja z Google Calendar**:
   - Pełna autoryzacja OAuth 2.0 (brak haseł w aplikacji).
   - Podgląd wykrytych wydarzeń i wybór pozycji przed ich utworzeniem w kalendarzu.
   - Bezpieczne odłączanie konta i usuwanie tokenów.
6. **Wszechstronny eksport i przygotowanie dla zewnętrznych modeli AI**:
   - Eksport transkrypcji do: `.txt`, `.md`, `.json`, `.srt` (napisy SubRip), `.vtt` (WebVTT).
   - Eksport uporządkowanej notatki do `.docx` (Microsoft Word) oraz `.md`.
   - Moduł *„Przygotuj materiał do zewnętrznego AI”*: kopiowanie do schowka, automatyczne dzielenie długiej transkrypcji na ponumerowane części (`PART 1/N`) z gotowym promptem.
7. **Historia i baza danych**:
   - Baza danych SQLite (aiosqlite) / PostgreSQL przez SQLAlchemy.
   - Przeglądanie historii lekcji, ponowne otwieranie i pobieranie materiałów.
8. **Nowoczesny interfejs webowy**:
   - Estetyczny, responsywny dashboard (SPA) z paskiem postępu na żywo, kartami wydarzeń i panelem ustawień domyślnych.

---

## 🏛 Architektura Systemu

```text
                               +-----------------------------+
                               |     Użytkownik / Przeglądarka|
                               +--------------+--------------+
                                              | HTTP / SSE / REST
                                              v
+-----------------------------------------------------------------------------------------+
|                                    BACKEND (FastAPI)                                    |
|                                                                                         |
|  +--------------------+   +---------------------+   +--------------------------------+  |
|  |   Upload & Audio   |   |    Baza Danych      |   |          Google OAuth          |  |
|  |     Validation     |   | (SQLAlchemy/SQLite) |   |        & Calendar Sync         |  |
|  +---------+----------+   +----------+----------+   +---------------+----------------+  |
|            |                         |                              |                   |
|            v                         |                              |                   |
|  +--------------------+              |                              |                   |
|  |  Audio Conversion  |              |                              |                   |
|  |  (FFmpeg Service)  |              |                              |                   |
|  +---------+----------+              |                              |                   |
|            |                         |                              |                   |
|            v                         |                              |                   |
|  +--------------------+              |                              |                   |
|  |    TRANSKRYPCJA    +--------------+ (Niezależny zapis transkrypcji)                  |
|  |  faster-whisper /  |                                                                 |
|  |  Whisper large-v3  |                                                                 |
|  +---------+----------+                                                                 |
|            |                                                                            |
|            v                                                                            |
|  +--------------------+                                                                 |
|  | Segment & Sentence |                                                                 |
|  |     Chunking       |                                                                 |
|  +---------+----------+                                                                 |
|            |                                                                            |
|            v                                                                            |
|  +--------------------+   +----------------------------------------------------------+  |
|  |     ANALIZA AI     |   |               RateLimiter (40 RPM Guard)                 |  |
|  |  (NVIDIA NIM API)  +<--+  - Sliding Window (max 38 req/60s)                       |  |
|  |                    |   |  - Exponential Backoff & Jitter                          |  |
|  +---------+----------+   |  - Obsługa HTTP 429 & Retry-After                        |  |
|            |              +----------------------------------------------------------+  |
|            v                                                                            |
|  +--------------------+                                                                 |
|  | Ekstrakcja Danych: |                                                                 |
|  |  - Wydarzenia/Daty |                                                                 |
|  |  - Temat & Synteza |                                                                 |
|  |  - Finalna Notatka |                                                                 |
|  +---------+----------+                                                                 |
|            |                                                                            |
|            v                                                                            |
|  +--------------------+                                                                 |
|  |    EKSPORT DANYCH  | ---> .TXT, .MD, .DOCX, .JSON, .SRT, .VTT, AI Multipart (1/N)    |
|  +--------------------+                                                                 |
+-----------------------------------------------------------------------------------------+
```

---

## 📁 Struktura Katalogów

```text
Notely/
├── app/
│   ├── main.py                   # Główny punkt startowy FastAPI, routing, CORS i statyki
│   ├── config.py                 # Konfiguracja środowiskowa (Pydantic BaseSettings)
│   ├── database/
│   │   ├── session.py            # Asynchroniczny silnik SQLAlchemy i sesje
│   │   ├── models.py             # Modele ORM: Lesson, UserSettings, GoogleOAuthToken
│   │   └── repository.py         # Repozytoria operacji na bazie danych
│   ├── services/
│   │   ├── audio.py              # Konwersja FFmpeg, ekstrakcja audio, walidacja
│   │   └── pipeline.py           # Główny orkiestrator przetwarzania lekcji
│   ├── transcription/
│   │   ├── base.py               # Abstrakcyjny interfejs TranscriptionProvider & modele segmentów
│   │   ├── faster_whisper_provider.py # Implementacja faster-whisper z detekcją sprzętu
│   │   ├── whisper_provider.py   # Implementacja OpenAI Whisper
│   │   └── factory.py            # Fabryka instancjonująca odpowiedni silnik
│   ├── ai/
│   │   ├── base.py               # Abstrakcyjny interfejs AIProvider i struktura wyników
│   │   ├── rate_limiter.py       # Globalny strażnik limitu 40 RPM (Sliding Window + Retry)
│   │   ├── chunking.py           # Inteligentne dzielenie transkrypcji po granicach zdań
│   │   ├── date_resolver.py      # Wyliczanie dat względnych na podstawie daty lekcji
│   │   ├── prompts.py            # Dedykowane szablony promptów anty-halucynacyjnych
│   │   └── nvidia_nim.py         # Klient NVIDIA NIM z bezpiecznym parserem JSON
│   ├── calendar/
│   │   └── google_calendar.py    # Obsługa Google OAuth 2.0 i synchronizacji zdarzeń
│   ├── exports/
│   │   ├── srt_exporter.py       # Generowanie napisów .srt i .vtt z timestampami
│   │   ├── docx_exporter.py      # Generowanie sformatowanych dokumentów Word (.docx)
│   │   └── ai_bundle.py          # Formatowanie materiałów pod zewnętrzne LLM
│   ├── api/
│   │   ├── schemas.py            # Schematy Pydantic żądań i odpowiedzi
│   │   ├── routes_upload.py      # Endpoint uploadu nagrania i uruchomienia pipeline'u
│   │   ├── routes_lessons.py     # Odczyt lekcji, historia, status na żywo, usuwanie
│   │   ├── routes_settings.py    # Zapis i odczyt globalnych ustawień użytkownika
│   │   ├── routes_calendar.py    # Logowanie Google OAuth, callback, sync wydarzeń
│   │   ├── routes_export.py      # Endpointy pobierania plików (txt, md, json, srt, vtt, docx)
│   │   └── routes_ai_prep.py     # Przygotowanie promptów i danych pod zewnętrzne AI
│   ├── static/
│   │   ├── css/style.css         # Nowoczesny arkusz stylów UI
│   │   └── js/app.js             # Skrypt frontendu SPA (pasek postępu, schowek, sync)
│   └── templates/
│       └── index.html            # Główny szablon dashboardu
├── data/
│   ├── uploads/                  # Bezpieczny magazyn przesłanych nagrań
│   └── processed/                # Folder roboczy przetworzonego audio
├── tests/
│   ├── fixtures/
│   │   └── sample_transcripts.py # Realistyczne transkrypcje testowe z historii i matematyki
│   ├── test_chunking.py          # Testy podziału tekstu i segmentów
│   ├── test_rate_limiter.py      # Testy limitera 40 RPM i mechanizmu ponawiania
│   ├── test_nim_parser.py        # Testy parsera i recoverera JSON
│   ├── test_event_detection.py   # Testy kalkulacji dat względnych
│   ├── test_exports.py           # Testy generowania SRT, VTT, DOCX, Bundle
│   ├── test_database.py          # Testy repozytorium bazy danych
│   └── test_api.py               # Testy integracyjne endpointów FastAPI
├── Dockerfile                    # Konteneryzacja wieloetapowa z FFmpeg
├── docker-compose.yml            # Konfiguracja Docker Compose (CPU i NVIDIA GPU)
├── requirements.txt              # Wymagane zależności Python
├── pytest.ini                    # Konfiguracja środowiska testowego pytest
├── .env.example                  # Szablon zmiennych środowiskowych
└── README.md                     # Kompletna dokumentacja projektu
```

---

## ⚙️ Wymagania

- **System operacyjny**: Linux, macOS, Windows (WSL2 zalecane).
- **Python**: 3.10, 3.11 lub 3.12 (zalecany Python 3.12).
- **FFmpeg**: Wymagany do konwersji audio i odczytu długości nagrań.
- **GPU (opcjonalnie)**: Karta graficzna NVIDIA z obsługą CUDA (dla przyspieszenia transkrypcji). W przypadku braku GPU, aplikacja automatycznie działa w trybie **CPU**.

---

## 🚀 Instalacja Krok po Kroku

### 1. Klonowanie repozytorium i utworzenie środowiska wirtualnego

```bash
cd /home/wojtek/PycharmProjects/Notely
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalacja FFmpeg

- **Ubuntu / Debian**:
  ```bash
  sudo apt update
  sudo apt install -y ffmpeg
  ```
- **macOS (Homebrew)**:
  ```bash
  brew install ffmpeg
  ```
- **Windows (Chocolatey / Scoop)**:
  ```powershell
  choco install ffmpeg
  ```

Zweryfikuj instalację:
```bash
ffmpeg -version
```

### 3. Instalacja bibliotek Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Opcjonalnie zainstaluj wybrany silnik transkrypcji:
```bash
# Zalecany: szybki i lekki faster-whisper
pip install faster-whisper

# Lub oficjalny pakiet OpenAI Whisper:
pip install openai-whisper
```

---

## 🔑 Konfiguracja Środowiska (.env)

Skopiuj szablon `.env.example` do `.env`:

```bash
cp .env.example .env
```

Edytuj plik `.env` i wprowadź dane konfiguracyjne:

```env
# Tryb aplikacji: development / production
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

# NVIDIA NIM API (Pobierz darmowy klucz z https://build.nvidia.com)
NVIDIA_API_KEY=nvapi-twoj_klucz_tutaj
NVIDIA_NIM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# Silnik transkrypcji: faster-whisper lub whisper
TRANSCRIPTION_ENGINE=faster-whisper
WHISPER_MODEL=large-v3
# WHISPER_DEVICE: auto, cuda lub cpu
WHISPER_DEVICE=auto
# WHISPER_COMPUTE_TYPE: auto, int8, float16, float32
WHISPER_COMPUTE_TYPE=auto
WHISPER_LANGUAGE=pl

# Prywatność i czyszczenie
DELETE_SOURCE_AFTER_PROCESSING=false

# Google Calendar OAuth 2.0 (Opcjonalnie)
GOOGLE_CLIENT_ID=twoj_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=twoj_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/calendar/callback
GOOGLE_CALENDAR_AUTO_ADD=false

# Baza danych
DATABASE_URL=sqlite+aiosqlite:///./data/notely.db
```

---

## 🛡️ Ograniczenie NVIDIA NIM — 40 RPM (Requests Per Minute)

Aplikacja posiada wbudowany, globalny mechanizm `RateLimiter` (`app/ai/rate_limiter.py`):
- Oparty na algorytmie **Sliding Window Counter** połączonym z asynchroniczną kolejką zapytań.
- Skonfigurowany domyślnie na **38 zapytań na 60 sekund** (zostawia 5% bufor bezpieczeństwa poniżej twardego limitu 40 RPM).
- W przypadku wystąpienia kodu **HTTP 429** lub błędu serwera, mechanizm automatycznie stosuje **wykładnicze opóźnienie (exponential backoff z jitterem)** oraz odczytuje nagłówek `Retry-After`.
- Zapobiega to blokadzie klucza API podczas przetwarzania bardzo długich, podzielonych na wiele części lekcji.

---

## 🗓️ Konfiguracja Google Calendar (OAuth 2.0)

1. Wejdź do [Google Cloud Console](https://console.cloud.google.com/).
2. Utwórz nowy projekt (np. `Notely Edu`).
3. Przejdź do **APIs & Services** -> **Enabled APIs & services** -> włącz **Google Calendar API**.
4. W sekcji **OAuth consent screen**:
   - Wybierz typ użytkownika: *External* (Zewnętrzny).
   - Podaj nazwę aplikacji i adres e-mail.
   - W sekcji uprawnień (Scopes) dodaj: `https://www.googleapis.com/auth/calendar.events` oraz `openid`, `email`.
   - W sekcji *Test users* dodaj swój adres e-mail Gmail.
5. W sekcji **Credentials** kliknij **Create Credentials** -> **OAuth client ID**:
   - Typ: *Web application*.
   - Authorized redirect URIs: `http://localhost:8000/api/calendar/callback`.
6. Skopiuj wygenerowany `Client ID` oraz `Client Secret` do pliku `.env`.
7. W aplikacji przejdź do zakładki **⚙ Ustawienia** i kliknij **Połącz z Google Calendar**.

---

## ▶️ Uruchamianie Aplikacji

### Uruchomienie lokalne

Możesz uruchomić aplikację bezpośrednio poleceniem:

```bash
python main.py
```

lub za pomocą serwera Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Aplikacja będzie dostępna w przeglądarce pod adresem:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🐳 Uruchamianie przez Docker

### 1. Tryb standardowy (CPU / Chmura)

```bash
docker compose up -d --build
```

Aplikacja wystartuje w odizolowanym kontenerze z preinstalowanym FFmpeg i automatyczną obsługą bazodanową.

### 2. Tryb z akceleracją GPU (NVIDIA CUDA)

Wymaga zainstalowanego [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

Uruchom profil GPU:

```bash
docker compose --profile gpu up -d --build
```

---

## 🧪 Uruchamianie Testów

Pakiet zawiera pełny zestaw 30 testów jednostkowych i integracyjnych pokrywających wszystkie moduły aplikacji:

```bash
pytest -v
```

Wynik:
```text
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_get_and_update_settings PASSED
tests/test_api.py::test_lessons_list_empty_or_valid PASSED
tests/test_api.py::test_calendar_status PASSED
tests/test_chunking.py::test_chunk_segments_basic PASSED
tests/test_chunking.py::test_chunk_segments_overlap PASSED
tests/test_chunking.py::test_chunk_plain_text_sentences PASSED
tests/test_chunking.py::test_format_external_ai_parts PASSED
tests/test_database.py::test_lesson_repository_lifecycle PASSED
tests/test_database.py::test_settings_repository PASSED
tests/test_database.py::test_google_oauth_repository PASSED
tests/test_event_detection.py::test_resolve_explicit_date PASSED
tests/test_event_detection.py::test_resolve_polish_month_date PASSED
tests/test_event_detection.py::test_resolve_jutro PASSED
tests/test_event_detection.py::test_resolve_pojutrze PASSED
tests/test_event_detection.py::test_resolve_za_tydzien PASSED
tests/test_event_detection.py::test_resolve_za_dwa_tygodnie PASSED
tests/test_event_detection.py::test_resolve_za_x_dni PASSED
tests/test_event_detection.py::test_relative_date_without_base_date_preserves_none PASSED
tests/test_exports.py::test_srt_timestamp_format PASSED
tests/test_exports.py::test_export_to_srt_and_vtt PASSED
tests/test_exports.py::test_create_lesson_docx PASSED
tests/test_exports.py::test_format_all_data_bundle PASSED
tests/test_nim_parser.py::test_extract_json_markdown_block PASSED
tests/test_nim_parser.py::test_extract_json_plain_object PASSED
tests/test_nim_parser.py::test_extract_json_embedded PASSED
tests/test_nim_parser.py::test_extract_json_corrupted_fallback PASSED
tests/test_rate_limiter.py::test_rate_limiter_throttling PASSED
tests/test_rate_limiter.py::test_execute_with_retry_success PASSED
tests/test_rate_limiter.py::test_execute_with_retry_exhausted PASSED

======================== 30 passed in 1.78s ========================
```

---

## 🛠️ Przykładowe Zapytania API (cURL)

### 1. Sprawdzenie stanu aplikacji
```bash
curl http://localhost:8000/health
```

### 2. Przesłanie nagrania lekcji
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@/sciezka/do/lekcja_matematyka.m4a" \
  -F "subject=Matematyka" \
  -F "lesson_date=2026-09-03"
```

### 3. Sprawdzenie statusu przetwarzania na żywo
```bash
curl "http://localhost:8000/api/lessons/{lesson_id}/status"
```

### 4. Pobranie pełnej notatki w formacie Markdown
```bash
curl "http://localhost:8000/api/lessons/{lesson_id}/export/note?format=md"
```

### 5. Pobranie transkrypcji z timestampami jako napisy .SRT
```bash
curl "http://localhost:8000/api/lessons/{lesson_id}/export/transcription?format=srt"
```

### 6. Przygotowanie wieloczęściowego materiału pod zewnętrzne AI
```bash
curl -X POST "http://localhost:8000/api/lessons/{lesson_id}/ai-prep" \
  -H "Content-Type: application/json" \
  -d '{"content_type": "prompt_transcription", "split_parts": true, "max_chars_per_part": 4000}'
```

---

## 🔧 Rozwiązywanie Problemów (Troubleshooting)

1. **Błąd: `Brak programu FFmpeg w systemie`**:
   Upewnij się, że pakiet `ffmpeg` jest zainstalowany w systemie operacyjnym (`which ffmpeg`). Jeśli uruchamiasz aplikację w Dockerze, jest on zainstalowany fabrycznie.
2. **Błąd: `NVIDIA NIM zwróciło błąd 429`**:
   Wbudowany limiter automatycznie wstrzyma kolejne zapytania do czasu wygaśnięcia okna czasowego (60 sekund) i ponowi zapytanie.
3. **Brak wykrycia karty graficznej (CUDA)**:
   Aplikacja automatycznie przechodzi w bezpieczny tryb `CPU` z obliczeniami `int8` dla biblioteki faster-whisper. Nie musisz niczego ręcznie zmieniać.
4. **Niewyraźne lub względne daty („za dwa tygodnie”)**:
   Jeśli w formularzu nie podasz daty lekcji, system zachowa oryginalny cytat słowny w polu `raw_date_expression`, a pole `date` ustawi na `null` (zapobiega to zmyślaniu nieistniejących terminów). Podanie daty lekcji pozwala systemowi precyzyjnie obliczyć konkretny dzień kalendarzowy.
5. **Prywatność i oszczędność miejsca na dysku**:
   Włącz opcję *„Automatycznie usuwaj oryginalne pliki wideo/audio po przetworzeniu”* w zakładce Ustawienia lub ustaw `DELETE_SOURCE_AFTER_PROCESSING=true` w `.env`. Oryginalne wideo zostanie usunięte natychmiast po udanej transkrypcji.

---

## 🔮 Możliwości Rozbudowy w Kolejnych Wersjach

Architektura aplikacji została zaprojektowana w oparciu o interfejsy i repozytoria, co pozwala na łatwe dodanie:
- **Wielu nagrań jednocześnie i analizy całego dnia lekcyjnego** (poprzez rozszerzenie `LessonPipeline` o pętlę wsadową i agregację tematów).
- **Automatycznego rozpoznawania mówców i diarizacji** (np. z użyciem biblioteki `pyannote.audio`).
- **Bezpośredniego nagrywania dźwięku z mikrofonu w przeglądarce** za pomocą Web Audio API i MediaRecorder.
- **Generowania fiszek (np. eksport do Anki / CSV)** na podstawie wyekstrahowanych definicji.
- **Integracji z kolejnymi chmurami** (Google Drive, Microsoft OneDrive, Notion API).
- **Lokalnych modeli LLM** (np. Ollama, vLLM, llama.cpp) poprzez implementację interfejsu `AIProvider`.
