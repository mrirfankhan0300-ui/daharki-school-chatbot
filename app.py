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

# IMPORTANT:
# File name model.py hai, is liye "from model" use ho raha hai.
from models import Base, Admission, Admin


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://localhost:5678/webhook-test/school-admission"
)


# =========================================================
# CREATE REQUIRED FOLDERS
# =========================================================

os.makedirs(
    "static",
    exist_ok=True
)

os.makedirs(
    "templates",
    exist_ok=True
)


# =========================================================
# DATABASE TABLES
# =========================================================

Base.metadata.create_all(
    bind=engine
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Daharki School Admission System",
    version="1.0.0"
)


# =========================================================
# TEMPLATES
# =========================================================

templates = Jinja2Templates(
    directory="templates"
)


# =========================================================
# STATIC FILES
# =========================================================

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
        .filter(
            Admin.email == "admin@daharkischool.edu.pk"
        )
        .first()
    )

    if not admin:

        admin = Admin(
            name="School Admin",
            email="admin@daharkischool.edu.pk",
            password="admin123"
        )

        db.add(admin)
        db.commit()

        print("✅ Default admin created")

    else:
        print("✅ Default admin already exists")


# =========================================================
# STARTUP EVENT
# =========================================================

@app.on_event("startup")
def startup_event():

    db = next(get_db())

    try:
        ensure_default_admin(db)

    finally:
        db.close()


# =========================================================
# CHECK ADMIN LOGIN
# =========================================================

def admin_is_logged_in(
    request: Request
) -> bool:

    token = request.cookies.get(
        "admin_session"
    )

    return bool(
        token and token in ADMIN_SESSIONS
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.get("/")
def home(
    request: Request
):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "admin_logged_in":
                admin_is_logged_in(request)
        }
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "message":
            "Daharki School backend is running"
    }


# =========================================================
# CREATE ADMISSION
# =========================================================

@app.post("/api/admissions")
def create_admission(
    admission_data: AdmissionCreate,
    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Get Last Admission
    # -----------------------------------------------------

    last_admission = (
        db.query(Admission)
        .order_by(
            Admission.id.desc()
        )
        .first()
    )


    # -----------------------------------------------------
    # Generate Next Number
    # -----------------------------------------------------

    if last_admission:

        next_number = (
            last_admission.id + 1
        )

    else:

        next_number = 1


    # -----------------------------------------------------
    # Generate Application Number
    # -----------------------------------------------------

    current_year = datetime.now().year

    application_no = (
        f"DSS-ADM-"
        f"{current_year}-"
        f"{next_number:04d}"
    )


    # -----------------------------------------------------
    # Create Admission Record
    # -----------------------------------------------------

    admission = Admission(

        application_no=
            application_no,

        student_name=
            admission_data.student_name.strip(),

        father_name=
            admission_data.father_name.strip(),

        mother_name=
            (admission_data.mother_name or "").strip(),

        date_of_birth=
            admission_data.date_of_birth,

        gender=
            admission_data.gender,

        applying_class=
            admission_data.applying_class.strip(),

        previous_school=
            (
                admission_data.previous_school
                or ""
            ).strip(),

        parent_cnic=
            (
                admission_data.parent_cnic
                or ""
            ).strip(),

        student_cnic=
            (
                admission_data.student_cnic
                or ""
            ).strip(),

        phone=
            admission_data.phone.strip(),

        whatsapp=
            (
                admission_data.whatsapp
                or ""
            ).strip(),

        email=
            (
                admission_data.email
                or ""
            ).strip(),

        address=
            (
                admission_data.address
                or ""
            ).strip(),

        status="PENDING"
    )


    # -----------------------------------------------------
    # Save Into Database
    # -----------------------------------------------------

    db.add(admission)

    db.commit()

    db.refresh(admission)


    # -----------------------------------------------------
    # Send Notification To n8n
    # -----------------------------------------------------

    webhook_sent = False

    try:

        webhook_response = requests.post(

            N8N_WEBHOOK_URL,

            json={

                "application_no":
                    admission.application_no,

                "student_name":
                    admission.student_name,

                "father_name":
                    admission.father_name,

                "mother_name":
                    admission.mother_name,

                "date_of_birth":
                    admission.date_of_birth,

                "gender":
                    admission.gender,

                "applying_class":
                    admission.applying_class,

                "previous_school":
                    admission.previous_school,

                "parent_cnic":
                    admission.parent_cnic,

                "student_cnic":
                    admission.student_cnic,

                "phone":
                    admission.phone,

                "whatsapp":
                    admission.whatsapp,

                "email":
                    admission.email,

                "address":
                    admission.address,

                "status":
                    admission.status
            },

            timeout=5
        )


        if webhook_response.ok:

            webhook_sent = True

            print(
                "✅ n8n webhook successful"
            )

        else:

            print(
                "⚠️ n8n webhook returned:",
                webhook_response.status_code
            )


    except requests.RequestException as error:

        print(
            "⚠️ n8n webhook error:",
            error
        )


    # -----------------------------------------------------
    # API Response
    # -----------------------------------------------------

    return {

        "success": True,

        "message":
            "Admission application submitted successfully",

        "application_no":
            admission.application_no,

        "student_name":
            admission.student_name,

        "status":
            admission.status,

        "admin_notification":
            webhook_sent
    }


# =========================================================
# GET ALL ADMISSIONS
# =========================================================

@app.get("/api/admissions")
def get_admissions(
    request: Request,
    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Admin Authentication
    # -----------------------------------------------------

    if not admin_is_logged_in(request):

        raise HTTPException(

            status_code=
                status.HTTP_401_UNAUTHORIZED,

            detail=
                "Not authenticated as Admin"
        )


    # -----------------------------------------------------
    # Get Records
    # -----------------------------------------------------

    admissions = (

        db.query(Admission)

        .order_by(
            Admission.id.desc()
        )

        .all()
    )


    return admissions


# =========================================================
# UPDATE ADMISSION STATUS
# =========================================================

@app.patch(
    "/api/admissions/{application_no}"
)
def update_admission_status(

    application_no: str,

    status_update: StatusUpdate,

    request: Request,

    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Check Admin Login
    # -----------------------------------------------------

    if not admin_is_logged_in(request):

        raise HTTPException(

            status_code=
                status.HTTP_401_UNAUTHORIZED,

            detail=
                "Not authenticated as Admin"
        )


    # -----------------------------------------------------
    # Find Admission
    # -----------------------------------------------------

    admission = (

        db.query(Admission)

        .filter(
            Admission.application_no
            == application_no
        )

        .first()
    )


    if not admission:

        raise HTTPException(

            status_code=404,

            detail=
                "Application record not found"
        )


    # -----------------------------------------------------
    # Validate Status
    # -----------------------------------------------------

    new_status = (
        status_update.status
        .strip()
        .upper()
    )


    allowed_statuses = [

        "PENDING",

        "APPROVED",

        "REJECTED"
    ]


    if new_status not in allowed_statuses:

        raise HTTPException(

            status_code=400,

            detail="Invalid status"
        )


    # -----------------------------------------------------
    # Update Database
    # -----------------------------------------------------

    admission.status = new_status

    db.commit()

    db.refresh(admission)


    return {

        "success": True,

        "application_no":
            admission.application_no,

        "new_status":
            admission.status
    }


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.post("/api/admin/login")
def admin_login(

    email: str = Form(...),

    password: str = Form(...),

    db: Session = Depends(get_db)
):

    # -----------------------------------------------------
    # Find Admin
    # -----------------------------------------------------

    admin = (

        db.query(Admin)

        .filter(
            Admin.email == email.strip()
        )

        .first()
    )


    # -----------------------------------------------------
    # Validate Login
    # -----------------------------------------------------

    if (
        not admin
        or admin.password != password
    ):

        raise HTTPException(

            status_code=
                status.HTTP_401_UNAUTHORIZED,

            detail=
                "Invalid email or password"
        )


    # -----------------------------------------------------
    # Create Session
    # -----------------------------------------------------

    session_token = (
        secrets.token_hex(32)
    )

    ADMIN_SESSIONS.add(
        session_token
    )


    # -----------------------------------------------------
    # Redirect To Homepage
    # -----------------------------------------------------

    response = RedirectResponse(

        url="/",

        status_code=
            status.HTTP_303_SEE_OTHER
    )


    response.set_cookie(

        key="admin_session",

        value=session_token,

        httponly=True,

        samesite="lax"
    )


    return response


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

        ADMIN_SESSIONS.remove(
            token
        )


    response = RedirectResponse(

        url="/",

        status_code=
            status.HTTP_303_SEE_OTHER
    )


    response.delete_cookie(
        key="admin_session"
    )


    return response