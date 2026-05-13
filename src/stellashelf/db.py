"""StellaShelf database models and session management.

SQLite with SQLAlchemy ORM + FTS5 full-text search.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Index,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, relationship, Session as SaSession, sessionmaker


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Equipment tables
# ---------------------------------------------------------------------------


class Camera(Base):
    """Astrophotography camera model."""

    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    short_name = Column(String(64), nullable=True)
    pixel_size_um = Column(Float, nullable=True)
    sensor_width_px = Column(Integer, nullable=True)
    sensor_height_px = Column(Integer, nullable=True)
    bit_depth = Column(Integer, nullable=True)
    is_color = Column(Boolean, default=False)

    sessions = relationship("Session", back_populates="camera")


class Telescope(Base):
    """Optical tube assembly or lens."""

    __tablename__ = "telescopes"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    short_name = Column(String(64), nullable=True)
    focal_length_mm = Column(Float, nullable=True)
    aperture_mm = Column(Float, nullable=True)
    f_ratio = Column(Float, nullable=True)

    sessions = relationship("Session", back_populates="telescope")


class Filter(Base):
    """Optical filter."""

    __tablename__ = "filters"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    filter_type = Column(String(32), nullable=True)
    bandwidth_nm = Column(Float, nullable=True)
    wavelength_nm = Column(Float, nullable=True)


# ---------------------------------------------------------------------------
# Target & Session tables
# ---------------------------------------------------------------------------


class Target(Base):
    """Astronomical target object (Deep-sky, Solar system, etc.)."""

    __tablename__ = "targets"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    alt_names = Column(Text, nullable=True)
    object_type = Column(String(64), nullable=True)
    constellation = Column(String(64), nullable=True)
    ra_deg = Column(Float, nullable=True)
    dec_deg = Column(Float, nullable=True)

    sessions = relationship("Session", back_populates="target")


class Session(Base):
    """An observation session: one target, one night, one equipment setup."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)
    target_id = Column(Integer, ForeignKey("targets.id"), nullable=False, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    telescope_id = Column(Integer, ForeignKey("telescopes.id"), nullable=True)

    date_obs = Column(DateTime, nullable=True, index=True)
    date_local = Column(DateTime, nullable=True)
    site_name = Column(String(255), nullable=True)

    group_key = Column(String(255), nullable=False, unique=True, index=True)
    path = Column(Text, nullable=True)

    status = Column(String(32), default="raw")

    total_exposure_s = Column(Float, default=0)
    total_exposure_h = Column(Float, default=0)
    frame_count = Column(Integer, default=0)

    capture_software = Column(String(255), nullable=True)
    observer = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now())
    updated_at = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())

    target = relationship("Target", back_populates="sessions")
    camera = relationship("Camera", back_populates="sessions")
    telescope = relationship("Telescope", back_populates="sessions")
    frames = relationship("Frame", back_populates="obs_session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sessions_target_date", "target_id", "date_obs"),
    )


# ---------------------------------------------------------------------------
# Frame table
# ---------------------------------------------------------------------------


class Frame(Base):
    """Individual frame (light, dark, flat, bias)."""

    __tablename__ = "frames"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)

    filename = Column(String(512), nullable=False)
    filepath = Column(Text, nullable=False, index=True)  # FIX #4: Index for fast dedup
    file_size = Column(Integer, nullable=True)

    frame_type = Column(String(16), nullable=True)

    object_name = Column(String(255), nullable=True, index=True)
    instrume = Column(String(255), nullable=True, index=True)
    telescop = Column(String(255), nullable=True)
    filter_name = Column(String(64), nullable=True, index=True)
    exposure = Column(Float, nullable=True)
    gain = Column(Integer, nullable=True)
    ccd_temp = Column(Float, nullable=True)
    binning = Column(Integer, default=1)
    date_obs = Column(DateTime, nullable=True, index=True)
    date_local = Column(DateTime, nullable=True)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    pixel_size_um = Column(Float, nullable=True)

    ra_deg = Column(Float, nullable=True)
    dec_deg = Column(Float, nullable=True)
    focal_length_mm = Column(Float, nullable=True)

    site_name = Column(String(255), nullable=True)
    observer = Column(String(255), nullable=True)
    creator = Column(String(255), nullable=True)

    fwhm = Column(Float, nullable=True)
    eccentricity = Column(Float, nullable=True)
    snr = Column(Float, nullable=True)

    file_sha256 = Column(String(64), nullable=True, unique=True)

    obs_session = relationship("Session", back_populates="frames")

    scanned_at = Column(DateTime, default=lambda: datetime.now())

    __table_args__ = (
        Index("ix_frames_type_object", "frame_type", "object_name"),
    )


# ---------------------------------------------------------------------------
# Calibration files
# ---------------------------------------------------------------------------


class CalibrationFile(Base):
    """Master calibration file (master dark, bias, flat)."""

    __tablename__ = "calibration_files"

    id = Column(Integer, primary_key=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    cal_type = Column(String(32), nullable=False)
    exposure_s = Column(Float, nullable=True)
    gain = Column(Integer, nullable=True)
    binning = Column(Integer, default=1)
    ccd_temp = Column(Float, nullable=True)
    filter_name = Column(String(64), nullable=True)
    filepath = Column(Text, nullable=False)
    filename = Column(String(512), nullable=False)

    parsed_exposure = Column(Float, nullable=True)
    parsed_gain = Column(Integer, nullable=True)
    parsed_binning = Column(Integer, nullable=True)
    parsed_ccd_temp = Column(Float, nullable=True)

    scanned_at = Column(DateTime, default=lambda: datetime.now())


# ---------------------------------------------------------------------------
# FTS5 full-text search
# ---------------------------------------------------------------------------


def get_db_path(app_dir: Path | None = None) -> Path:
    """Get the database file path."""
    if app_dir is None:
        app_dir = Path.home() / ".stellashelf"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "stellashelf.db"


def init_db(db_path: Path | None = None) -> tuple:
    """Initialize the database and return (engine, SessionLocal)."""
    if db_path is None:
        db_path = get_db_path()

    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS frames_fts USING fts5(
                    object_name,
                    instrume,
                    telescop,
                    filter_name,
                    filename,
                    site_name,
                    content=frames,
                    content_rowid=id
                )
                """
            )
        )
        conn.commit()

    with engine.connect() as conn:
        conn.execute(
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
        conn.execute(
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
        conn.execute(
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
        conn.commit()

    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal