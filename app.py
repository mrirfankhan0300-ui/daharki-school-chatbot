from datetime import datetime
import os
import secrets
import requests

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    Form,
    status
)

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import engine, get_db
from models import Base, Admission, Admin


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://localhost:5678/webhook-test/school-admission"
)

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "admin@daharkischool.edu.pk"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "admin123"
)


# =========================================================
# REQUIRED FOLDERS
# =========================================================

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)


# =========================================================
# DATABASE TABLES
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Daharki School Admission System",
    version="1.0.0"
)


# =========================================================
# TEMPLATES / STATIC
# =========================================================

templates = Jinja2Templates(
    directory="templates"
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# =========================================================
# ADMIN SESSION STORAGE
# =========================================================

ADMIN_SESSIONS = set()


# =========================================================
# PYDANTIC MODELS
# =========================================================

class AdmissionCreate(BaseModel):
    student_name: str
    father_name: str
    mother_name: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    applying_class: str
    previous_school: str | None = None
    parent_cnic: str | None = None
    student_cnic: str | None = None
    phone: str
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None


class StatusUpdate(BaseModel):
    status: str


# =========================================================
# DEFAULT ADMIN
# =========================================================

def ensure_default_admin(db: Session):

    admin = (
        db.query(Admin)
        .filter(Admin.email == ADMIN_EMAIL)
        .first()
    )

    if not admin:

        admin = Admin(
            name="School Admin",
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD
        )

        db.add(admin)
        db.commit()

        print("✅ Default admin created")

    else:

        # Keep DB password synced with environment variable
        admin.password = ADMIN_PASSWORD
        db.commit()

        print("✅ Default admin already exists")


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup_event():

    db = next(get_db())

    try:
        ensure_default_admin(db)

    finally:
        db.close()


# =========================================================
# ADMIN AUTH CHECK
# =========================================================

def admin_is_logged_in(request: Request) -> bool:

    token = request.cookies.get("admin_session")

    return bool(
        token and token in ADMIN_SESSIONS
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.get("/")
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "admin_logged_in": admin_is_logged_in(request)
        }
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "message": "Daharki School backend is running"
    }


# =========================================================
# CREATE ADMISSION
# =========================================================

@app.post("/api/admissions")
def create_admission(
    admission_data: AdmissionCreate,
    db: Session = Depends(get_db)
):

    last_admission = (
        db.query(Admission)
        .order_by(Admission.id.desc())
        .first()
    )

    next_number = (
        last_admission.id + 1
        if last_admission
        else 1
    )

    current_year = datetime.now().year

    application_no = (
        f"DSS-ADM-{current_year}-{next_number:04d}"
    )

    admission = Admission(
        application_no=application_no,
        student_name=admission_data.student_name.strip(),
        father_name=admission_data.father_name.strip(),
        mother_name=(admission_data.mother_name or "").strip(),
        date_of_birth=admission_data.date_of_birth,
        gender=admission_data.gender,
        applying_class=admission_data.applying_class.strip(),
        previous_school=(admission_data.previous_school or "").strip(),
        parent_cnic=(admission_data.parent_cnic or "").strip(),
        student_cnic=(admission_data.student_cnic or "").strip(),
        phone=admission_data.phone.strip(),
        whatsapp=(admission_data.whatsapp or "").strip(),
        email=(admission_data.email or "").strip(),
        address=(admission_data.address or "").strip(),
        status="PENDING"
    )

    db.add(admission)
    db.commit()
    db.refresh(admission)


    # -----------------------------------------------------
    # n8n Notification
    # -----------------------------------------------------

    webhook_sent = False

    try:

        response = requests.post(
            N8N_WEBHOOK_URL,
            json={
                "application_no": admission.application_no,
                "student_name": admission.student_name,
                "father_name": admission.father_name,
                "mother_name": admission.mother_name,
                "date_of_birth": admission.date_of_birth,
                "gender": admission.gender,
                "applying_class": admission.applying_class,
                "previous_school": admission.previous_school,
                "parent_cnic": admission.parent_cnic,
                "student_cnic": admission.student_cnic,
                "phone": admission.phone,
                "whatsapp": admission.whatsapp,
                "email": admission.email,
                "address": admission.address,
                "status": admission.status
            },
            timeout=5
        )

        if response.ok:
            webhook_sent = True

    except Exception as error:
        print("⚠️ n8n webhook error:", error)


    return {
        "success": True,
        "message": "Admission application submitted successfully",
        "application_no": admission.application_no,
        "student_name": admission.student_name,
        "status": admission.status,
        "admin_notification": webhook_sent
    }


# =========================================================
# ADMIN LOGIN PAGE
# =========================================================

@app.get("/admin/login")
def admin_login_page(
    request: Request
):

    if admin_is_logged_in(request):

        return RedirectResponse(
            url="/admin/dashboard",
            status_code=303
        )

    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "error": None
        }
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.post("/api/admin/login")
def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    admin = (
        db.query(Admin)
        .filter(Admin.email == email.strip())
        .first()
    )

    if (
        not admin
        or admin.password != password
    ):

        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "error": "Invalid email or password"
            },
            status_code=401
        )


    session_token = secrets.token_hex(32)

    ADMIN_SESSIONS.add(
        session_token
    )

    response = RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )

    response.set_cookie(
        key="admin_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=3600
    )

    return response


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.get("/admin/dashboard")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    if not admin_is_logged_in(request):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    admissions = (
        db.query(Admission)
        .order_by(Admission.id.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "admissions": admissions
        }
    )


# =========================================================
# ADMIN API - GET ADMISSIONS
# =========================================================

@app.get("/api/admin/admissions")
def get_admissions(
    request: Request,
    db: Session = Depends(get_db)
):

    if not admin_is_logged_in(request):

        raise HTTPException(
            status_code=401,
            detail="Admin login required"
        )

    return (
        db.query(Admission)
        .order_by(Admission.id.desc())
        .all()
    )


# =========================================================
# UPDATE ADMISSION STATUS
# =========================================================

@app.post(
    "/admin/admissions/{application_no}/status"
)
def update_admission_status(
    application_no: str,
    new_status: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db)
):

    if not admin_is_logged_in(request):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )

    admission = (
        db.query(Admission)
        .filter(
            Admission.application_no == application_no
        )
        .first()
    )

    if not admission:

        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    new_status = (
        new_status.strip().upper()
    )

    if new_status not in [
        "PENDING",
        "APPROVED",
        "REJECTED"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    admission.status = new_status

    db.commit()

    return RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.get("/api/admin/logout")
def admin_logout(
    request: Request
):

    token = request.cookies.get(
        "admin_session"
    )

    if (
        token
        and token in ADMIN_SESSIONS
    ):

        ADMIN_SESSIONS.remove(token)

    response = RedirectResponse(
        url="/admin/login",
        status_code=303
    )

    response.delete_cookie(
        "admin_session"
    )

    return response