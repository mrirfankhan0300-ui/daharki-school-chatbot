from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session
from pydantic import BaseModel

from datetime import datetime

import secrets
import os
import requests

from dotenv import load_dotenv

from database import engine, get_db
from models import Base, Admission, Admin


# =========================================================
# ENV SETTINGS
# =========================================================

load_dotenv()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "http://localhost:5678/webhook-test/school-admission"
)


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Daharki School Admission System"
)

templates = Jinja2Templates(
    directory="templates"
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# =========================================================
# ADMIN SESSION
# =========================================================

ADMIN_SESSIONS = set()


# =========================================================
# PYDANTIC MODEL
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

    phone: str

    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None


# =========================================================
# DEFAULT ADMIN
# =========================================================

def ensure_default_admin(db: Session):

    admin = (
        db.query(Admin)
        .filter(
            Admin.email ==
            "admin@daharkischool.edu.pk"
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
        context={}
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

    # Last admission record
    last = (
        db.query(Admission)
        .order_by(
            Admission.id.desc()
        )
        .first()
    )

    # Next number
    next_number = (
        last.id + 1
        if last
        else 1
    )

    # Application number
    application_no = (
        f"DSS-ADM-"
        f"{datetime.now().year}-"
        f"{next_number:04d}"
    )


    # =====================================================
    # CREATE DATABASE RECORD
    # =====================================================

    admission = Admission(

        application_no=
            application_no,

        student_name=
            admission_data
            .student_name
            .strip(),

        father_name=
            admission_data
            .father_name
            .strip(),

        mother_name=
            (
                admission_data.mother_name
                or ""
            ).strip(),

        date_of_birth=
            admission_data.date_of_birth,

        gender=
            admission_data.gender,

        applying_class=
            admission_data.applying_class,

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

        phone=
            admission_data
            .phone
            .strip(),

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


    # =====================================================
    # SAVE DATABASE FIRST
    # =====================================================

    db.add(admission)

    db.commit()

    db.refresh(admission)


    # =====================================================
    # SEND DATA TO N8N
    # =====================================================

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


    except Exception as e:

        print(
            "⚠️ n8n webhook error:",
            e
        )


    # =====================================================
    # RESPONSE TO USER
    # =====================================================

    return {

        "success": True,

        "message":
            "Admission application "
            "submitted successfully",

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
    db: Session = Depends(get_db)
):

    admissions = (

        db.query(Admission)

        .order_by(
            Admission.id.desc()
        )

        .all()
    )

    return admissions


# =========================================================
# ADMIN LOGIN PAGE
# =========================================================

@app.get("/admin")
def admin_login_page(

    request: Request,

    db: Session = Depends(get_db)

):

    ensure_default_admin(db)


    if admin_is_logged_in(
        request
    ):

        return RedirectResponse(

            url="/admin/dashboard",

            status_code=302
        )


    return templates.TemplateResponse(

        request=request,

        name="admin.html",

        context={
            "error": None
        }
    )


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.post("/admin/login")
def admin_login(

    request: Request,

    email: str = Form(...),

    password: str = Form(...),

    db: Session = Depends(get_db)

):

    ensure_default_admin(db)


    admin = (

        db.query(Admin)

        .filter(
            Admin.email ==
            email.strip()
        )

        .first()
    )


    if (
        not admin
        or
        admin.password != password
    ):

        return templates.TemplateResponse(

            request=request,

            name="admin.html",

            context={
                "error":
                    "Invalid email or password"
            },

            status_code=401
        )


    # Create session token
    token = secrets.token_urlsafe(32)

    ADMIN_SESSIONS.add(token)


    response = RedirectResponse(

        url="/admin/dashboard",

        status_code=302
    )


    response.set_cookie(

        key="admin_session",

        value=token,

        httponly=True,

        samesite="lax"
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

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(

            url="/admin",

            status_code=302
        )


    admissions = (

        db.query(Admission)

        .order_by(
            Admission.id.desc()
        )

        .all()
    )


    total = len(
        admissions
    )


    pending = sum(

        1

        for a in admissions

        if a.status == "PENDING"

    )


    approved = sum(

        1

        for a in admissions

        if a.status == "APPROVED"

    )


    rejected = sum(

        1

        for a in admissions

        if a.status == "REJECTED"

    )


    return templates.TemplateResponse(

        request=request,

        name="dashboard.html",

        context={

            "admissions":
                admissions,

            "total":
                total,

            "pending":
                pending,

            "approved":
                approved,

            "rejected":
                rejected
        }
    )


# =========================================================
# APPROVE ADMISSION
# =========================================================

@app.post(
    "/admin/admissions/{admission_id}/approve"
)
def approve_admission(

    admission_id: int,

    request: Request,

    db: Session = Depends(get_db)

):

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(

            url="/admin",

            status_code=302
        )


    admission = (

        db.query(Admission)

        .filter(
            Admission.id ==
            admission_id
        )

        .first()
    )


    if not admission:

        raise HTTPException(

            status_code=404,

            detail=
                "Admission not found"
        )


    admission.status = "APPROVED"

    db.commit()


    return RedirectResponse(

        url="/admin/dashboard",

        status_code=302
    )


# =========================================================
# REJECT ADMISSION
# =========================================================

@app.post(
    "/admin/admissions/{admission_id}/reject"
)
def reject_admission(

    admission_id: int,

    request: Request,

    db: Session = Depends(get_db)

):

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(

            url="/admin",

            status_code=302
        )


    admission = (

        db.query(Admission)

        .filter(
            Admission.id ==
            admission_id
        )

        .first()
    )


    if not admission:

        raise HTTPException(

            status_code=404,

            detail=
                "Admission not found"
        )


    admission.status = "REJECTED"

    db.commit()


    return RedirectResponse(

        url="/admin/dashboard",

        status_code=302
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.get("/admin/logout")
def admin_logout(
    request: Request
):

    token = request.cookies.get(
        "admin_session"
    )


    if token:

        ADMIN_SESSIONS.discard(
            token
        )


    response = RedirectResponse(

        url="/admin",

        status_code=302
    )


    response.delete_cookie(
        "admin_session"
    )


    return response