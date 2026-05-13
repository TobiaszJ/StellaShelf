"""StellaShelf FastAPI application."""

import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from stellashelf.db import init_db, Target, Session as ObsSession, Frame, Camera, Telescope, CalibrationFile

DB_PATH = Path("~/stellashelf/stellashelf.db").expanduser().resolve()


def get_session_local():
    """Initialize and return engine, SessionLocal."""
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found at {DB_PATH}. Run 'stellashelf scan' first.")
    return init_db(DB_PATH)


app = FastAPI(title="StellaShelf", version="0.1.0")


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
    "current_file": "",
    "phase": "idle",  # idle, scanning, importing, done
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


def _run_scan(root: Path, recursive: bool):
    """Background thread function: scan + import frames."""
    global _scan_state
    try:
        from stellashelf.scanner import scan_directory, generate_group_key
        from stellashelf.db import init_db as db_init

        progress_cb = _make_scan_progress_callback()

        # Phase: scanning
        with _scan_lock:
            _scan_state["phase"] = "scanning"

        frames = scan_directory(root, recursive=recursive, progress_callback=progress_cb)

        # Phase: importing
        with _scan_lock:
            _scan_state["phase"] = "importing"
            _scan_state["total"] = len(frames)
            _scan_state["processed"] = 0

        db_path = DB_PATH
        if not db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)

        engine, SessionLocal = db_init(db_path)

        imported = 0
        skipped = 0
        batch_count = 0
        BATCH_SIZE = 500

        with SessionLocal() as session:
            cameras_seen: dict[str, int] = {}
            telescopes_seen: dict[str, int] = {}
            targets_seen: dict[str, int] = {}
            sessions_seen: dict[str, int] = {}
            cal_files_seen: int = 0

            existing_paths = set()
            for row in session.query(Frame.filepath).all():
                existing_paths.add(row[0])

            for row in session.query(ObsSession.id, ObsSession.group_key).all():
                sessions_seen[row[1]] = row[0]

            for row in session.query(Camera.id, Camera.name).all():
                cameras_seen[row[1]] = row[0]
            for row in session.query(Telescope.id, Telescope.name).all():
                telescopes_seen[row[1]] = row[0]
            for row in session.query(Target.id, Target.name).all():
                targets_seen[row[1]] = row[0]

            for idx, frame in enumerate(frames):
                # Equipment
                camera_id = None
                if frame.instrume:
                    if frame.instrume not in cameras_seen:
                        camera = Camera(
                            name=frame.instrume,
                            short_name=frame.instrume.replace("ZWO ", "").replace("ASI Camera", "ASI"),
                            pixel_size_um=frame.pixel_size_um,
                        )
                        session.add(camera)
                        session.flush()
                        cameras_seen[frame.instrume] = camera.id
                    camera_id = cameras_seen[frame.instrume]

                telescope_id = None
                if frame.telescop:
                    if frame.telescop not in telescopes_seen:
                        telescope = Telescope(
                            name=frame.telescop,
                            short_name=frame.telescop,
                            focal_length_mm=frame.focal_length_mm,
                        )
                        session.add(telescope)
                        session.flush()
                        telescopes_seen[frame.telescop] = telescope.id
                    telescope_id = telescopes_seen[frame.telescop]

                # Calibration files
                if not frame.object_name and frame.frame_type in ("BIAS", "DARK", "FLAT"):
                    from stellashelf.db import CalibrationFile as CalFile
                    cal = CalFile(
                        camera_id=camera_id,
                        cal_type=frame.frame_type.lower(),
                        exposure_s=frame.exposure,
                        gain=frame.gain,
                        binning=frame.binning,
                        ccd_temp=frame.ccd_temp,
                        filepath=str(frame.filepath),
                        filename=frame.filename,
                    )
                    session.add(cal)
                    cal_files_seen += 1
                    # Update progress
                    with _scan_lock:
                        _scan_state["processed"] = idx + 1
                        _scan_state["imported"] = imported + cal_files_seen
                    continue

                # Target
                target_id = None
                obj_name = frame.object_name.strip() if frame.object_name else ""
                if obj_name and obj_name != "UNKNOWN":
                    if obj_name not in targets_seen:
                        target = Target(name=obj_name)
                        session.add(target)
                        session.flush()
                        targets_seen[obj_name] = target.id
                    target_id = targets_seen.get(obj_name)

                # Duplicate check
                fp = str(frame.filepath)
                if fp in existing_paths:
                    skipped += 1
                    with _scan_lock:
                        _scan_state["processed"] = idx + 1
                        _scan_state["skipped"] = skipped
                    continue
                existing_paths.add(fp)

                # Session
                group_key = generate_group_key(frame)
                obs_id = sessions_seen.get(group_key)

                if obs_id is None:
                    if target_id is None:
                        if "UNKNOWN" not in targets_seen:
                            unk = Target(name="UNKNOWN")
                            session.add(unk)
                            session.flush()
                            targets_seen["UNKNOWN"] = unk.id
                        target_id = targets_seen["UNKNOWN"]

                    existing_session = session.query(ObsSession).filter_by(group_key=group_key).first()
                    if existing_session:
                        obs_id = existing_session.id
                        sessions_seen[group_key] = obs_id
                    else:
                        obs = ObsSession(
                            target_id=target_id,
                            camera_id=camera_id,
                            telescope_id=telescope_id,
                            date_obs=frame.date_obs,
                            group_key=group_key,
                            path=str(frame.filepath.parent),
                            status="raw",
                        )
                        session.add(obs)
                        session.flush()
                        obs_id = obs.id
                        sessions_seen[group_key] = obs_id

                # Frame record
                db_frame = Frame(
                    session_id=obs_id,
                    filename=frame.filename,
                    filepath=fp,
                    file_size=frame.file_size,
                    frame_type=frame.frame_type or "LIGHT",
                    object_name=obj_name,
                    instrume=frame.instrume or "",
                    telescop=frame.telescop or "",
                    filter_name=frame.filter_name or "",
                    exposure=frame.exposure,
                    gain=frame.gain,
                    ccd_temp=frame.ccd_temp,
                    binning=frame.binning,
                    date_obs=frame.date_obs,
                    date_local=frame.date_local,
                    width=frame.width,
                    height=frame.height,
                    pixel_size_um=frame.pixel_size_um,
                    focal_length_mm=frame.focal_length_mm,
                    ra_deg=frame.ra_deg,
                    dec_deg=frame.dec_deg,
                    site_name=frame.site_name or "",
                    observer=frame.observer or "",
                    creator=frame.creator or "",
                )
                session.add(db_frame)
                imported += 1
                batch_count += 1

                if batch_count >= BATCH_SIZE:
                    session.commit()
                    batch_count = 0

                # Update progress
                with _scan_lock:
                    _scan_state["processed"] = idx + 1
                    _scan_state["imported"] = imported
                    _scan_state["skipped"] = skipped

            session.commit()

            # Recalculate session stats
            session.execute(
                """
                UPDATE sessions SET
                    frame_count = (SELECT COUNT(*) FROM frames WHERE frames.session_id = sessions.id),
                    total_exposure_s = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0),
                    total_exposure_h = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0) / 3600.0
                """
            )
            session.commit()

        with _scan_lock:
            _scan_state["running"] = False
            _scan_state["phase"] = "done"
            _scan_state["imported"] = imported
            _scan_state["skipped"] = skipped
            _scan_state["current_file"] = "Scan complete"

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


class SessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    date_obs: datetime
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


class TelescopeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_name: Optional[str]
    focal_length_mm: Optional[float]


class CalibrationFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_id: int
    cal_type: str
    exposure_s: Optional[float]
    gain: Optional[int]
    binning: int
    ccd_temp: Optional[float]
    filepath: str
    filename: str


class TargetDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    object_type: Optional[str] = None
    constellation: Optional[str] = None
    sessions: list[SessionSchema] = []


class SessionDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    target_id: int
    date_obs: datetime
    group_key: str
    status: str
    total_exposure_s: float
    total_exposure_h: float
    frame_count: int
    camera: Optional[CameraSchema] = None
    telescope: Optional[TelescopeSchema] = None
    frames: list[FrameSchema] = []


# ---------------------------------------------------------------------------
# Scan request schema
# ---------------------------------------------------------------------------

class ScanRequest(BaseModel):
    path: str
    recursive: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "db": str(DB_PATH)}


# --- Scan endpoints ---

@app.post("/api/v1/scan")
def start_scan(request: ScanRequest):
    """Start a background scan of FITS files."""
    global _scan_state

    with _scan_lock:
        if _scan_state["running"]:
            raise HTTPException(status_code=409, detail="A scan is already running")

    scan_path = Path(request.path)

    # Security: validate path prefix
    allowed_prefix = "/mnt/data/Astro"
    resolved = scan_path.resolve()
    if not str(resolved).startswith(allowed_prefix):
        raise HTTPException(
            status_code=403,
            detail=f"Path must start with {allowed_prefix}"
        )

    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=404, detail=f"Path not found: {resolved}")

    with _scan_lock:
        _scan_state["running"] = True
        _scan_state["total"] = 0
        _scan_state["processed"] = 0
        _scan_state["imported"] = 0
        _scan_state["skipped"] = 0
        _scan_state["current_file"] = "Initializing..."
        _scan_state["phase"] = "scanning"
        _scan_state["error"] = None

    thread = threading.Thread(
        target=_run_scan,
        args=(resolved, request.recursive),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "path": str(resolved)}


@app.get("/api/v1/scan/status")
def scan_status():
    """Get current scan progress."""
    with _scan_lock:
        return dict(_scan_state)


# --- Targets ---

@app.get("/api/v1/targets", response_model=list[TargetSchema])
def list_targets(
    search: Optional[str] = Query(None, description="Search targets by name"),
    sort_by: str = Query("name", regex="^(name|object_type|constellation)$"),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = session.query(Target)
        if search:
            q = q.filter(Target.name.ilike(f"%{search}%"))
        q = q.order_by(getattr(Target, sort_by))
        return q.all()


@app.get("/api/v1/targets/{target_id}", response_model=TargetDetailSchema)
def get_target(target_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        return target


@app.get("/api/v1/targets/{target_id}/sessions", response_model=list[SessionSchema])
def get_target_sessions(target_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        target = session.query(Target).get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        return target.sessions


# --- Sessions ---

@app.get("/api/v1/sessions", response_model=list[SessionSchema])
def list_sessions(
    target_id: Optional[int] = Query(None),
    camera_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("date_obs", regex="^(date_obs|total_exposure_h|frame_count|status)$"),
):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        q = session.query(ObsSession)
        if target_id is not None:
            q = q.filter(ObsSession.target_id == target_id)
        if camera_id is not None:
            q = q.filter(ObsSession.camera_id == camera_id)
        if status is not None:
            q = q.filter(ObsSession.status == status)
        q = q.order_by(getattr(ObsSession, sort_by))
        return q.all()


@app.get("/api/v1/sessions/{session_id}", response_model=SessionDetailSchema)
def get_session(session_id: int):
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        obs = session.query(ObsSession).get(session_id)
        if not obs:
            raise HTTPException(status_code=404, detail="Session not found")
        return obs


# --- Frames ---

@app.get("/api/v1/frames", response_model=list[FrameSchema])
def list_frames(
    session_id: Optional[int] = Query(None),
    object_name: Optional[str] = Query(None),
    filter_name: Optional[str] = Query(None),
    frame_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
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
        q = q.order_by(Frame.date_obs).limit(limit)
        return q.all()


# --- Equipment ---

@app.get("/api/v1/cameras", response_model=list[CameraSchema])
def list_cameras():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        return session.query(Camera).all()


@app.get("/api/v1/telescopes", response_model=list[TelescopeSchema])
def list_telescopes():
    engine, SessionLocal = get_session_local()
    with SessionLocal() as session:
        return session.query(Telescope).all()


# --- Statistics ---

@app.get("/api/v1/stats")
def get_stats():
    from sqlalchemy import func as sa_func

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
            "total_exposure_h": round(total_exposure_h, 2),
        }


# ---------------------------------------------------------------------------
# Static files (frontend)
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (FRONTEND_DIR / "index.html").read_text()
