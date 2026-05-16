# StellaShelf — Spezifikation / Detailkonzept

**Version**: 0.4.0
**Stand**: Mai 2026
**Lizenz**: AGPL-3.0

---

## 1. Projektübersicht

### 1.1 Was ist StellaShelf?

StellaShelf ist ein **Astrophotography Digital Asset Manager & Processing Hub** für Amateur-Astrophotografen. Es katalogisiert automatisch lokale FITS-Sammlungen, gruppiert Einzelframes in Beobachtungssessions, reichert sie mit Metadaten an (Koordinaten via Platesolving, Qualitätskennzahlen via HFD-Analyse, Objektidentifikation via OpenNGC-Katalog) und bietet eine moderne Vue-3-Weboberfläche zum Durchsuchen, Filtern und Verwalten.

### 1.2 Kernziele

- **Automatische Katalogisierung**: FITS-Header auslesen, Metadaten normalisieren, Duplikate erkennen
- **Sessions-Gruppierung**: Frames nach Zielobjekt + Datum + Kamera + Teleskop + Filter gruppieren
- **Metadaten-Anreicherung**:
  - Fehlende RA/Dec-Koordinaten via ASTAP-Platesolving bestimmen
  - HFD (Half Flux Diameter) und Sternanzahl via ASTAP-Analyse messen
  - Deep-Sky-Objekte im Bildfeld via OpenNGC-Katalog identifizieren
- **Durchsuchen & Verwalten**: Zielobjekte, Sessions, Frames und Equipment-Katalog mit Paginierung, Filterung, Volltextsuche und Thumbnails
- **Datenbereinigung**: Duplikaterkennung, Target-Merge, Orphan-Bereinigung

### 1.3 Zielpublikum

Amateur-Astrophotografen mit lokalen FITS-Sammlungen auf Linux-Workstations, die:
- eine Übersicht über ihre gesamte Astro-Sammlung wollen
- Frames ohne Koordinaten automatisch platen lassen möchten
- die Qualität ihrer Aufnahmen (HFD/Stars) bewerten wollen
- herausfinden wollen, welches Deep-Sky-Objekt auf einem Frame abgebildet ist

---

## 2. Architektur

### 2.1 Drei-Schichten-Architektur

```
┌──────────────────────────────────────────────────┐
│                    UI                            │
│       Vue 3 + Vite + ECharts + Lucide            │
│      13 Views, 6 Pinia Stores                   │
└─────────────────────┬────────────────────────────┘
                      │ HTTP/REST
┌─────────────────────▼────────────────────────────┐
│                    API                            │
│     FastAPI + Pydantic + SQLAlchemy + FTS5        │
│    30+ REST Endpoints + Background Tasks          │
└─────────────────────┬────────────────────────────┘
                      │ SQL
┌─────────────────────▼────────────────────────────┐
│                 Storage / Tools                   │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ SQLite   │  │ ASTAP   │  │ OpenNGC        │  │
│  │ + FTS5   │  │ CLI     │  │ NGC.csv         │  │
│  └──────────┘  └──────────┘  │ + addendum.csv │  │
│                              └────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 2.2 Komponenten

| Komponente | Technologie | Aufgabe |
|---|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 | REST-API, Background-Tasks, DB-Zugriff |
| Datenbank | SQLite + FTS5 | Persistenz, Volltextsuche – serverlos, portabel |
| Frontend | Vue 3 + Vite + ECharts + Lucide | Web-Dashboard, 13 Views |
| FITS-Reader | astropy.io.fits | FITS-Header-Extraktion, Thumbnails |
| Platesolver | ASTAP CLI (astap_cli) | RA/Dec-Bestimmung, HFD-Analyse |
| Katalog | OpenNGC (numpy, ~14k Objekte) | Deep-Sky-Objekt-Identifikation |
| RAW-Reader | rawpy (optional) | Canon/Nikon/Sony RAW-Formate (geplant) |
| Linting | Ruff | Python-Linter + Formatter |
| Tests | pytest + pytest-cov + httpx | Unit + Integrationstests |

### 2.3 Deployment

- **Entwicklung**: Lokal auf RK3588 (ARM64), Hot-Reload via `--reload`
- **Produktion**: Docker auf Kubuntu-Workstation (AMD 5900X, RX 9070), Daten via NFS gemountet
- **Port**: 8321 (Standard, konfigurierbar)
- **Start**: `stellashelf serve --host 0.0.0.0 --port 8321`

### 2.4 Verzeichnisstruktur

```
StellaShelf/
├── src/stellashelf/
│   ├── __init__.py     # Version (0.4.0), Build-Import
│   ├── _build.py       # Auto-generierte Build-Nummer
│   ├── scanner.py      # FITS-Header-Extraktion, Session-Gruppierung, Thumbnails,
│   │                   #   Platesolve, Analyse (HFD/Stars)
│   ├── skylookup.py    # OpenNGC-Katalog-Loader, Objektidentifikation, Suchradius
│   ├── db.py           # SQLAlchemy-Modelle (9 Tabellen), FTS5-Init, Trigger
│   ├── importer.py     # Zentrale Import-Pipeline (CLI + API)
│   ├── catalog.py      # Objektnamen-Normalisierung (M51→M51)
│   ├── api.py          # FastAPI-App, 30+ Endpoints, Background-Tasks
│   ├── cli.py          # Click-CLI-Kommandos (scan, stats, serve)
│   └── config.py       # Pfade, Defaults, Known-Cameras
├── frontend-vue/src/
│   ├── views/          # 13 Vue-Views
│   ├── stores/         # 6 Pinia-Stores
│   ├── components/     # StatCard, Pagination, etc.
│   └── router/         # Vue-Router-Konfiguration
├── data/
│   ├── NGC.csv         # OpenNGC-Hauptkatalog (13.970 Objekte)
│   └── addendum.csv    # OpenNGC-Ergänzungen (64 Objekte)
├── tests/
│   ├── test_db.py      # DB-Tests
│   ├── test_scanner.py # Scanner-Tests
│   └── test_api.py     # API-Integrationstests
├── docs/
│   ├── roadmap.md      # Entwicklungs-Roadmap
│   ├── specification.md # Dieses Dokument
│   └── architecture.md # Architektur-Übersicht
└── pyproject.toml      # Projekt-Metadaten, Dependencies
```

---

## 3. Datenmodell

### 3.1 Entity-Relationship-Diagramm

```
Target 1───* Session *───1 Camera
                    *───1 Telescope
                    *───* Frame
                    (Cascade-Delete)

CalibrationFile *───1 Camera
Setting (key-value, keine FK)
```

### 3.2 Tabellen

#### Target
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| name | String(255), NOT NULL, Index | Kanonischer Name (z. B. "M51", "NGC7000") |
| alt_names | Text, NULL | Komma-separierte Alternativnamen |
| object_type | String(64), NULL | Typ (Galaxy, Nebula, Open Cluster, …) |
| constellation | String(64), NULL | Sternbild (z. B. "CVn") |
| ra_deg | Float, NULL | Rektaszension in Grad (vom Katalog) |
| dec_deg | Float, NULL | Deklination in Grad (vom Katalog) |

#### Session
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| target_id | Integer (FK→Target) | Zielobjekt |
| camera_id | Integer (FK→Camera) | Kamera |
| telescope_id | Integer (FK→Telescope) | Teleskop |
| date_obs | DateTime, Index | UTC-Beobachtungsdatum |
| date_local | DateTime | Lokales Datum |
| site_name | String(255) | Standort |
| group_key | String(255), UNIQUE | Gruppierungsschlüssel (Object|Date|Camera|Telescope|Filter) |
| path | Text | Basisverzeichnis |
| status | String(32), Default "raw" | raw / calibrated / stacked |
| total_exposure_s | Float | Gesamtbelichtung in Sekunden |
| total_exposure_h | Float | Gesamtbelichtung in Stunden |
| frame_count | Integer | Anzahl Frames |
| capture_software | String(255) | Aufnahmesoftware |
| observer | String(255) | Beobachter |
| created_at, updated_at | DateTime | Audit-Timestamps |

#### Frame
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| session_id | Integer (FK→Session) | Session |
| filename | String(512) | Dateiname |
| filepath | Text, Index | Vollständiger Pfad |
| file_size | Integer | Dateigröße |
| frame_type | String(16) | LIGHT / DARK / FLAT / BIAS |
| object_name | String(255), Index | Zielobjekt-Name (kann überschrieben werden) |
| instrume | String(255), Index | Kamera |
| telescop | String(255) | Teleskop |
| filter_name | String(64), Index | Filter |
| exposure | Float | Einzelbelichtung in Sekunden |
| gain | Integer | Verstärkung |
| ccd_temp | Float | Sensortemperatur °C |
| binning | Integer, Default 1 | Binning |
| date_obs | DateTime, Index | UTC-Beobachtungszeit |
| date_local | DateTime | Lokale Zeit |
| width, height | Integer | Pixelmaße |
| pixel_size_um | Float | Pixelgröße in µm |
| ra_deg, dec_deg | Float | Koordinaten in Grad |
| focal_length_mm | Float | Brennweite |
| site_name | String(255) | Standort |
| observer, creator | String(255) | Metadaten |
| fwhm, eccentricity, snr | Float | Siril-Kennzahlen (reserviert) |
| **hfd_median** | Float | HFD-Wert via ASTAP-Analyse |
| **stars_detected** | Integer | Sternanzahl via ASTAP-Analyse |
| file_sha256 | String(64) | Datei-Hash (reserviert für Deduplizierung) |
| scanned_at | DateTime | Import-Zeitstempel |

**Indizes**:
- `ix_sessions_target_date`: `(target_id, date_obs)`
- `ix_frames_type_object`: `(frame_type, object_name)`
- `filepath`: Einzelfeld-Index (für Duplikaterkennung)
- FTS5-Index für Volltextsuche (siehe Abschnitt 5.8)

#### Camera
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| name | String(255), UNIQUE | Vollname (z. B. "ZWO ASI294MM Pro") |
| short_name | String(64) | Kurzname (z. B. "ASI294MM") |
| pixel_size_um | Float | Pixelgröße |
| sensor_width/height_px | Integer | Sensorauflösung |
| bit_depth | Integer | Bit-Tiefe |
| is_color | Boolean | Farbkamera |

#### Telescope
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| name | String(255), UNIQUE | Vollname |
| short_name | String(64) | Kurzname |
| focal_length_mm | Float | Brennweite |
| aperture_mm | Float | Öffnung |
| f_ratio | Float | Öffnungsverhältnis |

#### CalibrationFile
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| camera_id | Integer (FK→Camera) | Kamera |
| cal_type | String(32) | masterbias / masterdark / masterflat |
| exposure_s, gain, binning, ccd_temp, filter_name | diverse | Aufnahmeparameter |
| filepath, filename | Text/String | Datei-Identifikation |
| parsed_* | diverse | Aus Dateinamen geparste Werte |

#### Setting
| Spalte | Typ | Beschreibung |
|---|---|---|
| id | Integer (PK) | Auto-Inkrement |
| key | String(128), UNIQUE | Einstellungsschlüssel |
| value | Text | Wert |
| description | String(255) | Beschreibung |

---

## 4. Use Cases

### UC-01: FITS-Sammlung einlesen und katalogisieren

**Akteur**: Administrator/Benutzer  
**Vorbedingung**: Verzeichnis mit FITS-Dateien vorhanden, ASTAP installiert (optional)

**Ablauf**:
1. Benutzer startet `stellashelf scan /pfad/zu/fits` (CLI) oder klickt auf "Scannen" in der Web-Oberfläche (API: `POST /api/v1/scan`)
2. StellaShelf durchsucht rekursiv das Verzeichnis nach `.fit`/`.fits`-Dateien
3. Für jede Datei:
   - FITS-Header parsen (primäre HDU + ggf. erste Extension)
   - Metadaten extrahieren: OBJECT, INSTRUME, TELESCOP, FILTER, EXPOSURE, GAIN, DATE-OBS, Koordinaten etc.
   - Bei fehlendem OBJECT-Namen: Fallback aus Dateinamen versuchen
   - Kamera/Teleskop auch aus Verzeichnispfad extrahieren
   - Frame-Typ normalisieren (light → LIGHT etc.)
4. Duplikaterkennung via Dateipfad: bereits bekannte Pfade überspringen
5. Session-Gruppierung via `group_key` = `{Object}|{Date}|{Camera}|{Telescope}|{Filter}`
6. Batch-Commit alle 500 Frames
7. Session-Statistiken neu berechnen (frame_count, total_exposure)
8. Im CLI: Fortschrittsbalken mit Rich; in API: State-Dict wird live aktualisiert

**Nachbedingung**: FITS-Dateien sind in der Datenbank katalogisiert, in Sessions gruppiert, Equipment-Einträge automatisch angelegt  
**Fehlerszenarien**:
- Datei nicht lesbar → wird übersprungen, Warnung in Konsole/Log
- XISF-Datei → wird mit Warnung übersprungen
- DB-Schema fehlt → wird automatisch angelegt

---

### UC-02: Sessions und Frames durchsuchen/filtern

**Akteur**: Benutzer  
**Vorbedingung**: Datenbank wurde befüllt (UC-01)

**Ablauf**:
1. Benutzer öffnet die Web-Oberfläche
2. Sessions-Liste: Sessions nach Datum, Kamera, Teleskop, Filter, Status filterbar
3. Frames-Liste: Nach Session, Objekt, Filter, Typ, Koordinaten-Status, Dateiname/Pfad (Wildcards) filterbar
4. Sortierung aufsteigend/absteigend nach verschiedenen Kriterien
5. Paginierung (einstellbare Seitengröße)
6. Volltextsuche: FTS5-Suche über Objekt, Kamera, Teleskop, Filter, Dateiname, Standort

**Nachbedingung**: Filter-/Suchresultate werden angezeigt, Seitenwechsel möglich

---

### UC-03: Zielobjekte verwalten (Duplikate, Merge)

**Akteur**: Benutzer  
**Vorbedingung**: Datenbank enthält Targets (evtl. mit unterschiedlich normalisierten Namen wie "M51" und "M 51")

**Ablauf**:
1. Duplikaterkennung via `GET /api/v1/targets/duplicates`
2. Gruppierung anhand `normalize_object_name()` (M51 = m51 = M 51)
3. Zwei Merge-Modi:
   - **Manuell**: Quell-Target in Ziel-Target mergen (alias-Namen, ggf. Koordinaten übernehmen)
   - **Auto-Group**: Alle Targets mit gleichem kanonischen Namen in eines mergen (Behalte das mit den meisten Sessions)
4. Nach Merge: Session.frame_count und total_exposure werden neu berechnet
5. Orphan-Bereinigung (leere Targets/Sessions löschen)

**Nachbedingung**: Keine Duplikat-Targets mehr vorhanden, Sessions auf konsolidierte Targets umgebogen

---

### UC-04: Platesolving (RA/Dec per ASTAP bestimmen)

**Akteur**: Benutzer (oder automatisch via Background-Task)  
**Vorbedingung**: ASTAP CLI installiert, Frames ohne RA/Dec vorhanden

**Ablauf**:
1. Benutzer startet Platesolving via `POST /api/v1/platesolve`
2. Background-Task durchsucht alle Frames ohne RA/Dec (light + calibration)
3. Pro Frame:
   - ASTAP-CLI aufrufen: `astap_cli -f <file> -o <tmp> -r 10`
   - Optional: RA/Dec-Hint aus Target-Metadaten verwenden, falls vorhanden
   - WCS- oder INI-Resultat auf CRVAL1/CRVAL2 parsen
   - Bei Erfolg: frame.ra_deg/dec_deg in DB speichern
   - Bei Fehler: loggen, weitermachen
4. Cancel-Flag wird vor jedem Frame geprüft

**Nachbedingung**: Alle platebaren Frames haben Koordinaten, DB aktualisiert  
**Fehlerszenario**: ASTAP löst nicht (Sternanzahl zu gering, falscher Hint) → Frame bleibt ungelöst

---

### UC-05: Qualitätsanalyse (HFD/Stars via ASTAP)

**Akteur**: Benutzer  
**Vorbedingung**: ASTAP CLI installiert, LIGHT-Frames ohne HFD-Daten vorhanden

**Ablauf**:
1. Benutzer startet Analyse via `POST /api/v1/analyse`
2. Background-Task durchsucht LIGHT-Frames ohne `hfd_median`-Wert
3. Pro Frame:
   - `astap_cli -f <file> -analyse 30` aufrufen
   - Stdout parsen: `HFD_MEDIAN=4.2`, `STARS=1234`
   - Bei Erfolg: frame.hfd_median und frame.stars_detected setzen
   - Bei Fehler: loggen
4. Live-Fortschritt via `GET /api/v1/analyse/status`, cancelbar

**Nachbedingung**: Alle LIGHT-Frames haben HFD- und Stars-Werte  
**Grenzwerte**:
- HFD < 3.0 → exzellente Fokussierung
- HFD 3.0–5.0 → gut
- HFD > 5.0 → Fokus optimierbar
- Stars typisch: 500–5000+ je nach Himmelsregion und Belichtung

---

### UC-06: Objektidentifikation (Reverse Sky Lookup per OpenNGC)

**Akteur**: Benutzer  
**Vorbedingung**: OpenNGC-Katalog (NGC.csv + addendum.csv) vorhanden, LIGHT-Frames mit RA/Dec

**Ablauf**:
1. Benutzer startet Identifikation via `POST /api/v1/identify`
2. Background-Task durchsucht alle LIGHT-Frames mit RA/Dec
3. Pro Frame:
   - FOV-basierten Suchradius berechnen: `FOV_max / 2`
     - FOV = `(pixel_size × dimension / 1000) / focal_length × 57.296`
     - Fallback 0.5° bei fehlenden Metadaten
   - `find_dominant_object()` im OpenNGC-Katalog:
     - numpy-vectorisierte Distanz (großkreisähnlich mit cos(dec)-Näherung)
     - Maske: alle Objekte innerhalb des Suchradius
     - Gewinner: Objekt mit größtem `MajAx` (Major Axis)
   - Name auflösen: Common Name → Messier → NGC/IC (vom Katalogobjekt)
   - Target erzeugen oder aktualisieren mit Typ (G, PN, Neb, OCl...), Sternbild, Koordinaten
   - `frame.object_name` auf kanonischen Namen setzen
   - `session.target_id` auf (neues) Target setzen
4. Live-Fortschritt via `GET /api/v1/identify/status`, cancelbar

**Nachbedingung**: Frames sind mit Deep-Sky-Objekten verknüpft, Targets ggf. neu angelegt  
**Fehlerszenario**:
- Nichts im Suchfeld → "No object found in field" (z. B. bei Sternfeldern ohne NGC-Objekt)
- Keine RA/Dec → Frame wird übersprungen (muss erst geplated werden, UC-04)

---

### UC-07: Statistiken und Dashboard einsehen

**Akteur**: Benutzer  
**Vorbedingung**: Datenbank befüllt

**Ablauf**:
1. Dashboard (`GET /api/v1/dashboard`) zeigt:
   - Gesamtbelichtungszeit, Frames, Sessions, Targets
   - Top-10 Ziele nach Belichtungszeit (ECharts-Balkendiagramm)
   - Letzte 10 Sessions
   - Kamera-Statistiken (Frames, Belichtung pro Kamera)
2. Detailstatistiken (`GET /api/v1/stats`) zeigen:
   - Genaue Zählung für Targets, Sessions, Frames, Kameras, Teleskope, Kalibrierungsdateien

**Nachbedingung**: Kennzahlen werden angezeigt, regelmäßige Aktualisierung bei Seitenneuladung

---

### UC-08: Einstellungen konfigurieren

**Akteur**: Administrator  
**Vorbedingung**: StellaShelf läuft

**Ablauf**:
1. Einstellungsseite (`/settings`) öffnen
2. Tabs: Allgemein (Scan-Pfade, Theme, ASTAP-Pfad), Equipment-Overrides
3. Einstellungen speichern → `POST /api/v1/settings`
4. ASTAP-Pfad: Wird von Platesolve/Analyse-Tasks ausgelesen (`setting.key = "astap_binary"`)
5. Theme: Dark/Light/System → wird im localStorage gespeichert, nicht im Backend

**Nachbedingung**: Einstellungen persistent in der DB gespeichert, ASTAP-Tasks nutzen den konfigurierten Pfad

---

## 5. Feature-Spezifikationen

### 5.1 Scanner-Pipeline

**Datei**: `scanner.py`

**Eingabe**: Verzeichnispfad  
**Ausgabe**: Liste von `ScannedFrame`-Dataclasses

**Ablauf im Detail**:
1. **Dateisuche** (`find_fits_files`): `.fit`, `.fits`, `.fit.gz`, `.fits.gz` (rekursiv) – XISF wird erkannt aber übersprungen
2. **FITS-Header-Extraktion** (`scan_fits_file`):
   - Öffnen via `astropy.io.fits`
   - Zuerst Extension HDU (gzip-komprimierte SGP-Dateien haben Header in HDU[1]), dann Primary
   - Keys: OBJECT, INSTRUME, TELESCOP, FILTER, EXPOSURE, GAIN, CCD-TEMP, DATE-OBS, DATE-LOC, XBINNING, NAXIS1/2, IMAGETYP, FOCALLEN, XPIXSZ/YPIXSZ, RA, DEC, CRVAL1/2, SITENAME, OBSERVER, CREATOR, BAYERPAT
   - Unterstützt Alias-Namen: EXPOSURE→EXPTIME|EXP_TIME, CCD-TEMP→CCDTEMP|TEMPERAT, etc.
3. **Koordinaten-Parsing**: RA/DEC als Float, HMS/DMS-Strings, CRVAL1/2 (auch als String)
4. **Path-basierte Equipment-Erkennung**: Kamera und Teleskop aus Pfad `Astro/astro/{CAMERA}/_{TELESCOPE}/` extrahieren (überschreibt FITS-Header falls vorhanden)
5. **Frame-Typ-Normalisierung**: `light`/`light frame`/`lightframe` → `LIGHT`, `dark` → `DARK`, etc.
6. **Dateinamen-Fallback** (`parse_filename`): Pattern `{Object}_{Filter}_{Exposure}sec_{Binning}x..._{Temp}_gain_{Gain}_{Seq}` für LIGHT, `master{bias|dark|flat}_{Exposure}s_...` für Calibration
7. **Session-Gruppierung** (`generate_group_key`): `{Object}|{YYYY-MM-DD}|{Camera}|{Telescope}|{Filter}`
8. **Fortschritt**: Rich-Progress-Bar (CLI) oder Callback (API)

### 5.2 Importer

**Datei**: `importer.py` – `ImporterService`

- Zentralisierte Import-Pipeline, von CLI und API gleichermaßen genutzt
- Pre-Load existierender Einträge (Pfade, Sessions, Kameras, Teleskope, Targets) in Sets/Dicts für Performance
- Batch-Commit alle 500 Frames
- Automatische Equipment-Anlage (neue Kameras/Teleskope werden erzeugt)
- Target-Anlage mit Alias-Tracking (abweichende Originalschreibweisen → `alt_names`)
- Kalibrierungsdateien → separate `CalibrationFile`-Tabelle
- Session-Recalculation nach Import: `frame_count`, `total_exposure_s`, `total_exposure_h` per SQL-Update

### 5.3 Namensnormalisierung

**Datei**: `catalog.py` – `normalize_object_name()`

| Eingabe | Ausgabe |
|---|---|
| `M51` | `M51` |
| `m51` | `M51` |
| `M 51` | `M51` |
| `NGC 7000` | `NGC7000` |
| `ngc7000` | `NGC7000` |
| `M 101` | `M101` |
| `IC 434` | `IC434` |
| `SH2-101` | `SH2-101` |
| `LDN 1234` | `LDN 1234` |
| `Whirlpool Galaxy` | `WHIRLPOOL GALAXY` |
| `Orion Nebula` | `ORION NEBULA` |

**Unterstützte Kataloge**: M, NGC, IC, SH2, LDN, vdB, B, C, Mink, Pal, Mel, Cr, Tr  
Nicht-Katalog-Namen werden: uppercase, Leerzeichen normalisiert

### 5.4 Platesolving (ASTAP-Platesolving)

**Datei**: `scanner.py` – `platesolve_frame()`, `api.py` – `_run_platesolve_task()`

**ASTAP-Aufruf**:
```bash
astap_cli -f <FITS> -o <tmp> -r 10 [-ra <h> -spd <deg>]
```

**Parameter**:
- `-r 10`: Suchradius 10° (blind)
- `-ra`/`-spd`: Koordinaten-Hints in Stunden/South-Polar-Distance (optional, aus Target-Metadaten)
- `-o`: Temp-Output (WCS- + INI-Dateien)

**Resultat-Parsing**:
1. WCS-Datei (`.wcs`): `CRVAL1 = 123.456`, `CRVAL2 = 12.345`
2. Fallback INI-Datei (`.ini`): `ra = 123.456`, `dec = 12.345`

**Architektur**:
- State-Dict `_platesolve_state` mit `running`, `total`, `solved`, `failed`, `cancelled`, `log`
- Threading (daemon=True), Lock für State-Updates
- Pro Frame: Datei-Prüfung, Hints-Logik, ASTAP-Call, DB-Update
- Cancel via Flag-Prüfung vor jedem Frame

### 5.5 Qualitätsanalyse (HFD/Stars)

**Datei**: `scanner.py` – `analyse_frame()`, `api.py` – `_run_analyse_task()`

**ASTAP-Aufruf**:
```bash
astap_cli -f <FITS> -analyse 30
```

**Stdout-Parsing**:
```
HFD_MEDIAN=4.2
STARS=1234
```

**Felder auf Frame**: `hfd_median` (Float), `stars_detected` (Integer)

**Architektur**: Analog zu Platesolving, State-Dict `_analyse_state`

### 5.6 Objektidentifikation (Reverse Sky Lookup)

**Datei**: `skylookup.py` – `load_catalog()`, `find_dominant_object()`, `resolve_target_name()`, `compute_search_radius()`

**Katalog-Loader** (`load_catalog`):
- Lädt `data/NGC.csv` + `data/addendum.csv` (OpenNGC, delimiter `;`)
- Filtert: keine Sterne (`*`, `**`), Duplikate, NonEx, Other
- Typen-Filter: nur Deep-Sky-Objekte (G, PN, HII, Neb, OCl, GCl, SNR, etc.)
- Konvertiert RA/Dec von HMS/DMS in Grad
- Speichert als numpy-Arrays (`coords: float64[N,2]`, `majax: float64[N]`)
- lru_cached (maxsize=1) – einmaliger Ladevorgang

**Objekt-Suche** (`find_dominant_object`):
- `coords[:, 0] - ra` mit cos(dec)-Korrektur
- `dists <= radius` → Maske
- Gewinner: `argmax(majax[mask])` (größte Major Axis → prominentestes Objekt)
- Rückgabe: dict mit name, ra_deg, dec_deg, majax, type, common_names, messier, constellation, dist_deg

**Name-Resolution** (`resolve_target_name`):
1. `common_names` vorhanden? → verwenden (z. B. "Whirlpool Galaxy")
2. Sonst `messier` vorhanden? → "M{number}" (z. B. "M51")
3. Sonst NGC/IC-Name (z. B. "NGC5194")

**Suchradius** (`compute_search_radius`):
```
FOV_w = (width_px * pixel_size_um / 1000 / focal_length_mm) * 57.296
FOV_h = (height_px * pixel_size_um / 1000 / focal_length_mm) * 57.296
radius = max(FOV_w, FOV_h) / 2
Fallback: 0.5°
```

**Identify-Logik** (API):
- Alle LIGHT-Frames mit RA/Dec
- Pro Frame: Radius berechnen → OpenNGC-Suche → Target erstellen/aktualisieren
- `frame.object_name` auf kanonischen Namen überschreiben
- `session.target_id` auf (neues) Target updaten
- Target-Daten: name, alt_names, object_type, constellation, ra_deg, dec_deg

### 5.7 Thumbnails

**Datei**: `scanner.py` – `generate_thumbnail()`

- Letzte HDU (meist die mit Bilddaten) verwenden
- Bei 3D-Daten: ersten Frame oder Mittelwert (axis=0)
- NaN/Inf → 0
- Percentile-Stretching (5%–95%) für Kontrastoptimierung
- Auf 200px (Normal) oder ~25% (Preview) resizen via Pillow LANCZOS
- JPEG-Qualität 85
- Base64-Inline für Target-Thumbnails-Liste

### 5.8 FTS5-Volltextsuche

**Datei**: `db.py`

**Virtual Table**: `frames_fts` mit Spalten: `object_name`, `instrume`, `telescop`, `filter_name`, `filename`, `site_name`

**Trigger**:
- `frames_fts_ai`: AFTER INSERT → neuen Frame in FTS5 aufnehmen
- `frames_fts_ad`: AFTER DELETE → Frame aus FTS5 entfernen
- `frames_fts_au`: AFTER UPDATE → alten löschen, neuen einfügen

**API**: `GET /api/v1/search?q=...` – MATCH-Query auf frames_fts + ILIKE auf Targets/Sessions

---

## 6. API-Referenz

### 6.1 Health & System

| Method | Path | Beschreibung | Parameter | Response |
|---|---|---|---|---|
| GET | `/api/v1/health` | Health-Check | – | `{"status":"ok","version":"0.4.0","build":"b31.4e251a3.main","db":"/path/to/db"}` |
| GET | `/api/v1/dashboard` | Dashboard-Kennzahlen | – | `{total_exposure_h, total_frames, total_sessions, total_targets, top_targets[], recent_sessions[], cameras[]}` |
| GET | `/api/v1/stats` | Exakte Zählungen | – | `{targets, sessions, frames, cameras, telescopes, calibration_files, total_exposure_h}` |
| GET | `/api/v1/search` | Volltextsuche | `q` (Query), `limit` (1–100, Default 20) | `{targets[], sessions[], frames[]}` |

### 6.2 Scan

| Method | Path | Beschreibung | Request | Response |
|---|---|---|---|---|
| POST | `/api/v1/scan` | Scan starten | `{"path": "/data/astro", "recursive": true}` | `{"status":"started","path":"/data/astro"}` |
| GET | `/api/v1/scan/status` | Scan-Fortschritt | – | `{running, total, processed, imported, skipped, phase, error, current_file}` |

### 6.3 Targets

| Method | Path | Beschreibung | Parameter | Response |
|---|---|---|---|---|
| GET | `/api/v1/targets` | Targets mit Paginierung | `search, object_type, constellation, sort_by, sort_order, page, page_size` | `{total, page, page_size, pages, items: TargetSchema[]}` |
| GET | `/api/v1/targets/types` | Distinct-Typen/Sternbilder | – | `{object_types: string[], constellations: string[]}` |
| GET | `/api/v1/targets/{id}` | Target-Detail | – | `TargetSchema` |
| GET | `/api/v1/targets/{id}/sessions` | Sessions eines Targets | `camera_id, sort_by, sort_order, page, page_size` | `SessionListResponse` |
| GET | `/api/v1/targets/{id}/thumbnails` | Neueste Thumbnails | `limit` (1–20) | `[{id, filename, filter_name, exposure, date_obs, thumbnail: base64}]` |
| GET | `/api/v1/targets/duplicates` | Duplikat-Gruppen | – | `[{canonical_name, targets: [{id, name, session_count}]}]` |
| POST | `/api/v1/targets/merge` | Zwei Targets mergen | `{source_id, destination_id}` | `{status, target_id, name}` |
| POST | `/api/v1/targets/merge-group` | Auto-merge per Name | `{canonical_name}` | `{status, target_id, name, merged_ids[], merged_count}` |

### 6.4 Sessions

| Method | Path | Beschreibung | Parameter | Response |
|---|---|---|---|---|
| GET | `/api/v1/sessions` | Sessions-Liste | `target_id, camera_id, telescope_id, filter_name, status, date_from, date_to, sort_by, sort_order, page, page_size` | `SessionListResponse` |
| GET | `/api/v1/sessions/{id}` | Session-Detail | – | `SessionSchema` |
| GET | `/api/v1/sessions/{id}/stats` | Aggregierte Statistiken | – | `{frame_type_counts: {}, exposure_per_filter: []}` |
| PATCH | `/api/v1/sessions/{id}` | Status-Update | `{status: "raw|calibrated|stacked"}` | `{status, session_id, new_status}` |

### 6.5 Frames

| Method | Path | Beschreibung | Parameter | Response |
|---|---|---|---|---|
| GET | `/api/v1/frames` | Frames-Liste | `session_id, object_name, filter_name, frame_type, camera, has_coordinates, filename, filepath, sort_by, sort_order, page, page_size` | `FrameListResponse` (Schema: id, session_id, filename, filepath, frame_type, object_name, filter_name, exposure, gain, ccd_temp, binning, date_obs, **hfd_median**, **stars_detected**) |
| GET | `/api/v1/frames/{id}` | Frame-Detail | – | `FrameDetailSchema` (zusätzlich: file_size, instrume, telescop, width, height, pixel_size_um, **ra_deg**, **dec_deg**, focal_length_mm, site_name, observer, creator, fwhm, eccentricity, snr) |
| GET | `/api/v1/frames/{id}/thumbnail` | JPEG-Thumbnail | `?preview=true/false` | Image/JPEG (200px normal, ~25% preview) |
| POST | `/api/v1/frames/delete` | Bulk-Delete | `{frame_ids: [1,2,3]}` | `{status, deleted: N, affected_sessions: M}` |

### 6.6 Equipment

| Method | Path | Beschreibung | Response |
|---|---|---|---|
| GET | `/api/v1/cameras` | Kameras mit Nutzungsstatistik | `[{id, name, short_name, pixel_size_um, frame_count, total_exposure_h}]` |
| GET | `/api/v1/telescopes` | Teleskope mit Nutzungsstatistik | `[{id, name, short_name, focal_length_mm, frame_count, total_exposure_h}]` |
| GET | `/api/v1/filters` | Filter mit Nutzungsstatistik | `[{name, frame_count, total_exposure_h}]` |

### 6.7 Platesolving

| Method | Path | Beschreibung | Request | Response |
|---|---|---|---|---|
| POST | `/api/v1/platesolve` | Platesolving starten | – | `{"status":"started"}` |
| GET | `/api/v1/platesolve/status` | Platesolving-Fortschritt | – | `{running, total, solved, failed, phase, error, cancelled, log[]}` |
| POST | `/api/v1/platesolve/cancel` | Platesolving abbrechen | – | `{"status":"cancelling"}` |

### 6.8 Analyse (HFD/Stars)

| Method | Path | Beschreibung | Request | Response |
|---|---|---|---|---|
| POST | `/api/v1/analyse` | Analyse starten | – | `{"status":"started"}` |
| GET | `/api/v1/analyse/status` | Analyse-Fortschritt | – | `{running, total, analysed, failed, phase, error, cancelled, log[]}` |
| POST | `/api/v1/analyse/cancel` | Analyse abbrechen | – | `{"status":"cancelling"}` |

### 6.9 Identifikation

| Method | Path | Beschreibung | Request | Response |
|---|---|---|---|---|
| POST | `/api/v1/identify` | Identifikation starten | – | `{"status":"started"}` |
| GET | `/api/v1/identify/status` | Identifikation-Fortschritt | – | `{running, total, identified, failed, phase, error, cancelled, log[]}` |
| POST | `/api/v1/identify/cancel` | Identifikation abbrechen | – | `{"status":"cancelling"}` |

### 6.10 Settings & Database

| Method | Path | Beschreibung | Request | Response |
|---|---|---|---|---|
| GET | `/api/v1/settings` | Alle Einstellungen | – | `[{key, value, description}]` |
| POST | `/api/v1/settings` | Einstellungen speichern | `[{key, value, description}]` | `{"status":"ok"}` |
| POST | `/api/v1/db/reset` | DB zurücksetzen | `{"confirm": true}` | `{"status":"ok","message":"Database reset complete"}` |
| POST | `/api/v1/db/cleanup-orphans` | Orphan-Bereinigung | – | `{"status":"ok","sessions":N,"targets":N,"cameras":N,"telescopes":N}` |

---

## 7. Hintergrundprozesse

### 7.1 Gemeinsame Architektur

Alle vier Hintergrundprozesse (Scan, Platesolve, Analyse, Identify) folgen demselben Muster:

1. **State-Dict**: Ein globales Dict mit Statusinformationen, per Thread-Lock geschützt
2. **Threading**: `threading.Thread(daemon=True)`, startet via POST-Endpoint
3. **Cancel**: Boolean-Flag im State-Dict, vor jeder Datei geprüft
4. **Logging**: Array von `{frame, status, detail}`-Dicts für das UI

### 7.2 State-Dicts

**Scan-State**:
```python
{
    "running": bool, "total": int, "processed": int,
    "imported": int, "skipped": int, "calibration_files": int,
    "current_file": str, "phase": "idle|scanning|done|error",
    "error": str | None
}
```

**Platesolve/Analyse/Identify-State** (analog):
```python
{
    "running": bool, "total": int, "solved|analysed|identified": int,
    "failed": int, "phase": "idle|solving|analysing|identifying|done|error|cancelled",
    "error": str | None, "cancelled": bool,
    "log": [{"frame": str, "status": str, "detail": str}]
}
```

### 7.3 Ablauf eines Background-Tasks

```
POST /api/v1/{action}
  ├─ Lock prüfen (409 wenn bereits laufend)
  ├─ State initialisieren
  ├─ Thread starten → sofort return 200
  │
  └─ Thread:
       ├─ DB: Query für zu bearbeitende Frames
       ├─ Schleife über Frames:
       │   ├─ Cancel prüfen
       │   ├─ Datei-Existenz prüfen
       │   ├─ Aktion ausführen (ASTAP-CLI / OpenNGC-Suche)
       │   ├─ State updaten (Lock)
       │   └─ Bei Cancel: break
       ├─ DB-Commit
       └─ State auf "done" oder "cancelled" setzen
```

---

## 8. Frontend

### 8.1 Views (13)

| Route | View | Beschreibung |
|---|---|---|
| `/` | Dashboard.vue | Stats, Top-10 Targets, Recent Sessions, ECharts-Balkendiagramm |
| `/targets` | Targets.vue | Filterbare/sortierbare Target-Liste mit Typ-Badges |
| `/targets/:id` | TargetDetail.vue | Target-Info, Thumbnails, Session-Liste |
| `/sessions` | Sessions.vue | Filterbare/sortierbare Session-Liste |
| `/sessions/:id` | SessionDetail.vue | Frames-Liste mit Paginierung, Filterung, Aggregaten (Frames pro Typ, Belichtung pro Filter), HFD/Stars-Spalten |
| `/equipment` | Equipment.vue | Tabs: Kameras, Teleskope, Filter – sortierbar mit Nutzungsstatistik |
| `/search` | Search.vue | FTS5-Volltextsuche mit Tabbed Results (Targets/Sessions/Frames) |
| `/scan` | Scan.vue | Directory-Scanner mit Live-Fortschritt |
| `/platesolve` | Platesolve.vue | ASTAP-Platesolving mit Log, Fortschrittsbalken, Cancel |
| `/analyse` | Analyse.vue | ASTAP-HFD-Analyse mit Log, Fortschrittsbalken, Cancel |
| `/identify` | Identify.vue | OpenNGC-Objektidentifikation mit Log, Fortschrittsbalken, Cancel |
| `/settings` | Settings.vue | Tabs: Allgemein (Pfade, Theme, ASTAP), Equipment-Overrides |
| `/help` | Help.vue | Dokumentation und Tastaturkürzel |

### 8.2 Pinia Stores (6)

| Store | Zweck |
|---|---|
| `api.ts` | Zentraler HTTP-Client mit Loading/Error-State |
| `scan.ts` | Scan-Progress-Polling (500ms) |
| `theme.ts` | Dark/Light/System mit localStorage |
| `platesolve.ts` | Platesolve-Status-Polling + Log |
| `analyse.ts` | Analyse-Status-Polling + Log |
| `identify.ts` | Identify-Status-Polling + Log |

### 8.3 Routen-Konfiguration

```typescript
{
  path: "/",         name: "dashboard",  component: Dashboard
  path: "/targets",  name: "targets",    component: Targets
  path: "/targets/:id", name: "target-detail", component: TargetDetail
  path: "/sessions", name: "sessions",   component: Sessions
  path: "/sessions/:id", name: "session-detail", component: SessionDetail
  path: "/equipment", name: "equipment", component: Equipment
  path: "/search",   name: "search",     component: Search
  path: "/scan",     name: "scan",       component: Scan
  path: "/platesolve", name: "platesolve", component: Platesolve
  path: "/analyse",  name: "analyse",    component: Analyse
  path: "/identify", name: "identify",   component: Identify
  path: "/settings", name: "settings",   component: Settings
  path: "/help",     name: "help",       component: Help
}
```

---

## 9. Constraints & Designentscheidungen

### 9.1 Datenbank-Migrationen
**Keine Migrationen.** Bei Schema-Änderungen wird die bestehende Datenbank gelöscht und neu aufgebaut (`DELETE FROM` + `DROP TABLE` für Triggern). Dies ist ein Design-Constraint für die persönliche Nutzung ohne Produktionsdaten.

### 9.2 Name-Resolution-Priorität (Identify)
1. **Common Name** (z. B. "Whirlpool Galaxy") → höchste Priorität
2. **Messier-Nummer** (z. B. "M51") → mittlere Priorität
3. **NGC/IC-Name** (z. B. "NGC5194") → Fallback

### 9.3 Suchradius-Logik
- Berechnet aus FOV: `FOV = (pixel_size × dimension / 1000) / focal_length × 57.296`
- `radius = max(FOV_w, FOV_h) / 2`
- Fallback: `0.5°` wenn Metadaten fehlen
- OpenNGC-Suche: kosinus-korrigierte Distanz (Näherung für kleine Winkel)

### 9.4 In-Memory-Katalog
- OpenNGC-Katalog wird beim ersten Zugriff via `lru_cache` geladen
- numpy-Arrays (`coords`, `majax`) für vektorisierte Distanzberechnung
- Keine SciPy-Abhängigkeit – rein numpy-basiert
- ~14k Objekte, davon 99,5% mit MajAx-Daten

### 9.5 Frame.object_name Überschreibung
Bei Identify wird `frame.object_name` auf den kanonischen Target-Namen gesetzt, unabhängig vom ursprünglichen FITS-Header. Dadurch kann ein Frame nachträglich einem korrekten Zielobjekt zugeordnet werden.

### 9.6 Session.target_id Update
Identify aktualisiert `session.target_id` auf das identifizierte Target, basierend auf dem häufigsten Zielobjekt der Frames einer Session.

### 9.7 ASTAP CLI
- Nur `-analyse` Flag wird verwendet (HFD + Stars)
- `-extract` → NICHT verwendet (schreibt CSV neben Original, liefert HFD_MEDIAN=99.0)
- `-sqm` → NICHT verwendbar im CLI-Mode (nur in GUI-Version)
- D80- + V50-Sternendatenbank installiert, V50 verbessert HFD-Genauigkeit

### 9.8 FrameSchema vs. FrameDetailSchema
- `FrameSchema` (List-Ansicht): enthält `hfd_median`, `stars_detected`, aber **nicht** `ra_deg`/`dec_deg`
- `FrameDetailSchema` (Einzelansicht): enthält alle Felder inkl. `ra_deg`, `dec_deg`, `fwhm`, etc.

### 9.9 UI-Sprache
Das Frontend ist auf **Deutsch** (UI-Texte, Banner, Benennungen). Code-Kommentare und technische Dokumentation sind auf Englisch.

### 9.10 Ruff Linting
- `ruff check` + `ruff format` müssen vor jedem Push passieren
- Line-Length: 100
- Per-File-Ignores für SQL-Strings in db.py, importer.py, api.py

---

## 10. Offene Punkte / Ideenspeicher

### 10.1 SIMBAD TAP API als Fallback
**Status**: Dokumentiert in roadmap.md, nicht implementiert

Falls der lokale OpenNGC-Katalog kein passendes Objekt findet, könnte eine SIMBAD TAP Cone-Search als Online-Fallback dienen. SIMBAD sortiert nach `nbref DESC` (Anzahl Referenzen), sodass das prominenteste Objekt identifiziert wird.

- Endpoint: `http://simbad.cds.unistra.fr/simbad/sim-tap/sync`
- Keine zusätzlichen Dependencies (stdlib urllib reicht)
- Abdeckung: Millionen Objekte (Sharpless, LDN, Barnard, etc.)
- Ca. 50–300ms pro Query, Rate-Limit ~5–10 req/s

### 10.2 SQM (Sky Quality Meter)
**Status**: Nicht in ASTAP CLI verfügbar – benötigt GUI-Version oder V50-Photometrie-DB-Integration

### 10.3 Siril-Integration (Milestone 5)
- Siril-Script-Generator (`.sss`) pro Session
- Pipeline: Calibration → Registration → Stacking → PCC
- Remote-Execution via SSH zur Workstation
- WebSocket-Status-Tracking
- Result-Preview (gestapeltes Thumbnail)

### 10.4 XISF-Parsing
- Dateien werden erkannt aber übersprungen
- Benötigt Parser-Integration (z. B. via `xisf`-Bibliothek oder Sirius-FITS-Konverter)

### 10.5 RAW-Format-Support
- Canon CR2/CR3, Nikon NEF, Sony ARW via `rawpy`
- Optionale Dependency

### 10.6 Docker-Deployment (Milestone 6)
- Docker-Compose-Konfiguration
- NFS-Mount für Astro-Daten
- Production-Variant mit Uvicorn + nginx

### 10.7 Frontend-Optimierung
- Code-Splitting (aktuelles JS-Bundle: ~1,3 MB)
- Lazy-Loading für schwere Views
- Komponenten-Refactoring für bessere Tree-Shakeability

### 10.8 Performance für große Sammlungen (>10k Frames)
- Indizes-Optimierung
- Batch-Queries
- Lazy-Loading für Thumbnails
- Paginierung-Optimierung

### 10.9 Pre-commit Hook
- Automatischer `generate_build.py`-Aufruf vor jedem Commit
- Aktualisiert `_build.py` mit aktueller Build-Nummer

---

*Ende der Spezifikation – erstellt aus dem aktuellen Projektstand v0.4.0 (build b31.4e251a3.main)*
