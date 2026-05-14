"""
ImporterService handles the orchestration of scanning files and importing them into the database.
This service centralizes the logic previously duplicated in the CLI and API.
"""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import text

from stellashelf.db import CalibrationFile, Camera, Frame, Target, Telescope, init_db
from stellashelf.db import Session as ObsSession
from stellashelf.scanner import generate_group_key, generate_thumbnail, scan_directory


class ImporterService:
    """
    Service responsible for the core import pipeline:
    1. Scanning the filesystem for FITS/XISF files.
    2. Extracting and normalizing metadata.
    3. Persisting metadata into the SQLite database.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def import_from_path(
        self,
        root_path: Path,
        recursive: bool = True,
        progress_callback: Callable[[int, int, Path], None] | None = None,
    ) -> dict[str, int]:
        """
        Performs the full scan and import process.

        Returns a dictionary containing:
            imported: Number of new frames added.
            skipped: Number of duplicate frames skipped.
            calibration_files: Number of calibration files identified.
        """
        engine, SessionLocal = init_db(self.db_path)

        # 1. Perform the scan
        frames = scan_directory(root_path, recursive=recursive, progress_callback=progress_callback)

        stats = {"imported": 0, "skipped": 0, "calibration_files": 0}

        if not frames:
            return stats

        with SessionLocal() as session:
            # Pre-load existing data to avoid redundant queries and ensure speed
            existing_paths: set[str] = {row[0] for row in session.query(Frame.filepath).all()}
            sessions_by_key: dict[str, int] = {
                row[1]: row[0] for row in session.query(ObsSession.id, ObsSession.group_key).all()
            }
            cameras_by_name: dict[str, int] = {
                row[1]: row[0] for row in session.query(Camera.id, Camera.name).all()
            }
            telescopes_by_name: dict[str, int] = {
                row[1]: row[0] for row in session.query(Telescope.id, Telescope.name).all()
            }
            targets_by_name: dict[str, int] = {
                row[1]: row[0] for row in session.query(Target.id, Target.name).all()
            }

            cal_files_count = 0
            imported_count = 0
            skipped_count = 0

            # Batching configuration
            BATCH_SIZE = 500
            batch_counter = 0

            for i, frame in enumerate(frames):
                # Determine if this is a calibration file
                is_calibration = not frame.object_name and frame.frame_type in (
                    "BIAS",
                    "DARK",
                    "FLAT",
                    "FLATFIELD",
                )

                # 1. Handle Equipment (Camera/Telescope)
                camera_id = None
                if frame.instrume:
                    if frame.instrume not in cameras_by_name:
                        camera = Camera(
                            name=frame.instrume,
                            short_name=frame.instrume.replace("ZWO ", "").replace(
                                "ASI Camera", "ASI"
                            ),
                            pixel_size_um=frame.pixel_size_um,
                        )
                        session.add(camera)
                        session.flush()
                        cameras_by_name[frame.instrume] = camera.id
                    camera_id = cameras_by_name[frame.instrume]

                telescope_id = None
                if frame.telescop:
                    if frame.telescop not in telescopes_by_name:
                        telescope = Telescope(
                            name=frame.telescop,
                            short_name=frame.telescop,
                            focal_length_mm=frame.focal_length_mm,
                        )
                        session.add(telescope)
                        session.flush()
                        telescopes_by_name[frame.telescop] = telescope.id
                    telescope_id = telescopes_by_name[frame.telescop]

                # 2. Handle Calibration Files
                if is_calibration:
                    cal = CalibrationFile(
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
                    cal_files_count += 1
                    imported_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(frames), frame.filepath)
                    continue

                # 3. Handle Target and Session
                target_id = None
                obj_name = frame.object_name.strip() if frame.object_name else ""

                if obj_name and obj_name != "UNKNOWN":
                    if obj_name not in targets_by_name:
                        target = Target(name=obj_name)
                        session.add(target)
                        session.flush()
                        targets_by_name[obj_name] = target.id
                    target_id = targets_by_name[obj_name]
                else:
                    if "UNKNOWN" not in targets_by_name:
                        unk = Target(name="UNKNOWN")
                        session.add(unk)
                        session.flush()
                        targets_by_name["UNKNOWN"] = unk.id
                    target_id = targets_by_name["UNKNOWN"]
                    obj_name = "UNKNOWN"

                # 4. Duplicate Check
                fp_str = str(frame.filepath)
                if fp_str in existing_paths:
                    skipped_count += 1
                    if progress_callback:
                        progress_callback(i + 1, len(frames), frame.filepath)
                    continue

                existing_paths.add(fp_str)

                # 5. Session Management
                group_key = generate_group_key(frame)
                obs_id = sessions_by_key.get(group_key)

                if obs_id is None:
                    existing_session = (
                        session.query(ObsSession).filter_by(group_key=group_key).first()
                    )
                    if existing_session:
                        obs_id = existing_session.id
                        sessions_by_key[group_key] = obs_id
                    else:
                        new_session = ObsSession(
                            target_id=target_id,
                            camera_id=camera_id,
                            telescope_id=telescope_id,
                            date_obs=frame.date_obs,
                            group_key=group_key,
                            path=str(frame.filepath.parent),
                            status="raw",
                        )
                        session.add(new_session)
                        session.flush()
                        obs_id = new_session.id
                        sessions_by_key[group_key] = obs_id

                # 6. Add Frame
                new_frame = Frame(
                    session_id=obs_id,
                    filename=frame.filename,
                    filepath=fp_str,
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
                session.add(new_frame)
                imported_count += 1

                if progress_callback:
                    progress_callback(i + 1, len(frames), frame.filepath)

                batch_counter += 1
                if batch_counter >= BATCH_SIZE:
                    session.commit()
                    batch_counter = 0

            session.commit()

            # Recalculate session stats
            session.execute(
                text(
                    """
                UPDATE sessions SET
                    frame_count = (SELECT COUNT(*) FROM frames WHERE frames.session_id = sessions.id),
                    total_exposure_s = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0),
                    total_exposure_h = COALESCE((SELECT SUM(frames.exposure) FROM frames WHERE frames.session_id = sessions.id), 0) / 3600.0
                """
                )
            )
            session.commit()

            stats["imported"] = imported_count
            stats["skipped"] = skipped_count
            stats["calibration_files"] = cal_files_count

        # Generate thumbnails for newly imported light frames
        if imported_count > 0:
            try:
                with SessionLocal() as session:
                    light_frames = (
                        session.query(Frame)
                        .filter(Frame.frame_type == "LIGHT")
                        .order_by(Frame.date_obs.desc())
                        .limit(20)
                        .all()
                    )
                    for f in light_frames:
                        fp = Path(f.filepath)
                        if fp.exists():
                            generate_thumbnail(fp)
            except Exception:
                pass

        return stats
