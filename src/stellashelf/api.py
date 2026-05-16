"""StellaShelf FastAPI application.

REST API for browsing astrophotography sessions, frames, and equipment.
Supports pagination, filtering, and full-text search.
"""

import os
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func as sa_func
from sqlalchemy import text

from stellashelf import __version__
from stellashelf.config import DEFAULT_DB_PATH
from stellashelf.db import CalibrationFile, Camera, Frame, Setting, Target, Telescope, init_db
from stellashelf.db import Session as ObsSession
from stellashelf.importer import ImporterService
from stellashelf.scanner import generate_thumbnail, platesolve_frame

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------

_db_path: Path = DEFAULT_DB_PATH
_engine = None
_session_local = None
_engine_lock = threading.Lock()


def set_db_path(path: Path) -> None:
    """Override the database path and reset cached engine."""
    global _db_path, _engine, _session_local
    with _engine_lock:
        _db_path = path
        _engine = None
        _session_local = None


def get_session_local():
    """Return cached (engine, SessionLocal), initializing once."""
    global _engine, _session_local
    if _session_local is None:
        with _engine_lock:
            if _session_local is None:
                if not _db_path.exists():
                    raise RuntimeError(
                        f"Database not found at {_db_path}. Run 'stellashelf scan' first."
                    )
                _engine, _session_local = init_db(_db_path)
    return _engine, _session_local


app = FastAPI(title="StellaShelf", version=__version__)

_cors_origins = os.environ.get("STELLASHELF_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Scan state management
# ---------------------------------------------------------------------------

_scan_lock = threading.Lock()
_scan_state: dict = {
    "running": False,
    "total": 0,
    "processed": 0,
    "imported": 0,
    "skipped": 0,
    "calibration_files": 0,
    "current_file": "",
    "phase": "idle",
    "error": None,
}

_platesolve_lock = threading.Lock()
_platesolve_state: dict = {
    "running": False,
    "total": 0,
    "solved": 0,
    "failed": 0,
    "phase": "idle",
    "error": None,
    "cancelled": False,
    "log": [],
}


def _make_scan_progress_callback():
    """Create a progress callback for the scanner that updates _scan_state."""

    def callback(processed: int, total: int, current_file: Path):
        with _scan_lock:
            _scan_state["processed"] = processed
            _scan_state["total"] = total
            _scan_state["current_file"] = str(current_file)
            _scan_state["phase"] = "scanning"

    return callback


def _run_scan_task(root: Path, recursive: bool):
    """Background thread task: delegates scan and import to ImporterService."""
    global _scan_state
    try:
        importer = ImporterService(_db_path)
        progress_cb = _make_scan_progress_callback()

        with _scan_lock:
            _scan_state["phase"] = "scanning"
            _scan_state["running"] = True

        stats = importer.import_from_path(root, recursive=recursive, progress_callback=progress_cb)

        with _scan_lock:
            _scan_state["phase"] = "done"
            _scan_state["imported"] = stats["imported"]
            _scan_state["skipped"] = stats["skipped"]
            _scan_state["calibration_files"] = stats["calibration_files"]
            _scan_state["running"] = False
            _scan_state["error"] = None

    except Exception as e:
        with _scan_lock:
            _scan_state["running"] = False
            _scan_state["phase"] = "error"
            _scan_state["error"] = str(e)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TargetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    object_type: str | None = None
    constellation: str | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    session_count: int = 0
    total_exposure_h: float = 0


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    target_name: str = ""
    camera_name: str | None = None
    telescope_name: str | None = None
    date_obs: datetime | None = None
    group_key: str
    status: str
    total_exposure_s: float
    total_exposure_h: float
    frame_count: int
    folder_path: str | None = None


class FrameSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: int | None
    filename: str
    filepath: str
    frame_type: str | None = None
    object_name: str | None = None
    filter_name: str | None = None
    exposure: float | None
    gain: int | None
    ccd_temp: float | None
    binning: int
    date_obs: datetime | None


class FrameDetailSchema(FrameSchema):
    file_size: int | None = None
    instrume: str | None = None
    telescop: str | None = None
    date_local: datetime | None = None
    width: int | None = None
    height: int | None = None
    pixel_size_um: float | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    focal_length_mm: float | None = None
    site_name: str | None = None
    observer: str | None = None
    creator: str | None = None
    fwhm: float | None = None
    eccentricity: float | None = None
    snr: float | None = None


class CameraSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_name: str | None
    pixel_size_um: float | None
    frame_count: int = 0
    total_exposure_h: float = 0


class TelescopeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_name: str | None
    focal_length_mm: float | None
    frame_count: int = 0
    total_exposure_h: float = 0


class CalibrationFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_id: int | None
    cal_type: str
    exposure_s: float | None
    gain: int | None
    binning: int
    ccd_temp: float | None
    filepath: str
    filename: str


class MergeRequest(BaseModel):
    source_id: int
    destination_id: int


class MergeGroupRequest(BaseModel):
    canonical_name: str


class DbResetRequest(BaseModel):
    confirm: bool = False


# ---------------------------------------------------------------------------
# Paginated response wrappers
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


class TargetListResponse(PaginatedResponse):
    items: list[TargetSchema]


class SessionListResponse(PaginatedResponse):
    items: list[SessionSchema]


class FrameListResponse(PaginatedResponse):
    items: list[FrameSchema]


class CameraListResponse(PaginatedResponse):
    items: list[CameraSchema]


class TelescopeListResponse(PaginatedResponse):
    items: list[TelescopeSchema]


# ---------------------------------------------------------------------------
# Scan API
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    path: str
    recursive: bool = True


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "db": str(_db_path)}


@app.get("/api/v1/search")
def search_all(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """Full-text search across targets, sessions, and frames via FTS5."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        # Search frames via FTS5
        fts_results = session.execute(
            text(
                "SELECT frames.id, frames.object_name, frames.filename, "
                "frames.frame_type, frames.date_obs "
                "FROM frames "
                "JOIN frames_fts ON frames_fts.rowid = frames.id "
                "WHERE frames_fts MATCH :q "
                "LIMIT :limit"
            ),
            {"q": q, "limit": limit},
        ).fetchall()

        # Search targets by name
        target_results = (
            session.query(Target.id, Target.name, Target.object_type)
            .filter(Target.name.ilike(f"%{q}%"))
            .limit(limit)
            .all()
        )

        # Search sessions by target name
        session_results = (
            session.query(
                ObsSession.id, ObsSession.group_key, ObsSession.date_obs, ObsSession.frame_count
            )
            .join(Target, Target.id == ObsSession.target_id)
            .filter(Target.name.ilike(f"%{q}%"))
            .limit(limit)
            .all()
        )

        return {
            "targets": [
                {"id": t.id, "name": t.name, "type": t.object_type} for t in target_results
            ],
            "sessions": [
                {
                    "id": s.id,
                    "group_key": s.group_key,
                    "date_obs": str(s.date_obs) if s.date_obs else None,
                    "frame_count": s.frame_count,
                }
                for s in session_results
            ],
            "frames": [
                {
                    "id": f.id,
                    "object_name": f.object_name,
                    "filename": f.filename,
                    "frame_type": f.frame_type,
                }
                for f in fts_results
            ],
        }


@app.post("/api/v1/scan")
def start_scan(request: ScanRequest):
    """Start a background scan of FITS files."""
    global _scan_state

    with _scan_lock:
        if _scan_state["running"]:
            raise HTTPException(status_code=409, detail="A scan is already running")

    scan_path = Path(request.path)
    resolved = scan_path.resolve()

    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"Path not found: {resolved}")

    with _scan_lock:
        _scan_state["running"] = True
        _scan_state["total"] = 0
        _scan_state["processed"] = 0
        _scan_state["imported"] = 0
        _scan_state["skipped"] = 0
        _scan_state["calibration_files"] = 0
        _scan_state["current_file"] = "Initializing..."
        _scan_state["phase"] = "scanning"
        _scan_state["error"] = None

    thread = threading.Thread(
        target=_run_scan_task, args=(resolved, request.recursive), daemon=True
    )
    thread.start()

    return {"status": "started", "path": str(resolved)}


@app.get("/api/v1/scan/status")
def scan_status():
    """Get current scan progress."""
    with _scan_lock:
        return dict(_scan_state)


# ---------------------------------------------------------------------------
# Dashboard / Aggregation endpoints
# ---------------------------------------------------------------------------


@app.get("/api/v1/dashboard")
def get_dashboard():
    """Aggregated dashboard data: totals, top targets, recent sessions."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        total_exposure_h = session.query(sa_func.sum(ObsSession.total_exposure_h)).scalar() or 0
        total_frames = session.query(Frame).count()
        total_sessions = session.query(ObsSession).count()
        total_targets = session.query(Target).count()

        # Top 10 targets by exposure
        top_targets = (
            session.query(
                Target.id,
                Target.name,
                sa_func.sum(ObsSession.total_exposure_h).label("total_h"),
                sa_func.count(ObsSession.id).label("session_count"),
            )
            .join(ObsSession, ObsSession.target_id == Target.id)
            .group_by(Target.id, Target.name)
            .order_by(sa_func.sum(ObsSession.total_exposure_h).desc())
            .limit(10)
            .all()
        )

        # Recent 10 sessions
        recent = (
            session.query(
                ObsSession.id,
                ObsSession.target_id,
                ObsSession.date_obs,
                ObsSession.total_exposure_h,
                ObsSession.frame_count,
                ObsSession.path.label("folder_path"),
                Target.name.label("target_name"),
            )
            .join(Target, Target.id == ObsSession.target_id)
            .filter(ObsSession.date_obs.isnot(None))
            .order_by(ObsSession.date_obs.desc())
            .limit(10)
            .all()
        )

        # Camera usage stats
        camera_stats = (
            session.query(
                Camera.id,
                Camera.name,
                Camera.short_name,
                Camera.pixel_size_um,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.coalesce(sa_func.sum(Frame.exposure), 0).label("total_s"),
            )
            .outerjoin(ObsSession, ObsSession.camera_id == Camera.id)
            .outerjoin(Frame, Frame.session_id == ObsSession.id)
            .group_by(Camera.id, Camera.name, Camera.short_name, Camera.pixel_size_um)
            .order_by(sa_func.count(Frame.id).desc())
            .all()
        )

        return {
            "total_exposure_h": round(total_exposure_h, 1),
            "total_frames": total_frames,
            "total_sessions": total_sessions,
            "total_targets": total_targets,
            "top_targets": [
                {
                    "id": t.id,
                    "name": t.name,
                    "total_exposure_h": round(t.total_h, 1),
                    "session_count": t.session_count,
                }
                for t in top_targets
            ],
            "recent_sessions": [
                {
                    "id": s.id,
                    "target_id": s.target_id,
                    "target_name": s.target_name,
                    "date_obs": s.date_obs,
                    "total_exposure_h": round(s.total_exposure_h, 1),
                    "frame_count": s.frame_count,
                }
                for s in recent
            ],
            "cameras": [
                {
                    "id": c.id,
                    "name": c.name,
                    "short_name": c.short_name,
                    "frame_count": c.frame_count,
                    "total_exposure_h": round(c.total_s / 3600, 1),
                }
                for c in camera_stats
            ],
        }


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@app.get("/api/v1/targets", response_model=TargetListResponse)
def list_targets(
    search: str | None = Query(None, description="Search targets by name"),
    object_type: str | None = Query(
        None, description="Filter by object type (e.g. Galaxy, Nebula)"
    ),
    constellation: str | None = Query(None, description="Filter by constellation"),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = session.query(
            Target.id,
            Target.name,
            Target.object_type,
            Target.constellation,
            Target.ra_deg,
            Target.dec_deg,
            sa_func.count(ObsSession.id).label("session_count"),
            sa_func.coalesce(sa_func.sum(ObsSession.total_exposure_h), 0).label("total_h"),
        ).outerjoin(ObsSession, ObsSession.target_id == Target.id)

        if search:
            q = q.filter(Target.name.ilike(f"%{search}%"))
        if object_type:
            q = q.filter(Target.object_type == object_type)
        if constellation:
            q = q.filter(Target.constellation == constellation)

        # Group by target
        q = q.group_by(
            Target.id,
            Target.name,
            Target.object_type,
            Target.constellation,
            Target.ra_deg,
            Target.dec_deg,
        )

        total = q.count()
        pages = (total + page_size - 1) // page_size

        if sort_by in ("name", "object_type", "constellation", "total_h", "session_count"):
            col = (
                getattr(Target, sort_by, Target.name)
                if sort_by not in ("total_h", "session_count")
                else sa_func.coalesce(sa_func.sum(ObsSession.total_exposure_h), 0)
                if sort_by == "total_h"
                else sa_func.count(ObsSession.id)
            )
            order_col = col.desc() if sort_order == "desc" else col.asc()
        else:
            order_col = Target.name.asc()

        q = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size)

        items = [
            TargetSchema(
                id=r.id,
                name=r.name,
                object_type=r.object_type,
                constellation=r.constellation,
                ra_deg=r.ra_deg,
                dec_deg=r.dec_deg,
                session_count=r.session_count,
                total_exposure_h=round(r.total_h, 1),
            )
            for r in q.all()
        ]

        return TargetListResponse(
            total=total, page=page, page_size=page_size, pages=pages, items=items
        )


@app.get("/api/v1/targets/types")
def list_target_types():
    """Get distinct object types and constellations for filter dropdowns."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        types = [
            row[0]
            for row in session.query(Target.object_type)
            .distinct()
            .filter(Target.object_type.isnot(None))
            .order_by(Target.object_type)
            .all()
        ]
        constellations = [
            row[0]
            for row in session.query(Target.constellation)
            .distinct()
            .filter(Target.constellation.isnot(None))
            .order_by(Target.constellation)
            .all()
        ]
        return {"object_types": types, "constellations": constellations}


# ---------------------------------------------------------------------------
# Target Merge & Duplicate Detection
# ---------------------------------------------------------------------------


@app.get("/api/v1/targets/duplicates")
def find_duplicate_targets():
    """Find targets that are likely duplicates based on normalized name matching."""
    from stellashelf.catalog import normalize_object_name

    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        targets = session.query(Target).all()
        groups: dict[str, list[Target]] = {}
        for t in targets:
            norm = normalize_object_name(t.name)
            if norm not in groups:
                groups[norm] = []
            groups[norm].append(t)

        duplicates = []
        for norm, group in groups.items():
            if len(group) > 1:
                duplicates.append(
                    {
                        "canonical_name": norm,
                        "targets": [
                            {
                                "id": t.id,
                                "name": t.name,
                                "session_count": len(t.sessions) if t.sessions else 0,
                            }
                            for t in group
                        ],
                    }
                )
        return duplicates


@app.post("/api/v1/targets/merge")
def merge_targets(req: MergeRequest):
    """Merge source target into destination target.

    Moves all sessions from source to destination.
    Adds source name(s) to destination alt_names.
    Deletes source target.
    """
    if req.source_id == req.destination_id:
        raise HTTPException(400, "Cannot merge a target into itself")

    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        source = session.get(Target, req.source_id)
        dest = session.get(Target, req.destination_id)
        if not source or not dest:
            raise HTTPException(404, "Source or destination target not found")

        session.query(ObsSession).filter(ObsSession.target_id == source.id).update(
            {"target_id": dest.id}
        )

        session.query(Frame).filter(Frame.object_name == source.name).update(
            {"object_name": dest.name}
        )

        all_aliases = set()
        if dest.alt_names:
            all_aliases.update(dest.alt_names.split(","))
        all_aliases.add(source.name)
        if source.alt_names:
            all_aliases.update(source.alt_names.split(","))
        all_aliases.discard(dest.name)
        all_aliases.discard("")
        dest.alt_names = ",".join(sorted(all_aliases)) if all_aliases else None

        if dest.ra_deg is None and source.ra_deg is not None:
            dest.ra_deg = source.ra_deg
            dest.dec_deg = source.dec_deg

        session.flush()

        session.execute(
            text(
                """
            UPDATE sessions SET
                frame_count = (SELECT COUNT(*) FROM frames WHERE frames.session_id = sessions.id),
                total_exposure_s = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0),
                total_exposure_h = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0) / 3600.0
            WHERE sessions.target_id = :dest_id
            """
            ),
            {"dest_id": dest.id},
        )

        session.flush()
        session.execute(text("DELETE FROM targets WHERE id = :tid"), {"tid": source.id})
        session.commit()

        return {"status": "ok", "target_id": dest.id, "name": dest.name}


@app.post("/api/v1/targets/merge-group")
def merge_target_group(req: MergeGroupRequest):
    """Auto-merge all targets with the given canonical name into one.

    Keeps the target with the most sessions, merges all others into it.
    """
    from stellashelf.catalog import normalize_object_name

    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        all_targets = session.query(Target).all()
        group = [t for t in all_targets if normalize_object_name(t.name) == req.canonical_name]

        if len(group) < 2:
            raise HTTPException(400, "No duplicates found for this name")

        group.sort(key=lambda t: len(t.sessions) if t.sessions else 0, reverse=True)
        keep = group[0]
        merged = []
        for t in group[1:]:
            session.query(ObsSession).filter(ObsSession.target_id == t.id).update(
                {"target_id": keep.id}
            )
            session.query(Frame).filter(Frame.object_name == t.name).update(
                {"object_name": keep.name}
            )
            all_aliases = set()
            if keep.alt_names:
                all_aliases.update(keep.alt_names.split(","))
            all_aliases.add(t.name)
            if t.alt_names:
                all_aliases.update(t.alt_names.split(","))
            all_aliases.discard(keep.name)
            all_aliases.discard("")
            keep.alt_names = ",".join(sorted(all_aliases)) if all_aliases else None
            if keep.ra_deg is None and t.ra_deg is not None:
                keep.ra_deg = t.ra_deg
                keep.dec_deg = t.dec_deg
            merged.append(t.id)
            session.flush()
            session.execute(text("DELETE FROM targets WHERE id = :tid"), {"tid": t.id})

        session.flush()
        session.execute(
            text(
                """
            UPDATE sessions SET
                frame_count = (SELECT COUNT(*) FROM frames WHERE frames.session_id = sessions.id),
                total_exposure_s = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0),
                total_exposure_h = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0) / 3600.0
            WHERE sessions.target_id = :keep_id
            """
            ),
            {"keep_id": keep.id},
        )
        session.commit()

        return {
            "status": "ok",
            "target_id": keep.id,
            "name": keep.name,
            "merged_ids": merged,
            "merged_count": len(merged),
        }


@app.post("/api/v1/db/reset")
def reset_database(req: DbResetRequest):
    """Delete all data and recreate tables."""
    if not req.confirm:
        raise HTTPException(400, "confirm must be true")

    engine, SessionLocal = get_session_local()
    with SessionLocal() as sess:
        # Drop FTS5 triggers first so DELETE doesn't fire them
        sess.execute(text("DROP TRIGGER IF EXISTS frames_fts_ai"))
        sess.execute(text("DROP TRIGGER IF EXISTS frames_fts_ad"))
        sess.execute(text("DROP TRIGGER IF EXISTS frames_fts_au"))
        sess.execute(text("DROP TABLE IF EXISTS frames_fts"))

        # Delete all data (FK-safe order)
        sess.execute(text("DELETE FROM calibration_files"))
        sess.execute(text("DELETE FROM frames"))
        sess.execute(text("DELETE FROM sessions"))
        sess.execute(text("DELETE FROM targets"))
        sess.execute(text("DELETE FROM cameras"))
        sess.execute(text("DELETE FROM telescopes"))
        sess.execute(text("DELETE FROM filters"))
        sess.execute(text("DELETE FROM settings"))

        # Recreate FTS5 virtual table
        sess.execute(
            text(
                """
            CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                object_name, instrume, telescop, filter_name, filename, site_name,
                content=frames, content_rowid=id
            )
            """
            )
        )
        sess.commit()

    with SessionLocal() as sess:
        sess.execute(
            text(
                """
            CREATE TRIGGER IF NOT EXISTS frames_fts_ai AFTER INSERT ON frames
            BEGIN
                INSERT INTO frames_fts(rowid, object_name, instrume, telescop, filter_name, filename, site_name)
                VALUES (new.id, new.object_name, new.instrume, new.telescop, new.filter_name, new.filename, new.site_name);
            END
            """
            )
        )
        sess.execute(
            text(
                """
            CREATE TRIGGER IF NOT EXISTS frames_fts_ad AFTER DELETE ON frames
            BEGIN
                INSERT INTO frames_fts(frames_fts, rowid, object_name, instrume, telescop, filter_name, filename, site_name)
                VALUES ('delete', old.id, old.object_name, old.instrume, old.telescop, old.filter_name, old.filename, old.site_name);
            END
            """
            )
        )
        sess.execute(
            text(
                """
            CREATE TRIGGER IF NOT EXISTS frames_fts_au AFTER UPDATE ON frames
            BEGIN
                INSERT INTO frames_fts(frames_fts, rowid, object_name, instrume, telescop, filter_name, filename, site_name)
                VALUES ('delete', old.id, old.object_name, old.instrume, old.telescop, old.filter_name, old.filename, old.site_name);
                INSERT INTO frames_fts(rowid, object_name, instrume, telescop, filter_name, filename, site_name)
                VALUES (new.id, new.object_name, new.instrume, new.telescop, new.filter_name, new.filename, new.site_name);
            END
            """
            )
        )
        sess.commit()

    return {"status": "ok", "message": "Database reset complete"}


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@app.get("/api/v1/targets/{target_id}", response_model=TargetSchema)
def get_target(target_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.get(Target, target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        session_count = (
            session.query(sa_func.count(ObsSession.id))
            .filter(ObsSession.target_id == target_id)
            .scalar()
        )
        total_h = (
            session.query(sa_func.sum(ObsSession.total_exposure_h))
            .filter(ObsSession.target_id == target_id)
            .scalar()
            or 0
        )
        return TargetSchema(
            id=target.id,
            name=target.name,
            object_type=target.object_type,
            constellation=target.constellation,
            ra_deg=target.ra_deg,
            dec_deg=target.dec_deg,
            session_count=session_count,
            total_exposure_h=round(total_h, 1),
        )


@app.get("/api/v1/targets/{target_id}/sessions", response_model=SessionListResponse)
def get_target_sessions(
    target_id: int,
    camera_id: int | None = Query(None),
    sort_by: str = Query("date_obs"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.get(Target, target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        q = (
            session.query(
                ObsSession.id,
                ObsSession.target_id,
                ObsSession.date_obs,
                ObsSession.group_key,
                ObsSession.status,
                ObsSession.total_exposure_s,
                ObsSession.total_exposure_h,
                ObsSession.frame_count,
                ObsSession.path.label("folder_path"),
                Camera.name.label("camera_name"),
                Telescope.name.label("telescope_name"),
            )
            .outerjoin(Camera, Camera.id == ObsSession.camera_id)
            .outerjoin(Telescope, Telescope.id == ObsSession.telescope_id)
            .filter(ObsSession.target_id == target_id)
        )
        if camera_id is not None:
            q = q.filter(ObsSession.camera_id == camera_id)

        total = q.count()
        pages = (total + page_size - 1) // page_size

        allowed_sort = {"date_obs": ObsSession.date_obs, "total_exposure_h": ObsSession.total_exposure_h, "frame_count": ObsSession.frame_count}
        order_col = allowed_sort.get(sort_by, ObsSession.date_obs)
        order_col = order_col.desc() if sort_order == "desc" else order_col.asc()

        items = [
            SessionSchema(
                id=r.id,
                target_id=r.target_id,
                target_name=target.name,
                camera_name=r.camera_name,
                telescope_name=r.telescope_name,
                date_obs=r.date_obs,
                group_key=r.group_key,
                status=r.status,
                total_exposure_s=r.total_exposure_s,
                total_exposure_h=round(r.total_exposure_h, 2),
                frame_count=r.frame_count,
                folder_path=r.folder_path,
            )
            for r in q.order_by(order_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        ]

        return SessionListResponse(
            total=total, page=page, page_size=page_size, pages=pages, items=items
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@app.get("/api/v1/sessions", response_model=SessionListResponse)
def list_sessions(
    target_id: int | None = Query(None),
    camera_id: int | None = Query(None),
    telescope_id: int | None = Query(None),
    filter_name: str | None = Query(None, description="Filter by filter name used in sessions"),
    status: str | None = Query(None),
    date_from: str | None = Query(None, description="Start date YYYY-MM-DD"),
    date_to: str | None = Query(None, description="End date YYYY-MM-DD"),
    sort_by: str = Query("date_obs"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = (
            session.query(
                ObsSession.id,
                ObsSession.target_id,
                ObsSession.date_obs,
                ObsSession.group_key,
                ObsSession.status,
                ObsSession.total_exposure_s,
                ObsSession.total_exposure_h,
                ObsSession.frame_count,
                ObsSession.path.label("folder_path"),
                Target.name.label("target_name"),
                Camera.name.label("camera_name"),
                Telescope.name.label("telescope_name"),
            )
            .join(Target, Target.id == ObsSession.target_id)
            .outerjoin(Camera, Camera.id == ObsSession.camera_id)
            .outerjoin(Telescope, Telescope.id == ObsSession.telescope_id)
        )
        if target_id is not None:
            q = q.filter(ObsSession.target_id == target_id)
        if camera_id is not None:
            q = q.filter(ObsSession.camera_id == camera_id)
        if telescope_id is not None:
            q = q.filter(ObsSession.telescope_id == telescope_id)
        if filter_name is not None:
            q = q.filter(
                ObsSession.id.in_(
                    session.query(Frame.session_id).filter(
                        Frame.session_id.isnot(None),
                        Frame.filter_name == filter_name
                    )
                )
            )
        if status is not None:
            q = q.filter(ObsSession.status == status)
        if date_from:
            try:
                q = q.filter(ObsSession.date_obs >= datetime.fromisoformat(date_from))
            except ValueError as err:
                raise HTTPException(
                    status_code=400, detail=f"Invalid date_from: {date_from}"
                ) from err
        if date_to:
            try:
                q = q.filter(ObsSession.date_obs <= datetime.fromisoformat(date_to))
            except ValueError as err:
                raise HTTPException(status_code=400, detail=f"Invalid date_to: {date_to}") from err

        total = q.count()
        pages = (total + page_size - 1) // page_size

        _allowed_session_sort = {"date_obs": ObsSession.date_obs, "total_exposure_h": ObsSession.total_exposure_h, "total_exposure_s": ObsSession.total_exposure_s, "frame_count": ObsSession.frame_count, "target_id": ObsSession.target_id, "camera_id": ObsSession.camera_id, "status": ObsSession.status, "group_key": ObsSession.group_key}
        order_col = _allowed_session_sort.get(sort_by, ObsSession.date_obs)
        order_col = order_col.desc() if sort_order == "desc" else order_col.asc()

        items = [
            SessionSchema(
                id=r.id,
                target_id=r.target_id,
                target_name=r.target_name,
                camera_name=r.camera_name,
                telescope_name=r.telescope_name,
                date_obs=r.date_obs,
                group_key=r.group_key,
                status=r.status,
                total_exposure_s=r.total_exposure_s,
                total_exposure_h=round(r.total_exposure_h, 2),
                frame_count=r.frame_count,
                folder_path=r.folder_path,
            )
            for r in q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return SessionListResponse(
            total=total, page=page, page_size=page_size, pages=pages, items=items
        )


@app.get("/api/v1/sessions/{session_id}", response_model=SessionSchema)
def get_session(session_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = (
            session.query(
                ObsSession.id,
                ObsSession.target_id,
                ObsSession.date_obs,
                ObsSession.group_key,
                ObsSession.status,
                ObsSession.total_exposure_s,
                ObsSession.total_exposure_h,
                ObsSession.frame_count,
                ObsSession.path.label("folder_path"),
                Target.name.label("target_name"),
                Camera.name.label("camera_name"),
                Telescope.name.label("telescope_name"),
            )
            .join(Target, Target.id == ObsSession.target_id)
            .outerjoin(Camera, Camera.id == ObsSession.camera_id)
            .outerjoin(Telescope, Telescope.id == ObsSession.telescope_id)
            .filter(ObsSession.id == session_id)
            .first()
        )
        if not obs:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionSchema(
            id=obs.id,
            target_id=obs.target_id,
            target_name=obs.target_name,
            camera_name=obs.camera_name,
            telescope_name=obs.telescope_name,
            date_obs=obs.date_obs,
            group_key=obs.group_key,
            status=obs.status,
            total_exposure_s=obs.total_exposure_s,
            total_exposure_h=round(obs.total_exposure_h, 2),
            frame_count=obs.frame_count,
            folder_path=obs.folder_path,
        )


class SessionStatusUpdate(BaseModel):
    status: str


@app.patch("/api/v1/sessions/{session_id}")
def update_session(session_id: int, req: SessionStatusUpdate):
    """Update session metadata (e.g. status)."""
    allowed_statuses = {"raw", "calibrated", "stacked"}
    if req.status not in allowed_statuses:
        raise HTTPException(400, f"Invalid status. Allowed: {', '.join(sorted(allowed_statuses))}")

    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = session.get(ObsSession, session_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Session not found")
        obs.status = req.status
        session.commit()
        return {"status": "ok", "session_id": session_id, "new_status": req.status}


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------


@app.get("/api/v1/sessions/{session_id}/stats")
def get_session_stats(session_id: int):
    """Get aggregated stats for a session: exposure per filter, frames per type."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = session.get(ObsSession, session_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Session not found")

        # Frames per type
        type_stats = (
            session.query(Frame.frame_type, sa_func.count(Frame.id))
            .filter(Frame.session_id == session_id)
            .group_by(Frame.frame_type)
            .all()
        )

        # Exposure per filter
        filter_stats = (
            session.query(
                Frame.filter_name,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.sum(Frame.exposure).label("total_s"),
            )
            .filter(Frame.session_id == session_id)
            .group_by(Frame.filter_name)
            .order_by(sa_func.sum(Frame.exposure).desc())
            .all()
        )

        return {
            "frame_type_counts": {row[0] or "UNKNOWN": row[1] for row in type_stats},
            "exposure_per_filter": [
                {
                    "filter": r.filter_name or "UNKNOWN",
                    "frames": r.frame_count,
                    "total_s": r.total_s,
                }
                for r in filter_stats
            ],
        }


@app.get("/api/v1/frames", response_model=FrameListResponse)
def list_frames(
    session_id: int | None = Query(None),
    object_name: str | None = Query(None),
    filter_name: str | None = Query(None),
    frame_type: str | None = Query(None),
    camera: str | None = Query(None),
    has_coordinates: bool | None = Query(
        None, description="Filter by presence of RA/Dec coordinates"
    ),
    filename: str | None = Query(None, description="Search in filename (use * for wildcard)"),
    filepath: str | None = Query(None, description="Search in filepath (use * for wildcard)"),
    sort_by: str = Query("date_obs"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=10000),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = session.query(Frame)
        if session_id is not None:
            q = q.filter(Frame.session_id == session_id)
        if object_name:
            q = q.filter(Frame.object_name.ilike(f"%{object_name}%"))
        if filter_name:
            q = q.filter(Frame.filter_name == filter_name)
        if frame_type:
            q = q.filter(Frame.frame_type == frame_type)
        if camera:
            q = q.filter(Frame.instrume.ilike(f"%{camera}%"))
        if has_coordinates is True:
            q = q.filter(Frame.ra_deg.isnot(None), Frame.dec_deg.isnot(None))
        elif has_coordinates is False:
            q = q.filter(Frame.ra_deg.is_(None), Frame.dec_deg.is_(None))

        if filename:
            raw = filename.replace("\\", "\\\\")
            like_pattern = raw.replace("_", "\\_").replace("%", "\\%").replace("*", "%").replace("?", "_")
            if "%" not in like_pattern:
                like_pattern = f"%{like_pattern}%"
            q = q.filter(Frame.filename.ilike(like_pattern, escape="\\"))
        if filepath:
            raw = filepath.replace("\\", "\\\\")
            like_pattern = raw.replace("_", "\\_").replace("%", "\\%").replace("*", "%").replace("?", "_")
            if "%" not in like_pattern:
                like_pattern = f"%{like_pattern}%"
            q = q.filter(Frame.filepath.ilike(like_pattern, escape="\\"))

        total = q.count()
        pages = (total + page_size - 1) // page_size

        _allowed_frame_sort = {"date_obs": Frame.date_obs, "filename": Frame.filename, "frame_type": Frame.frame_type, "filter_name": Frame.filter_name, "exposure": Frame.exposure, "gain": Frame.gain, "ccd_temp": Frame.ccd_temp, "binning": Frame.binning, "object_name": Frame.object_name, "filepath": Frame.filepath, "session_id": Frame.session_id, "date_local": Frame.date_local, "file_size": Frame.file_size}
        order_col = _allowed_frame_sort.get(sort_by, Frame.date_obs)
        order_col = order_col.desc() if sort_order == "desc" else order_col.asc()

        items = [
            FrameSchema.model_validate(f)
            for f in q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return FrameListResponse(
            total=total, page=page, page_size=page_size, pages=pages, items=items
        )


@app.get("/api/v1/frames/{frame_id}", response_model=FrameDetailSchema)
def get_frame(frame_id: int):
    """Get full metadata for a single frame."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        frame = session.get(Frame, frame_id)
        if not frame:
            raise HTTPException(404, "Frame not found")
        return FrameDetailSchema.model_validate(frame)


@app.get("/api/v1/frames/{frame_id}/thumbnail")
def get_frame_thumbnail(frame_id: int, preview: bool = Query(False)):
    """Get a JPEG thumbnail for a specific frame.
    
    Normal (preview=false): max 200px, quick thumbnail.
    Preview (preview=true): ~25% of original resolution for the popup viewer.
    """
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        frame = session.get(Frame, frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail="Frame not found")

        fp = Path(frame.filepath)
        if not fp.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        size = 200
        if preview:
            raw_w = frame.width or 4000
            size = max(400, min(raw_w // 4, 2000))

        thumb_bytes = generate_thumbnail(fp, size=size)
        if thumb_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

        return Response(content=thumb_bytes, media_type="image/jpeg")


@app.get("/api/v1/targets/{target_id}/thumbnails")
def get_target_thumbnails(target_id: int, limit: int = Query(6, ge=1, le=20)):
    """Get thumbnails for recent frames of a target."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.get(Target, target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        recent_frames = (
            session.query(Frame)
            .filter(Frame.object_name.ilike(f"%{target.name}%"), Frame.frame_type == "LIGHT")
            .order_by(Frame.date_obs.desc())
            .limit(limit)
            .all()
        )

        import base64

        results = []
        for f in recent_frames:
            fp = Path(f.filepath)
            thumb_url = None
            if fp.exists():
                thumb_bytes = generate_thumbnail(fp)
                if thumb_bytes:
                    thumb_url = f"data:image/jpeg;base64,{base64.b64encode(thumb_bytes).decode()}"

            results.append(
                {
                    "id": f.id,
                    "filename": f.filename,
                    "filter_name": f.filter_name,
                    "exposure": f.exposure,
                    "date_obs": str(f.date_obs) if f.date_obs else None,
                    "thumbnail": thumb_url,
                }
            )

        return results


class FrameDeleteRequest(BaseModel):
    frame_ids: list[int]


@app.post("/api/v1/frames/delete")
def delete_frames(req: FrameDeleteRequest):
    """Delete frames by list of IDs. Also recalculates affected session stats."""
    if not req.frame_ids:
        raise HTTPException(400, "No frame IDs provided")

    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        affected_session_ids = set()
        frames = session.query(Frame).filter(Frame.id.in_(req.frame_ids)).all()
        if not frames:
            raise HTTPException(404, "No frames found")

        for f in frames:
            if f.session_id:
                affected_session_ids.add(f.session_id)

        session.query(Frame).filter(Frame.id.in_(req.frame_ids)).delete(
            synchronize_session="fetch"
        )

        if affected_session_ids:
            from sqlalchemy import update as sa_update

            for sid in affected_session_ids:
                frame_stats = (
                    session.query(
                        sa_func.count(Frame.id),
                        sa_func.coalesce(sa_func.sum(Frame.exposure), 0),
                    )
                    .filter(Frame.session_id == sid)
                    .first()
                )
                cnt, total_s = frame_stats
                total_h = (total_s or 0) / 3600.0
                session.execute(
                    sa_update(ObsSession)
                    .where(ObsSession.id == sid)
                    .values(frame_count=cnt, total_exposure_s=total_s, total_exposure_h=total_h)
                )

        session.commit()

        _cleanup_orphans(session)

    return {"status": "ok", "deleted": len(req.frame_ids), "affected_sessions": len(affected_session_ids)}


def _cleanup_orphans(session):
    """Delete orphaned sessions (no frames), targets (no sessions), and unused equipment."""
    # Orphaned sessions
    orphan_sessions = session.query(ObsSession).filter(
        ~ObsSession.id.in_(session.query(Frame.session_id).filter(Frame.session_id.isnot(None)))
    ).all()
    orphan_session_ids = [s.id for s in orphan_sessions]
    for s in orphan_sessions:
        session.delete(s)

    # Orphaned targets
    orphan_targets = session.query(Target).filter(
        ~Target.id.in_(session.query(ObsSession.target_id).filter(ObsSession.target_id.isnot(None)))
    ).all()
    for t in orphan_targets:
        session.delete(t)

    # Orphaned cameras
    orphan_cameras = session.query(Camera).filter(
        ~Camera.id.in_(session.query(ObsSession.camera_id).filter(ObsSession.camera_id.isnot(None)))
    ).all()
    for c in orphan_cameras:
        session.delete(c)

    # Orphaned telescopes
    orphan_telescopes = session.query(Telescope).filter(
        ~Telescope.id.in_(session.query(ObsSession.telescope_id).filter(ObsSession.telescope_id.isnot(None)))
    ).all()
    for t in orphan_telescopes:
        session.delete(t)

    session.flush()
    return {
        "sessions": len(orphan_session_ids),
        "targets": len(orphan_targets),
        "cameras": len(orphan_cameras),
        "telescopes": len(orphan_telescopes),
    }


@app.post("/api/v1/db/cleanup-orphans")
def cleanup_orphans():
    """Remove orphaned sessions, targets, and equipment without frames."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        result = _cleanup_orphans(session)
        session.commit()
    return {"status": "ok", **result}


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------


@app.get("/api/v1/cameras", response_model=list[CameraSchema])
def list_cameras():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        results = (
            session.query(
                Camera.id,
                Camera.name,
                Camera.short_name,
                Camera.pixel_size_um,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.coalesce(sa_func.sum(Frame.exposure), 0).label("total_s"),
            )
            .outerjoin(ObsSession, ObsSession.camera_id == Camera.id)
            .outerjoin(Frame, Frame.session_id == ObsSession.id)
            .group_by(Camera.id, Camera.name, Camera.short_name, Camera.pixel_size_um)
            .order_by(sa_func.count(Frame.id).desc())
            .all()
        )
        return [
            CameraSchema(
                id=r.id,
                name=r.name,
                short_name=r.short_name,
                pixel_size_um=r.pixel_size_um,
                frame_count=r.frame_count,
                total_exposure_h=round(r.total_s / 3600, 1),
            )
            for r in results
        ]


@app.get("/api/v1/telescopes", response_model=list[TelescopeSchema])
def list_telescopes():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        results = (
            session.query(
                Telescope.id,
                Telescope.name,
                Telescope.short_name,
                Telescope.focal_length_mm,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.coalesce(sa_func.sum(Frame.exposure), 0).label("total_s"),
            )
            .outerjoin(ObsSession, ObsSession.telescope_id == Telescope.id)
            .outerjoin(Frame, Frame.session_id == ObsSession.id)
            .group_by(Telescope.id, Telescope.name, Telescope.short_name, Telescope.focal_length_mm)
            .order_by(sa_func.count(Frame.id).desc())
            .all()
        )
        return [
            TelescopeSchema(
                id=r.id,
                name=r.name,
                short_name=r.short_name,
                focal_length_mm=r.focal_length_mm,
                frame_count=r.frame_count,
                total_exposure_h=round(r.total_s / 3600, 1),
            )
            for r in results
        ]


@app.get("/api/v1/filters")
def list_filters():
    """List all unique filter names with usage statistics."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        results = (
            session.query(
                Frame.filter_name,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.coalesce(sa_func.sum(Frame.exposure), 0).label("total_s"),
            )
            .filter(Frame.filter_name.isnot(None), Frame.filter_name != "")
            .group_by(Frame.filter_name)
            .order_by(sa_func.count(Frame.id).desc())
            .all()
        )
        return [
            {
                "name": r.filter_name,
                "frame_count": r.frame_count,
                "total_exposure_h": round((r.total_s or 0) / 3600, 1),
            }
            for r in results
        ]


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


@app.get("/api/v1/stats")
def get_stats():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as sess:
        total_exposure_h = sess.query(sa_func.sum(ObsSession.total_exposure_h)).scalar() or 0
        return {
            "targets": sess.query(Target).count(),
            "sessions": sess.query(ObsSession).count(),
            "frames": sess.query(Frame).count(),
            "cameras": sess.query(Camera).count(),
            "telescopes": sess.query(Telescope).count(),
            "calibration_files": sess.query(CalibrationFile).count(),
            "total_exposure_h": round(total_exposure_h, 1),
        }


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingSchema(BaseModel):
    key: str
    value: str | None
    description: str | None


@app.get("/api/v1/settings", response_model=list[SettingSchema])
def list_settings():
    """Get all application settings."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as sess:
        results = sess.query(Setting).all()
        return [{"key": r.key, "value": r.value, "description": r.description} for r in results]


@app.post("/api/v1/settings")
def update_settings(settings: list[SettingSchema]):
    """Update application settings (upsert by key)."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as sess:
        for s in settings:
            existing = sess.query(Setting).filter(Setting.key == s.key).first()
            if existing:
                existing.value = s.value
            else:
                setting = Setting(key=s.key, value=s.value, description=s.description)
                sess.add(setting)
        sess.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Platesolving
# ---------------------------------------------------------------------------


@app.post("/api/v1/platesolve")
def run_platesolve():
    """Start ASTAP platesolving on all frames without RA/Dec coordinates (background task)."""
    with _platesolve_lock:
        if _platesolve_state["running"]:
            raise HTTPException(status_code=409, detail="A platesolve operation is already running")
        _platesolve_state["running"] = True
        _platesolve_state["phase"] = "solving"
        _platesolve_state["solved"] = 0
        _platesolve_state["failed"] = 0
        _platesolve_state["error"] = None
        _platesolve_state["cancelled"] = False
        _platesolve_state["log"] = []

    thread = threading.Thread(target=_run_platesolve_task, daemon=True)
    thread.start()

    return {"status": "started"}


@app.get("/api/v1/platesolve/status")
def platesolve_status():
    """Get current platesolve progress."""
    with _platesolve_lock:
        return dict(_platesolve_state)


@app.post("/api/v1/platesolve/cancel")
def cancel_platesolve():
    """Cancel a running platesolve operation."""
    with _platesolve_lock:
        _platesolve_state["cancelled"] = True
    return {"status": "cancelling"}


def _run_platesolve_task():
    """Background thread task for platesolving."""
    global _platesolve_state
    try:
        engine, SessionLocal = get_session_local()

        astap_binary = "astap_cli"
        with SessionLocal() as sess:
            setting = sess.query(Setting).filter(Setting.key == "astap_binary").first()
            if setting and setting.value:
                astap_binary = setting.value

            unplated = (
                sess.query(Frame)
                .filter(Frame.ra_deg.is_(None), Frame.dec_deg.is_(None))
                .limit(50)
                .all()
            )

            total = len(unplated)
            solved = 0
            failed = 0
            log_entries = []

            with _platesolve_lock:
                _platesolve_state["total"] = total
                _platesolve_state["log"] = []

            for _i, frame in enumerate(unplated):
                # Check for cancellation
                with _platesolve_lock:
                    if _platesolve_state.get("cancelled"):
                        log_entries.append(
                            {"frame": frame.filename, "status": "cancelled", "detail": "Cancelled"}
                        )
                        break

                fp = Path(frame.filepath)
                if not fp.exists():
                    failed += 1
                    log_entries.append(
                        {"frame": frame.filename, "status": "failed", "detail": "File not found"}
                    )
                    with _platesolve_lock:
                        _platesolve_state["failed"] = failed
                        _platesolve_state["log"] = list(log_entries)
                    continue

                ra_hint = frame.ra_deg or None
                dec_hint = frame.dec_deg or None
                if ra_hint is None and dec_hint is None and frame.object_name:
                    from stellashelf.catalog import normalize_object_name

                    norm = normalize_object_name(frame.object_name)
                    target = sess.query(Target).filter(Target.name == norm).first()
                    if target and target.ra_deg is not None:
                        ra_hint = target.ra_deg
                        dec_hint = target.dec_deg

                result = platesolve_frame(fp, astap_binary, ra_hint=ra_hint, dec_hint=dec_hint)
                if result:
                    frame.ra_deg = result["ra_deg"]
                    frame.dec_deg = result["dec_deg"]
                    solved += 1
                    log_entries.append(
                        {
                            "frame": frame.filename,
                            "status": "solved",
                            "detail": f"RA={result['ra_deg']:.4f}° Dec={result['dec_deg']:.4f}°",
                        }
                    )
                else:
                    failed += 1
                    log_entries.append(
                        {"frame": frame.filename, "status": "failed", "detail": "No solution found"}
                    )

                with _platesolve_lock:
                    _platesolve_state["solved"] = solved
                    _platesolve_state["failed"] = failed
                    _platesolve_state["log"] = list(log_entries)

            sess.commit()

        with _platesolve_lock:
            _platesolve_state["phase"] = "done" if not _platesolve_state.get("cancelled") else "cancelled"
            _platesolve_state["solved"] = solved
            _platesolve_state["failed"] = failed
            _platesolve_state["log"] = log_entries
            _platesolve_state["running"] = False

    except Exception as e:

        with _platesolve_lock:
            _platesolve_state["running"] = False
            _platesolve_state["phase"] = "error"
            _platesolve_state["error"] = str(e)
            _platesolve_state["log"] = (
                _platesolve_state.get("log", [])
                + [{"frame": "", "status": "error", "detail": str(e)}]
            )


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------

# Vue 3 SPA build output
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-vue" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    if (FRONTEND_DIR / "public").exists():
        app.mount("/icons", StaticFiles(directory=str(FRONTEND_DIR / "public")), name="public")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def index(path: str = ""):
        # Serve index.html for all non-API, non-asset paths (SPA routing)
        if path.startswith("api/") or path.startswith("assets/") or path.startswith("icons/"):
            raise HTTPException(status_code=404)
        return (FRONTEND_DIR / "index.html").read_text()
