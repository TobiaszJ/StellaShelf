"""StellaShelf FastAPI application.

REST API for browsing astrophotography sessions, frames, and equipment.
Supports pagination, filtering, and full-text search.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func as sa_func

from stellashelf.db import init_db, Target, Session as ObsSession, Frame, Camera, Telescope, CalibrationFile
from stellashelf.importer import ImporterService

DB_PATH = Path("~/stellashelf/stellashelf.db").expanduser().resolve()


def get_session_local():
    """Initialize and return engine, SessionLocal."""
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found at {DB_PATH}. Run 'stellashelf scan' first.")
    return init_db(DB_PATH)


app = FastAPI(title="StellaShelf", version="0.2.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        importer = ImporterService(DB_PATH)
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
    object_type: Optional[str] = None
    constellation: Optional[str] = None
    ra_deg: Optional[float] = None
    dec_deg: Optional[float] = None
    session_count: int = 0
    total_exposure_h: float = 0


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    target_name: str = ""
    camera_name: Optional[str] = None
    telescope_name: Optional[str] = None
    date_obs: Optional[datetime] = None
    group_key: str
    status: str
    total_exposure_s: float
    total_exposure_h: float
    frame_count: int


class FrameSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    session_id: Optional[int]
    filename: str
    filepath: str
    frame_type: str
    object_name: str
    filter_name: str
    exposure: Optional[float]
    gain: Optional[int]
    ccd_temp: Optional[float]
    binning: int
    date_obs: Optional[datetime]


class CameraSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_name: Optional[str]
    pixel_size_um: Optional[float]
    frame_count: int = 0
    total_exposure_h: float = 0


class TelescopeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_name: Optional[str]
    focal_length_mm: Optional[float]
    frame_count: int = 0
    total_exposure_h: float = 0


class CalibrationFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_id: Optional[int]
    cal_type: str
    exposure_s: Optional[float]
    gain: Optional[int]
    binning: int
    ccd_temp: Optional[float]
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
    return {"status": "ok", "db": str(DB_PATH)}


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

    thread = threading.Thread(target=_run_scan_task, args=(resolved, request.recursive), daemon=True)
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
                Target.id, Target.name,
                sa_func.sum(ObsSession.total_exposure_h).label("total_h"),
                sa_func.count(ObsSession.id).label("session_count")
            )
            .join(ObsSession, ObsSession.target_id == Target.id)
            .group_by(Target.id, Target.name)
            .order_by(sa_func.sum(ObsSession.total_exposure_h).desc())
            .limit(10)
            .all()
        )

        # Recent 10 sessions
        recent = (
            session.query(ObsSession)
            .filter(ObsSession.date_obs != None)
            .order_by(ObsSession.date_obs.desc())
            .limit(10)
            .all()
        )

        # Camera usage stats
        camera_stats = (
            session.query(
                Camera.id, Camera.name, Camera.short_name, Camera.pixel_size_um,
                sa_func.count(Frame.id).label("frame_count"),
                sa_func.coalesce(sa_func.sum(Frame.exposure), 0).label("total_s")
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
                {"id": t.id, "name": t.name, "total_exposure_h": round(t.total_h, 1), "session_count": t.session_count}
                for t in top_targets
            ],
            "recent_sessions": [
                {"id": s.id, "target_id": s.target_id, "date_obs": s.date_obs, "total_exposure_h": round(s.total_exposure_h, 1), "frame_count": s.frame_count}
                for s in recent
            ],
            "cameras": [
                {"id": c.id, "name": c.name, "short_name": c.short_name, "frame_count": c.frame_count, "total_exposure_h": round(c.total_s / 3600, 1)}
                for c in camera_stats
            ],
        }


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

@app.get("/api/v1/targets", response_model=TargetListResponse)
def list_targets(
    search: Optional[str] = Query(None, description="Search targets by name"),
    sort_by: str = Query("name"),
    sort_order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = session.query(
            Target.id, Target.name, Target.object_type, Target.constellation,
            Target.ra_deg, Target.dec_deg,
            sa_func.count(ObsSession.id).label("session_count"),
            sa_func.coalesce(sa_func.sum(ObsSession.total_exposure_h), 0).label("total_h"),
        ).outerjoin(ObsSession, ObsSession.target_id == Target.id)

        if search:
            q = q.filter(Target.name.ilike(f"%{search}%"))

        # Group by target
        q = q.group_by(Target.id, Target.name, Target.object_type, Target.constellation, Target.ra_deg, Target.dec_deg)

        total = q.count()
        pages = (total + page_size - 1) // page_size

        if sort_by in ("name", "object_type", "constellation", "total_h", "session_count"):
            col = getattr(Target, sort_by, Target.name) if sort_by not in ("total_h", "session_count") else sa_func.coalesce(sa_func.sum(ObsSession.total_exposure_h), 0) if sort_by == "total_h" else sa_func.count(ObsSession.id)
            order_col = col.desc() if sort_order == "desc" else col.asc()
        else:
            order_col = Target.name.asc()

        q = q.order_by(order_col).offset((page - 1) * page_size).limit(page_size)

        items = [
            TargetSchema(
                id=r.id, name=r.name, object_type=r.object_type, constellation=r.constellation,
                ra_deg=r.ra_deg, dec_deg=r.dec_deg, session_count=r.session_count,
                total_exposure_h=round(r.total_h, 1),
            )
            for r in q.all()
        ]

        return TargetListResponse(total=total, page=page, page_size=page_size, pages=pages, items=items)


@app.get("/api/v1/targets/{target_id}", response_model=TargetSchema)
def get_target(target_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        session_count = session.query(sa_func.count(ObsSession.id)).filter(ObsSession.target_id == target_id).scalar()
        total_h = session.query(sa_func.sum(ObsSession.total_exposure_h)).filter(ObsSession.target_id == target_id).scalar() or 0
        return TargetSchema(
            id=target.id, name=target.name, object_type=target.object_type,
            constellation=target.constellation, ra_deg=target.ra_deg, dec_deg=target.dec_deg,
            session_count=session_count, total_exposure_h=round(total_h, 1),
        )


@app.get("/api/v1/targets/{target_id}/sessions", response_model=SessionListResponse)
def get_target_sessions(
    target_id: int,
    camera_id: Optional[int] = Query(None),
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
                ObsSession.id, ObsSession.target_id, ObsSession.date_obs,
                ObsSession.group_key, ObsSession.status,
                ObsSession.total_exposure_s, ObsSession.total_exposure_h,
                ObsSession.frame_count,
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
                id=r.id, target_id=r.target_id, target_name=target.name,
                camera_name=r.camera_name, telescope_name=r.telescope_name,
                date_obs=r.date_obs, group_key=r.group_key, status=r.status,
                total_exposure_s=r.total_exposure_s, total_exposure_h=round(r.total_exposure_h, 2),
                frame_count=r.frame_count,
            )
            for r in q.order_by(ObsSession.date_obs.desc()).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return SessionListResponse(total=total, page=page, page_size=page_size, pages=pages, items=items)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@app.get("/api/v1/sessions", response_model=SessionListResponse)
def list_sessions(
    target_id: Optional[int] = Query(None),
    camera_id: Optional[int] = Query(None),
    telescope_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    sort_by: str = Query("date_obs"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = (
            session.query(
                ObsSession.id, ObsSession.target_id, ObsSession.date_obs,
                ObsSession.group_key, ObsSession.status,
                ObsSession.total_exposure_s, ObsSession.total_exposure_h,
                ObsSession.frame_count,
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
                id=r.id, target_id=r.target_id, target_name=r.target_name,
                camera_name=r.camera_name, telescope_name=r.telescope_name,
                date_obs=r.date_obs, group_key=r.group_key, status=r.status,
                total_exposure_s=r.total_exposure_s, total_exposure_h=round(r.total_exposure_h, 2),
                frame_count=r.frame_count,
            )
            for r in q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return SessionListResponse(total=total, page=page, page_size=page_size, pages=pages, items=items)


@app.get("/api/v1/sessions/{session_id}", response_model=SessionSchema)
def get_session(session_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = (
            session.query(
                ObsSession.id, ObsSession.target_id, ObsSession.date_obs,
                ObsSession.group_key, ObsSession.status,
                ObsSession.total_exposure_s, ObsSession.total_exposure_h,
                ObsSession.frame_count,
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
            id=obs.id, target_id=obs.target_id, target_name=obs.target_name,
            camera_name=obs.camera_name, telescope_name=obs.telescope_name,
            date_obs=obs.date_obs, group_key=obs.group_key, status=obs.status,
            total_exposure_s=obs.total_exposure_s, total_exposure_h=round(obs.total_exposure_h, 2),
            frame_count=obs.frame_count,
        )


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

@app.get("/api/v1/frames", response_model=FrameListResponse)
def list_frames(
    session_id: Optional[int] = Query(None),
    object_name: Optional[str] = Query(None),
    filter_name: Optional[str] = Query(None),
    frame_type: Optional[str] = Query(None),
    camera: Optional[str] = Query(None),
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

        total = q.count()
        pages = (total + page_size - 1) // page_size

        order_col = getattr(Frame, sort_by, Frame.date_obs)
        order_col = order_col.desc() if sort_order == "desc" else order_col.asc()

        items = [
            FrameSchema.model_validate(f)
            for f in q.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()
        ]

        return FrameListResponse(total=total, page=page, page_size=page_size, pages=pages, items=items)


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

@app.get("/api/v1/cameras", response_model=list[CameraSchema])
def list_cameras():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        results = (
            session.query(
                Camera.id, Camera.name, Camera.short_name, Camera.pixel_size_um,
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
                id=r.id, name=r.name, short_name=r.short_name, pixel_size_um=r.pixel_size_um,
                frame_count=r.frame_count, total_exposure_h=round(r.total_s / 3600, 1),
            )
            for r in results
        ]


@app.get("/api/v1/telescopes", response_model=list[TelescopeSchema])
def list_telescopes():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        results = (
            session.query(
                Telescope.id, Telescope.name, Telescope.short_name, Telescope.focal_length_mm,
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
                id=r.id, name=r.name, short_name=r.short_name, focal_length_mm=r.focal_length_mm,
                frame_count=r.frame_count, total_exposure_h=round(r.total_s / 3600, 1),
            )
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
