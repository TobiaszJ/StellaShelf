"""Database model tests."""

import tempfile
from pathlib import Path

from stellashelf.db import CalibrationFile, Camera, Frame, Session, Target, Telescope, init_db


class TestDatabase:
    """Tests for database initialization and basic operations."""

    def test_init_db_creates_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine, SessionLocal = init_db(db_path)

            with SessionLocal() as session:
                # Create a target
                target = Target(name="M33", object_type="Galaxy", constellation="Triangulum")
                session.add(target)
                session.commit()

                assert target.id is not None
                assert target.name == "M33"

    def test_create_session_with_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine, SessionLocal = init_db(db_path)

            with SessionLocal() as session:
                from datetime import datetime

                target = Target(
                    name="NGC 7000", object_type="Emission Nebula", constellation="Cygnus"
                )
                camera = Camera(name="ASI294MMPro", short_name="ASI294MMPro", pixel_size_um=4.63)
                telescope = Telescope(name="_140PH", short_name="140PH", focal_length_mm=676)
                session.add_all([target, camera, telescope])
                session.flush()

                obs = Session(
                    target_id=target.id,
                    camera_id=camera.id,
                    telescope_id=telescope.id,
                    date_obs=datetime(2020, 11, 23, 19, 54, 29),
                    group_key="NGC7000|2020-11-23|ASI294MMPro|140PH|L",
                    total_exposure_s=3000,
                    total_exposure_h=0.833,
                    frame_count=10,
                    status="raw",
                )
                session.add(obs)
                session.commit()

                assert obs.id is not None
                assert obs.target.name == "NGC 7000"

    def test_add_frame(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine, SessionLocal = init_db(db_path)

            with SessionLocal() as session:
                from datetime import datetime

                target = Target(name="M33")
                camera = Camera(name="ASI294MMPro")
                telescope = Telescope(name="_140PH")
                session.add_all([target, camera, telescope])
                session.flush()

                obs = Session(
                    target_id=target.id,
                    camera_id=camera.id,
                    telescope_id=telescope.id,
                    date_obs=datetime(2020, 11, 23),
                    group_key="M33|2020-11-23|ASI294MMPro|140PH|L",
                    status="raw",
                )
                session.add(obs)
                session.flush()

                frame = Frame(
                    session_id=obs.id,
                    filename="M33_L_300sec_1x1_-20C_gain_120_0001.fit",
                    filepath="/mnt/data/Astro/astro/ASI294MMPro/_140PH/M33/2020-11-23/M33_L_300sec_1x1_-20C_gain_120_0001.fit",
                    frame_type="LIGHT",
                    object_name="M33",
                    instrume="ASI Camera (1)",
                    telescop="POTH Hub",
                    filter_name="L",
                    exposure=300.0,
                    gain=120,
                    ccd_temp=-19.8,
                    binning=1,
                    date_obs=datetime(2020, 11, 23, 19, 54, 29),
                    width=4144,
                    height=2822,
                    pixel_size_um=4.63,
                )
                session.add(frame)
                session.commit()

                assert frame.id is not None
                assert frame.object_name == "M33"

    def test_calibration_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            engine, SessionLocal = init_db(db_path)

            with SessionLocal() as session:
                camera = Camera(name="ASI2600MMPro")
                session.add(camera)
                session.flush()

                cal = CalibrationFile(
                    camera_id=camera.id,
                    cal_type="masterdark",
                    exposure_s=300,
                    gain=0,
                    binning=1,
                    ccd_temp=-20.0,
                    filepath="/mnt/data/Astro/astro/ASI2600MMPro/masterdark_300s_1x1_100x_gain_0_-20C.fit",
                    filename="masterdark_300s_1x1_100x_gain_0_-20C.fit",
                )
                session.add(cal)
                session.commit()

                assert cal.id is not None
                assert cal.cal_type == "masterdark"
