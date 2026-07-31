import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./hostel_management.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# SQLALCHEMY MODELS
# ==========================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)  # e.g., STU001, WAR001, SUP001, SEC001
    name = Column(String)
    hashed_password = Column(String)
    role = Column(String)  # student, warden, supervisor, security
    room_number = Column(String, nullable=True)
    block = Column(String, nullable=True)


class GatePass(Base):
    __tablename__ = "gate_passes"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"))
    reason = Column(String)
    status = Column(String, default="pending")  # pending, approved, rejected
    requested_at = Column(DateTime, default=datetime.datetime.utcnow)
    out_time = Column(String, nullable=True)
    in_time = Column(String, nullable=True)


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    contact = Column(String)
    purpose = Column(String)
    visiting_student_id = Column(String, ForeignKey("users.user_id"))
    qr_code = Column(String, unique=True, index=True)
    status = Column(String, default="pending")  # pending, approved, checked_in, checked_out
    checkin_time = Column(DateTime, nullable=True)


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"))
    category = Column(String)
    description = Column(String)
    status = Column(String, default="open")  # open, resolved
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    content = Column(String)
    posted_by = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"))
    room_number = Column(String)
    status = Column(String, default="active")  # active, acknowledged
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
