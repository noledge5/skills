# DataBrokerScanner — Review & Projektplan

> Kritische Durchsicht des Handoffs plus ausgearbeiteter Umsetzungsplan aus Senior-Developer-Sicht.
> Stand: 2026-07-07. Sprache des Codes: Englisch, Doku zweisprachig (DE-Primär).

---

## 1. Kurzfazit

Die Grundidee ist legitim und wertvoll: ein **Privacy-Self-Audit-Tool**, das einer Person zeigt, wo ihre öffentlich zugänglichen Daten liegen, und direkt zu den Opt-out-Prozessen führt. Vergleichbare Dienste (DeleteMe, Optery, Mozilla Monitor) belegen den Bedarf.

Der Handoff ist ambitioniert und in den Zielen richtig ausgerichtet (kein CAPTCHA-Bypass, keine Login-Automatisierung, nur öffentliche Daten). Er enthält aber **drei substanzielle Widersprüche** und einige technische Fehler, die vor dem ersten Commit geklärt werden müssen. Ohne diese Korrekturen baut man ein Tool, das seine eigenen ethischen Leitplanken verletzt.

**Kernbotschaft:** Nicht als „Scraper für Personensuchmaschinen" bauen, sondern als **einwilligungsbasiertes Selbst-Audit mit assistiertem Manuell-Modus**. Das löst gleichzeitig die rechtlichen, ethischen und technischen Probleme.

---

## 2. Kritische Korrekturen (müssen vor Baubeginn entschieden werden)

### 2.1 Widerspruch: „robots.txt respektieren" vs. „Broker automatisch scannen"

Die meisten US-Personensuchmaschinen (Spokeo, BeenVerified, TruthFinder, InstantCheckmate, Radaris …) untersagen automatisierten Zugriff sowohl in ihren **ToS** als auch in **robots.txt**. Wenn man robots.txt ernst nimmt — und der Handoff verlangt das explizit — dann **darf man den Großteil dieser Seiten gar nicht automatisiert abfragen**.

**Auflösung (empfohlen):** Broker in drei Klassen einteilen, statt „alle scrapen":

| Klasse | Verhalten | Beispiele |
|---|---|---|
| `automated` | robots.txt erlaubt Abruf → automatischer Scan + Parse | Seiten mit permissiver robots.txt / offizieller Such-API |
| `assisted` | robots.txt/ToS verbieten Automatisierung → Tool öffnet die **vorbefüllte Such-URL im sichtbaren Browser**, Nutzer prüft Treffer selbst, Tool erfasst nur, was der Nutzer bestätigt | Spokeo, BeenVerified, Radaris, TruthFinder |
| `optout_only` | Kein Scan, nur kuratierter Deep-Link zum Datenschutz-/Auskunfts-/Opt-out-Prozess | SCHUFA, CRIF, Acxiom, LiveRamp, Oracle, Epsilon, D&B |

Das ist konsistent mit der bereits im Handoff formulierten Regel („Sobald eine Webseite menschliche Interaktion verlangt, pausieren") — wir verallgemeinern sie zum Architekturprinzip.

### 2.2 Widerspruch: „keine Schutzmaßnahmen umgehen" vs. `undetected-playwright` + `fake-useragent`

`undetected-playwright` und rotierende Fake-User-Agents existieren **ausschließlich**, um Bot-Erkennung zu umgehen — das ist per Definition das Umgehen einer technischen Schutzmaßnahme und widerspricht direkt der wichtigsten Anforderung des Handoffs (und ggf. §202a StGB / CFAA-Diskussion / ToS).

**Auflösung:** Beide Abhängigkeiten **streichen**. Stattdessen:
- Ein **ehrlicher, identifizierbarer** User-Agent inkl. Kontakt-/Projekt-URL (z. B. `DataBrokerScanner/0.1 (+https://github.com/…; self-privacy-audit)`).
- Konservatives, höfliches Rate-Limiting statt Tarnung.
- Wird man blockiert → das ist ein **legitimes Nein der Seite**, das respektiert wird (Broker auf `assisted` herabstufen), nicht ein zu umgehendes Hindernis.

### 2.3 Rechtlicher/ethischer Missbrauchsvektor: Suche nach Dritten

Das Tool kann trivial zum **Stalking/Doxxing/OSINT gegen fremde Personen** zweckentfremdet werden — die gefährlichste Eigenschaft. Der Handoff adressiert das nicht.

**Auflösung — Leitplanken einbauen (nicht nur dokumentieren):**
- **Einwilligungs-Gate** beim ersten Start: explizite Bestätigung „Ich suche nach mir selbst oder habe die dokumentierte Einwilligung/rechtliche Grundlage der betroffenen Person." Bestätigung wird mit Zeitstempel in der DB gespeichert (`consent`-Tabelle).
- **Keine Bulk-Targets:** eine Person pro Lauf; kein Import von Personenlisten in v1.
- Konservative Default-Rate-Limits (siehe unten), damit kein Massenbetrieb entsteht.
- DSGVO/CCPA-Kontext + Haftungsausschluss prominent in README und CLI-Startbanner.

> Diese drei Punkte sind keine „nice to have" — sie sind die Existenzberechtigung des Tools als defensives Werkzeug. Ich empfehle, sie als nicht verhandelbare Akzeptanzkriterien für v1 zu setzen.

### 2.4 Technischer Fehler: Modulnamen wie `11880.py` / `411`

`import 11880` ist **kein gültiges Python** — Modulnamen dürfen nicht mit einer Ziffer beginnen. Der Handoff listet `11880.py` und Broker „411" so auf.

**Auflösung:** Broker werden nicht über Dateinamen adressiert, sondern über einen **Registry-/Plugin-Mechanismus** (Entry-Points bzw. Auto-Discovery via `importlib`), bei dem der `name` ein Attribut der Klasse ist. Dateien heißen z. B. `de_11880.py`, Klasse `Elfeightyeighty`/`Broker11880` mit `name = "11880"`. Der stabile Schlüssel ist ein `slug` (`"11880"`, `"das-telefonbuch"`), nicht der Dateiname.

### 2.5 Redundanz: `brokers.json` **und** je eine Python-Klasse pro Broker

Für die ~20 reinen `optout_only`-Einträge (SCHUFA, Acxiom, LiveRamp …) braucht es **keinen Code** — nur Metadaten. Eine eigene Python-Klasse pro solchem Broker ist toter Boilerplate.

**Auflösung:** Deklarativ + Code sauber trennen:
- `brokers/registry.yaml` (oder `.json`) = **Datenquelle der Wahrheit** für Metadaten aller Broker (Name, Slug, Land, Kategorie, `class`-Feld `automated|assisted|optout_only`, Such-URL-Template, Opt-out-URL, Enabled).
- Eine **generische `DeclarativeBroker`**-Klasse bedient `optout_only` und einfache `assisted`-Broker rein aus den Metadaten.
- Eine **eigene Python-Klasse** wird nur dort geschrieben, wo echte Parse-Logik nötig ist (`automated`). Genau das erfüllt die Erweiterbarkeitsanforderung „neuer Broker = neue Datei + Eintrag" — nur eben ohne Zwang zu Boilerplate.

---

## 3. Weitere Verbesserungen (empfohlen, nicht blockierend)

- **Projektlayout:** `src/`-Layout mit Paketname `databroker_scanner` statt loser Top-Level-Module (`person.py`, `report.py` …). Verhindert Import-Schatten und macht das Paket sauber installierbar.
- **Python-Version:** 3.13 ist ok, aber einige Libs (Playwright-Builds, `pyarrow`) hinken teils hinterher. Empfehlung: **Floor 3.12**, getestet gegen 3.12 + 3.13 in der CI.
- **`pydantic` v2 durchgängig:** `Person` und `Settings` als Pydantic-Modelle; `config.yaml` via `pydantic-settings` laden + validieren. Fehlkonfiguration schlägt früh und klar fehl.
- **Confidence-Score als echter Algorithmus** definieren, nicht als Handwave: gewichtete Signale (Nachname exakt, Vorname exakt/Initiale, Stadt/Bundesland-Match, Alter/Telefon-Korroboration) → 0–100, plus Schwellenwerte `likely/possible/unlikely`. Als eigene, **unit-getestete** Funktion (`scoring.py`).
- **Rate-Limiting pro Domain**, nicht nur global. Default konservativ: `parallel: 2`, `per_domain_delay: 3–5 s`. Der Handoff-Default `parallel: 6` ist für Broker-Scraping zu aggressiv und provoziert Blocks.
- **`tenacity`-Retries nur für transiente Fehler** (Timeout, 5xx, Netzwerk). **Kein** Retry bei 403/429/CAPTCHA — das ist ein „Nein", kein Fehler; dort: Broker auf `assisted` herabstufen bzw. pausieren.
- **Tests gegen gespeicherte HTML-Fixtures**, nicht gegen Live-Netz. Jeder `automated`-Broker-Parser wird gegen ein eingechecktes HTML-Snapshot getestet → deterministisch, offline, CI-tauglich. Live-Netzzugriff nur in optionalen, standardmäßig übersprungenen `@pytest.mark.network`-Tests.
- **CLI konsolidieren:** `scanner html/csv/json` sind keine sinnvollen Top-Level-Kommandos. Besser `scanner export --format html|csv|json|md`. Screenshots fallen automatisch beim Scan an, kein eigenes Verb nötig. Finales CLI: `search`, `resume`, `report`, `export`, `brokers`, `config`.
- **Persistenz-Layer** hinter einem Repository-Interface (kein SQL im Broker-Code). SQLite via `sqlite3` reicht für v1; `sqlmodel`/`SQLAlchemy` optional, wenn Migrationen nötig werden. Parquet/`pyarrow` erst, wenn es einen echten Analyse-Use-Case gibt — sonst YAGNI.
- **Ein einziges, self-contained HTML-Report** (Jinja2, CSS/JS inline, Screenshots als eingebettete Assets oder relativ verlinkt) — leicht teilbar, kein Server nötig.
- **Strukturiertes Logging** mit `rich` (Konsole) + optional JSON-Lines-Datei; Korrelation über `scan_run_id`.
- **Secrets/PII:** DB und Reports enthalten personenbezogene Daten → `results/`, `reports/`, `screenshots/` in `.gitignore`; Hinweis in README, DB-Datei nicht zu committen; optional lokale Verschlüsselung als spätere Ausbaustufe.

---

## 4. Zielarchitektur (korrigiert)

```
databroker-scanner/
  pyproject.toml            # Paketdef, [project.scripts] scanner = "databroker_scanner.cli:app"
  README.md                 # Install, Beispiele, FAQ, Haftungsausschluss, Datenschutz, Lizenz
  LICENSE                   # MIT
  config.example.yaml
  .gitignore                # results/ reports/ screenshots/ *.db
  src/databroker_scanner/
    __init__.py
    cli.py                  # typer-App: search/resume/report/export/brokers/config
    config.py               # pydantic-settings: Settings aus config.yaml
    consent.py              # Einwilligungs-Gate + Persistenz
    models.py               # Person, Match, ScanRun, Broker-Metadaten (pydantic)
    scoring.py              # Confidence-Score (getestet)
    registry.py             # Auto-Discovery + Laden der Broker aus registry.yaml
    core/
      broker.py             # ABC Broker: search()/parse()/optout(); DeclarativeBroker
      scanner.py            # asyncio-Orchestrierung, Semaphore, per-Domain-Rate-Limit
      robots.py             # robots.txt-Check je Domain (Cache)
      checkpoint.py         # Resume/Crash-Recovery über scan_run_id
    browser/
      session.py            # Playwright-Chromium-Lifecycle (headless/visible/slowmo/proxy)
      interaction.py        # CAPTCHA/Human-Gate-Erkennung → Pause + Nutzerhinweis
      screenshot.py         # Full-Page-PNG, Treffermarkierung
    storage/
      db.py                 # SQLite-Schema + Repository (persons/scans/matches/screenshots/consent)
    reporting/
      html.py               # Jinja2, self-contained
      exporters.py          # csv/json/markdown
      templates/report.html.j2
    brokers/
      registry.yaml         # Datenquelle der Wahrheit für ALLE Broker
      automated/            # nur Broker mit echter Parse-Logik
        <slug>.py
  tests/
    fixtures/               # eingecheckte HTML-Snapshots pro Broker
    test_scoring.py
    test_registry.py
    test_brokers_<slug>.py  # Parser gegen Fixtures
    test_consent.py
```

### Broker-Basisklasse (korrigiert)

```python
class Broker(ABC):
    slug: str                     # stabiler Schlüssel, z.B. "11880"
    name: str
    country: str
    category: str
    mode: Literal["automated", "assisted", "optout_only"]
    search_url_template: str      # z.B. "https://…/{firstname}-{lastname}/{city}"
    optout_url: str

    async def search(self, session: BrowserSession, person: Person) -> SearchOutcome: ...
    async def parse(self, page) -> list[Match]: ...       # nur 'automated'
    def optout(self) -> OptOutInfo: ...                    # Deep-Link + Anleitung
```

`DeclarativeBroker(Broker)` implementiert `search`/`parse` generisch für `assisted`/`optout_only` aus den Metadaten; nur `automated`-Broker überschreiben `parse`.

---

## 5. Datenmodell (SQLite)

- `consent(id, acknowledged_at, statement_version)`
- `persons(id, firstname, lastname, middlename, phone, email, city, state, country, zipcode, created_at)` — nur befüllte Felder werden in Suchen genutzt
- `scan_runs(id, person_id, started_at, finished_at, status, config_snapshot)`
- `matches(id, scan_run_id, broker_slug, profile_name, profile_url, search_term, status, confidence, optout_url, optout_type, found_at)`
- `screenshots(id, match_id, path, taken_at)`

Resume = offener `scan_run` + pro Broker ein Status (`pending/done/blocked/skipped`) → Crash-Recovery lädt den letzten Checkpoint.

---

## 6. Umsetzungsplan (Phasen / vertikale Slices)

Jede Phase ist lauffähig und liefert Wert („tracer bullet"), statt breit-aber-tot vorzubauen.

**Phase 0 — Fundament & Leitplanken (Basis für alles)**
- Repo-Skeleton, `pyproject.toml`, `src/`-Layout, CI (lint `ruff`, typecheck `mypy`/`pyright`, `pytest`, 3.12+3.13).
- `models.py` (Person, Match …), `config.py`, `consent.py` inkl. Gate.
- README-Gerüst mit Haftungsausschluss/Datenschutz.
- *Akzeptanz:* `scanner --help` läuft; Einwilligungs-Gate blockt ohne Bestätigung; Tests grün.

**Phase 1 — Erster End-to-End-Slice: `optout_only`**
- `registry.yaml` + `DeclarativeBroker`; Registry-Auto-Discovery.
- Alle `optout_only`-Broker (SCHUFA, CRIF, Acxiom, LiveRamp, Oracle, Epsilon, D&B, Experian) rein deklarativ.
- `scanner brokers` (Liste) + `scanner report`/`export` (HTML/CSV/JSON) auf Basis der DB.
- *Akzeptanz:* Ohne jeden Netz-Scan bekommt der Nutzer einen vollständigen, korrekten Opt-out-Report. Beweist die gesamte Pipeline (Registry → DB → Report) an der risikoärmsten Broker-Klasse.

**Phase 2 — Browser & assistierter Modus**
- `browser/session.py` (Playwright), `interaction.py` (CAPTCHA/Human-Gate-Erkennung → Pause), `screenshot.py`, `robots.py`.
- `assisted`-Flow: vorbefüllte Such-URL im sichtbaren Browser öffnen, Nutzer bestätigt Treffer, Screenshot + Match erfassen.
- Checkpoint/Resume (`scanner resume`).
- *Akzeptanz:* Ein `assisted`-Broker (z. B. Das Telefonbuch/Das Örtliche, DE, meist tolerantere ToS) läuft sauber inkl. Pause-bei-CAPTCHA und Resume.

**Phase 3 — `automated`-Broker + Scoring**
- `scanner.py`: asyncio-Orchestrierung, Semaphore, per-Domain-Rate-Limit, `tenacity` (nur transient).
- `scoring.py` + 2–3 `automated`-Broker **nur dort, wo robots.txt es zulässt**, jeweils mit HTML-Fixture-Tests.
- *Akzeptanz:* Parallel-Scan mit Confidence-Scores; Parser deterministisch offline getestet.

**Phase 4 — Politur**
- HTML-Dashboard (Filter/Suche/Opt-out-Buttons), Markdown-Report, JSON-Logs.
- Broker-Katalog vervollständigen (überwiegend deklarativ), README-FAQ/Screenshots, Contribution-Guide „So fügst du einen Broker hinzu".

**Bewusst verschoben (YAGNI bis Bedarf):** `pyarrow`/Parquet, `undetected-playwright` (gestrichen), Multi-Person-Batch, Proxy-Rotation, DB-Verschlüsselung.

---

## 7. Offene Entscheidungen für dich

1. **Geografischer Fokus v1** — DE-Broker (Telefonbuch/Örtliche/11880/Yasni, tolerantere ToS, gute erste `automated`-Kandidaten) oder US-Broker zuerst? Empfehlung: DE zuerst, weil rechtlich/technisch der weichere Einstieg.
2. **Verhältnis Automatisierung vs. Assistiert** — Bist du mit dem Prinzip einverstanden, dass Seiten mit restriktiver robots.txt **nicht** automatisiert gescannt, sondern im assistierten Modus geführt werden? (Meine klare Empfehlung: ja.)
3. **`undetected-playwright` streichen** — bestätigt? (Empfehlung: ja, siehe 2.2.)
4. **Zielrepo** — Soll das ein eigenständiges Repo werden? Der aktuelle `skills`-Monorepo ist thematisch ein anderer Kontext; dieser Plan liegt vorerst nur als Dokument auf dem Feature-Branch.

---

## 8. Was dieser Branch aktuell enthält

Nur dieses Planungsdokument. Es wurde **noch kein** ausführbarer Code erzeugt — der Handoff bat um „prüfen, korrigieren, planen". Sobald du die vier Entscheidungen in §7 getroffen hast, starte ich mit **Phase 0 + 1** (Fundament + erster End-to-End-Slice über die risikoarmen `optout_only`-Broker).
