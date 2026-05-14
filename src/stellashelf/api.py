"""StellaShelf FastAPI application.

REST API for browsing astrophotography sessions, frames, and equipment.
Supports pagination, filtering, and full-text search.
"""

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

from stellashelf.config import DEFAULT_DB_PATH
from stellashelf.db import CalibrationFile, Camera, Frame, Setting, Target, Telescope, init_db
from stellashelf.db import Session as ObsSession
from stellashelf.importer import ImporterService

# Module-level db path, can be overridden via create_app() or set_db_path()
_db_path: Path = DEFAULT_DB_PATH


def set_db_path(path: Path) -> None:
    """Override the database path used by the API."""
    global _db_path
    _db_path = path


def get_session_local():
    """Initialize and return engine, SessionLocal."""
    if not _db_path.exists():
        raise RuntimeError(f"Database not found at {_db_path}. Run 'stellashelf scan' first.")
    return init_db(_db_path)


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_path: Path to the SQLite database. Defaults to ~/.stellashelf/stellashelf.db.
    """
    if db_path is not None:
        set_db_path(db_path)

    # Allow CORS for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = FastAPI(title="StellaShelf", version="0.2.0")


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
    frame_type: str
    object_name: str
    filter_name: str
    exposure: float | None
    gain: int | None
    ccd_temp: float | None
    binning: int
    date_obs: datetime | None


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
        fts_results = (
            session.query(
                Frame.id, Frame.object_name, Frame.filename, Frame.frame_type, Frame.date_obs
            )
            .filter(
                text("frames_fts MATCH :q"),
            )
            .params(q=q)
            .limit(limit)
            .all()
        )

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


@app.get("/api/v1/targets/{target_id}", response_model=TargetSchema)
def get_target(target_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
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
        if camera_id:
            q = q.filter(ObsSession.camera_id == camera_id)

        total = q.count()
        pages = (total + page_size - 1) // page_size

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
            for r in q.order_by(ObsSession.date_obs.desc())
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
        if status is not None:
            q = q.filter(ObsSession.status == status)
        if date_from:
            q = q.filter(ObsSession.date_obs >= datetime.fromisoformat(date_from))
        if date_to:
            q = q.filter(ObsSession.date_obs <= datetime.fromisoformat(date_to))

        total = q.count()
        pages = (total + page_size - 1) // page_size

        order_col = getattr(ObsSession, sort_by, ObsSession.date_obs)
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


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------


@app.get("/api/v1/sessions/{session_id}/stats")
def get_session_stats(session_id: int):
    """Get aggregated stats for a session: exposure per filter, frames per type."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = session.query(ObsSession).get(session_id)
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
    sort_by: str = Query("date_obs"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
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

        total = q.count()
        pages = (total + page_size - 1) // page_size

        order_col = getattr(Frame, sort_by, Frame.date_obs)
        order_col = order_col.desc() if sort_order == "desc" else order_col.asc()

        items = [
            FrameSchema.model_validate(f)
            for f in q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return FrameListResponse(
            total=total, page=page, page_size=page_size, pages=pages, items=items
        )


@app.get("/api/v1/frames/{frame_id}/thumbnail")
def get_frame_thumbnail(frame_id: int):
    """Get a JPEG thumbnail for a specific frame."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        frame = session.query(Frame).get(frame_id)
        if not frame:
            raise HTTPException(status_code=404, detail="Frame not found")

        fp = Path(frame.filepath)
        if not fp.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        from stellashelf.scanner import generate_thumbnail

        thumb_bytes = generate_thumbnail(fp)
        if thumb_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

        return Response(content=thumb_bytes, media_type="image/jpeg")


@app.get("/api/v1/targets/{target_id}/thumbnails")
def get_target_thumbnails(target_id: int, limit: int = Query(6, ge=1, le=20)):
    """Get thumbnails for recent frames of a target."""
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")

        recent_frames = (
            session.query(Frame)
            .filter(Frame.object_name.ilike(f"%{target.name}%"), Frame.frame_type == "LIGHT")
            .order_by(Frame.date_obs.desc())
            .limit(limit)
            .all()
        )

        results = []
        for f in recent_frames:
            fp = Path(f.filepath)
            thumb_url = None
            if fp.exists():
                from stellashelf.scanner import generate_thumbnail

                thumb_bytes = generate_thumbnail(fp)
                if thumb_bytes:
                    import base64

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
                folder_path=r.folder_path,
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
                folder_path=r.folder_path,
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
    """Run ASTAP platesolving on all frames without RA/Dec coordinates."""
    from stellashelf.db import Setting
    from stellashelf.scanner import platesolve_frame

    engine, SessionLocal = get_session_local()

    # Get ASTAP binary path from settings
    astap_binary = "astap"
    with SessionLocal() as sess:
        setting = sess.query(Setting).filter(Setting.key == "astap_binary").first()
        if setting and setting.value:
            astap_binary = setting.value

    solved = 0
    failed = 0

    with SessionLocal() as sess:
        unplated = (
            sess.query(Frame)
            .filter(Frame.ra_deg.is_(None), Frame.dec_deg.is_(None))
            .limit(50)
            .all()
        )

        for frame in unplated:
            fp = Path(frame.filepath)
            if not fp.exists():
                continue
            result = platesolve_frame(fp, astap_binary)
            if result:
                frame.ra_deg = result["ra_deg"]
                frame.dec_deg = result["dec_deg"]
                solved += 1
            else:
                failed += 1

        sess.commit()

    return {
        "status": "ok",
        "solved": solved,
        "failed": failed,
        "remaining": len(unplated) - solved - failed,
    }


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------

# Vue 3 SPA build output
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend-vue" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/{path:path}", response_class=HTMLResponse)
    async def index(path: str = ""):
        # Serve index.html for all non-API, non-asset paths (SPA routing)
        if path.startswith("api/") or path.startswith("assets/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        return (FRONTEND_DIR / "index.html").read_text()
