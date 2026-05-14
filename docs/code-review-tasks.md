# Codebasis-Review: Konkrete Aufgabenvorschläge

Diese Notiz enthält vier priorisierte Aufgaben aus einem kurzen Review der Codebasis.

## 1) Aufgabe: Tippfehler/Inkonsistenz in Standardpfaden beheben

**Problem:** In CLI und API ist der Standard-DB-Pfad `~/stellashelf/stellashelf.db`, während die zentrale DB-Hilfsfunktion `~/.stellashelf/stellashelf.db` nutzt. Das ist eine typische Tippfehler-/Pfadinkonsistenz (fehlender Punkt) und führt leicht zu "leerer DB" bzw. "DB nicht gefunden" je nach Einstiegspunkt.

**Fundstellen:**
- `src/stellashelf/cli.py` (`--db` Defaults bei `scan`, `stats`, `serve`)
- `src/stellashelf/api.py` (`DB_PATH`)
- `src/stellashelf/db.py` (`get_db_path`)

**Vorschlag (Task):**
- Alle Default-Pfade auf **eine** Quelle vereinheitlichen (bevorzugt `get_db_path()` aus `db.py`).
- Regressionstest ergänzen: CLI/API nutzen denselben effektiven Default-Pfad.

---

## 2) Aufgabe: Programmierfehler beheben (API ignoriert `--db` aus `serve`)

**Problem:** `stellashelf serve --db ...` zeigt den übergebenen Pfad an, aber die API liest intern trotzdem den globalen `DB_PATH` in `api.py`. Der CLI-Parameter wirkt dadurch funktional nicht.

**Fundstellen:**
- `src/stellashelf/cli.py` (`serve` übergibt Pfad nicht an App-Konfiguration)
- `src/stellashelf/api.py` (`get_session_local()` nutzt globales `DB_PATH`)

**Vorschlag (Task):**
- App-Factory einführen, z. B. `create_app(db_path: Path) -> FastAPI`.
- `serve` so umbauen, dass der DB-Pfad per Env/Factory in die API injiziert wird.
- E2E-Test: `serve --db <tempfile>` und Health/Query gegen genau diese DB.

---

## 3) Aufgabe: Dokumentations-Unstimmigkeit korrigieren

**Problem:** In der Architekturübersicht der README wird `src/stellashelf/config.py` genannt, diese Datei existiert in der aktuellen Codebasis nicht.

**Fundstellen:**
- `README.md` (Architektur-Block)
- Dateiliste im Repository (kein `src/stellashelf/config.py` vorhanden)

**Vorschlag (Task):**
- README auf Ist-Zustand korrigieren (Datei entfernen oder durch echte Konfigurationsquelle ersetzen).
- Optional: kurze Sektion "Konfiguration" ergänzen (wo DB-Pfad/Defaults tatsächlich definiert sind).

---

## 4) Aufgabe: Tests verbessern (robuster und CI-tauglicher)

**Problem:** Integrationstests in `tests/test_scanner.py` hängen an einem lokalen absoluten Pfad (`/mnt/data/Astro/astro`). Das ist für CI/Contributor unzuverlässig und testet nur eine Umgebung.

**Fundstellen:**
- `tests/test_scanner.py` (`ASTRO_DATA = Path("/mnt/data/Astro/astro")`)

**Vorschlag (Task):**
- Testdaten als kleine synthetische FITS-Fixtures im Repo (oder per Factory) erzeugen.
- Integrationstests via Marker + `--run-integration`/Env-Flag explizit aktivieren.
- Mindestens ein End-to-End-Flow ohne externe Daten: `scan_directory(..., dry_run=True)` auf temp-Dataset.

---

## Priorisierung (empfohlen)
1. **Programmierfehler `serve --db`** (funktionale Korrektheit)
2. **Pfadinkonsistenz** (Benutzerfehler vermeiden)
3. **Testverbesserung** (langfristige Qualität)
4. **README-Korrektur** (Doku-Verlässlichkeit)
