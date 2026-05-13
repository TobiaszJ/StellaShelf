"""StellaShelf FastAPI application."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from stellashelf.db import init_db, Target, Session as ObsSession, Frame, Camera, Telescope, CalibrationFile

DB_PATH = Path("~/.stellashelf/stellashelf.db").expanduser().resolve()


def get_session_local():
    """Initialize and return engine, SessionLocal."""
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found at {DB_PATH}. Run 'stellashelf scan' first.")
    return init_db(DB_PATH)


app = FastAPI(title="StellaShelf", version="0.1.0")


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


# ---------------------------------------------------------------------------
# Aggregated schemas
# ---------------------------------------------------------------------------

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
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok", "db": str(DB_PATH)}


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