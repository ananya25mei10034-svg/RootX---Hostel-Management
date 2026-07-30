import datetime
import uuid
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db, User, GatePass, Visitor, Complaint, Announcement, EmergencyAlert
from auth import (
    get_current_user,
    verify_password,
    create_access_token,
    seed_default_users
)

app = FastAPI(title="XYZ Hostel Management Portal API", version="1.0.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
    seed_default_users()


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    name: str


class GatePassCreate(BaseModel):
    reason: str
    out_time: Optional[str] = None
    in_time: Optional[str] = None


class GatePassUpdate(BaseModel):
    status: str  # approved, rejected


class VisitorCreate(BaseModel):
    name: str
    contact: str
    purpose: str


class ComplaintCreate(BaseModel):
    category: str
    description: str


class AnnouncementCreate(BaseModel):
    title: str
    content: str


# ==========================================
# API ENDPOINTS
# ==========================================

# --- 1. AUTHENTICATION ---
@app.post("/api/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == form_data.username.upper()).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect User ID or Password")

    access_token = create_access_token(data={"sub": user.user_id, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.user_id,
        "name": user.name
    }


# --- 2. GATE / LEAVE PASSES ---
@app.get("/api/gatepass")
def get_gate_passes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "student":
        return db.query(GatePass).filter(GatePass.student_id == current_user.user_id).all()
    return db.query(GatePass).all()


@app.post("/api/gatepass")
def create_gate_pass(data: GatePassCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can apply for gate passes")

    new_pass = GatePass(
        student_id=current_user.user_id,
        reason=data.reason,
        out_time=data.out_time,
        in_time=data.in_time
    )
    db.add(new_pass)
    db.commit()
    return {"message": "Gate pass submitted successfully"}


@app.put("/api/gatepass/{pass_id}")
def update_gate_pass_status(pass_id: int, data: GatePassUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["warden", "supervisor"]:
        raise HTTPException(status_code=403, detail="Unauthorized to approve passes")

    pass_obj = db.query(GatePass).filter(GatePass.id == pass_id).first()
    if not pass_obj:
        raise HTTPException(status_code=404, detail="Gate pass not found")

    pass_obj.status = data.status
    db.commit()
    return {"message": f"Gate pass status changed to {data.status}"}


# --- 3. VISITORS & QR CODES ---
@app.get("/api/visitors")
def get_visitors(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "student":
        return db.query(Visitor).filter(Visitor.visiting_student_id == current_user.user_id).all()
    return db.query(Visitor).all()


@app.post("/api/visitors")
def request_visitor_pass(data: VisitorCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can request visitor passes")

    unique_code = uuid.uuid4().hex[:10].upper()
    visitor = Visitor(
        name=data.name,
        contact=data.contact,
        purpose=data.purpose,
        visiting_student_id=current_user.user_id,
        qr_code=unique_code,
        status="pending"
    )
    db.add(visitor)
    db.commit()
    return {"message": "Visitor pass requested", "code": unique_code}


@app.put("/api/visitors/{visitor_id}/approve")
def approve_visitor(visitor_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["warden", "supervisor"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor request not found")

    visitor.status = "approved"
    db.commit()
    return {"message": "Visitor approved successfully"}


@app.post("/api/security/scan-qr/{qr_code}")
def scan_visitor_qr(qr_code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["security", "warden", "supervisor"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    visitor = db.query(Visitor).filter(Visitor.qr_code == qr_code).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Invalid QR Code")

    if visitor.status != "approved":
        raise HTTPException(status_code=400, detail=f"Visitor status is '{visitor.status}'. Pass not active.")

    visitor.status = "checked_in"
    visitor.checkin_time = datetime.datetime.utcnow()
    db.commit()
    return {"message": f"Visitor {visitor.name} checked in successfully", "visitor": visitor}


# --- 4. COMPLAINTS ---
@app.get("/api/complaints")
def get_complaints(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "student":
        return db.query(Complaint).filter(Complaint.student_id == current_user.user_id).all()
    return db.query(Complaint).all()


@app.post("/api/complaints")
def raise_complaint(data: ComplaintCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can raise complaints")

    complaint = Complaint(
        student_id=current_user.user_id,
        category=data.category,
        description=data.description
    )
    db.add(complaint)
    db.commit()
    return {"message": "Complaint raised successfully"}


@app.put("/api/complaints/{complaint_id}/resolve")
def resolve_complaint(complaint_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["warden", "supervisor"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.status = "resolved"
    db.commit()
    return {"message": "Complaint marked as resolved"}


# --- 5. ANNOUNCEMENTS ---
@app.get("/api/announcements")
def get_announcements(db: Session = Depends(get_db)):
    return db.query(Announcement).order_by(Announcement.created_at.desc()).all()


@app.post("/api/announcements")
def post_announcement(data: AnnouncementCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "warden":
        raise HTTPException(status_code=403, detail="Only Wardens can post announcements")

    announcement = Announcement(
        title=data.title,
        content=data.content,
        posted_by=f"{current_user.name} ({current_user.role.capitalize()})"
    )
    db.add(announcement)
    db.commit()
    return {"message": "Announcement posted successfully"}


# --- 6. EMERGENCY SOS ALERTS ---
@app.post("/api/sos")
def trigger_sos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can trigger SOS alerts")

    alert = EmergencyAlert(
        student_id=current_user.user_id,
        room_number=current_user.room_number or "Unknown"
    )
    db.add(alert)
    db.commit()
    return {"message": "Emergency SOS triggered! Wardens and security notified."}


@app.get("/api/sos")
def get_active_sos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["warden", "supervisor", "security"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return db.query(EmergencyAlert).filter(EmergencyAlert.status == "active").all()


@app.put("/api/sos/{alert_id}/acknowledge")
def acknowledge_sos(alert_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["warden", "supervisor", "security"]:
        raise HTTPException(status_code=403, detail="Unauthorized")

    alert = db.query(EmergencyAlert).filter(EmergencyAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    db.commit()
    return {"message": "SOS Alert acknowledged"}

