# Importers (planned)

Import adapters turn a user's *existing* commitments into `ExternalEvent` records
(see `__init__.py`) so the app can (a) avoid double-booking and (b) place them into
the fortnight view. Planned sources, one module each (single responsibility):

| module (planned)        | source                         | notes |
|-------------------------|--------------------------------|-------|
| `google_calendar.py`    | Google Calendar API            | user's own OAuth credentials, on device; read now, write later |
| `spreadsheet.py`        | .xlsx / .csv                   | reuse `fk_core.xlsx` |
| `image.py`              | photo of a hand-written schedule | needs the user's own AI provider (see `docs/ai-providers.md`) for OCR/structuring |

Rules: importers are read-only with respect to `data/`; they never store credentials;
they return raw payloads under `raw` so nothing is lost. Exporters (pushing FortKnight
plans *to* a calendar) will live in a sibling `exporters/` package.
