# Codebasis-Review: Konkrete Aufgabenvorschläge

Diese Notiz enthält vier priorisierte Aufgaben aus einem kurzen Review der Codebasis.

## 1) ~~Aufgabe: Tippfehler/Inkonsistenz in Standardpfaden beheben~~ ✅ ERLEDIGT

**Problem:** In CLI und API war der Standard-DB-Pfad inkonsistent.

**Lösung:** Alle Default-Pfade nutzen jetzt `config.py` als einzige Quelle (`DEFAULT_DB_PATH` / `get_db_path()`). Die CLI `serve`-Command injiziert den DB-Pfad korrekt per `set_db_path()` in die API.

---

## 2) ~~Aufgabe: Programmierfehler beheben (API ignoriert `--db` aus `serve`)~~ ✅ ERLEDIGT

**Problem:** `stellashelf serve --db ...` ignorierte den übergebenen Pfad.

**Lösung:** `cli.py` ruft jetzt `set_db_path(db_path)` vor dem Start von uvicorn auf. Der DB-Pfad wird korrekt in die API injiziert.

---

## 3) ~~Aufgabe: Dokumentations-Unstimmigkeit korrigieren~~ ✅ ERLEDIGT

**Problem:** `src/stellashelf/config.py` wurde in der README erwähnt, existierte aber nicht.

**Lösung:** `config.py` wurde erstellt und enthält jetzt `DEFAULT_DB_PATH`, `DEFAULT_HOST`, `DEFAULT_PORT`, `KNOWN_CAMERAS` und `get_db_path()`. README und Architecture-Doku wurden auf den aktuellen Stand gebracht.

---

## 4) Aufgabe: Tests verbessern (robuster und CI-tauglicher)

**Problem:** Integrationstests in `tests/test_scanner.py` hängen an einem lokalen absoluten Pfad (`/mnt/data/Astro/astro`). Das ist für CI/Contributor unzuverlässig.

**Fundstellen:**
- `tests/test_scanner.py` (`ASTRO_DATA = Path("/mnt/data/Astro/astro")`)

**Vorschlag (Task):**
- Testdaten als kleine synthetische FITS-Fixtures im Repo (oder per Factory) erzeugen.
- Integrationstests via Marker + `--run-integration`/Env-Flag explizit aktivieren.
- Mindestens ein End-to-End-Flow ohne externe Daten: `scan_directory(..., dry_run=True)` auf temp-Dataset.

---

## Priorisierung (empfohlen)
1. ~~**Programmierfehler `serve --db`** (funktionale Korrektheit)~~ ✅
2. ~~**Pfadinkonsistenz** (Benutzerfehler vermeiden)~~ ✅
3. ~~**README-Korrektur** (Doku-Verlässlichkeit)~~ ✅
4. **Testverbesserung** (langfristige Qualität) — offen
