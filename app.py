from datetime import datetime
from io import BytesIO

import os
import secrets
import requests

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    Request,
    Depends,
    HTTPException,
    Form
)

from fastapi.responses import (
    RedirectResponse,
    StreamingResponse
)

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session
from sqlalchemy import text

from pydantic import BaseModel

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

from database import engine, get_db
from models import Base, Admission, Admin


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    ""
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
# FOLDERS
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
# DATABASE
# =========================================================

Base.metadata.create_all(
    bind=engine
)


# =========================================================
# ADD NEW COLUMNS SAFELY
# =========================================================

def update_database_schema():

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                ALTER TABLE admissions
                ADD COLUMN IF NOT EXISTS grade VARCHAR
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE admissions
                ADD COLUMN IF NOT EXISTS certificate_status VARCHAR
                DEFAULT 'NOT_GENERATED'
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE admissions
                ADD COLUMN IF NOT EXISTS student_cnic VARCHAR
                """
            )
        )


update_database_schema()


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="Daharki School Admission System",
    version="2.0.0"
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
# ADMIN SESSIONS
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
    student_cnic: str | None = None

    phone: str

    whatsapp: str | None = None
    email: str | None = None

    address: str | None = None


# =========================================================
# CREATE / UPDATE DEFAULT ADMIN
# =========================================================

def ensure_default_admin(
    db: Session
):

    admin = (
        db.query(Admin)
        .filter(
            Admin.email == ADMIN_EMAIL
        )
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

        print(
            "✅ Default admin created"
        )

    else:

        admin.password = ADMIN_PASSWORD

        db.commit()

        print(
            "✅ Default admin already exists"
        )


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
def startup_event():

    db = next(
        get_db()
    )

    try:

        ensure_default_admin(
            db
        )

    finally:

        db.close()


# =========================================================
# ADMIN AUTH CHECK
# =========================================================

def admin_is_logged_in(
    request: Request
):

    token = request.cookies.get(
        "admin_session"
    )

    return bool(
        token
        and token in ADMIN_SESSIONS
    )


# =========================================================
# HOME
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

@app.post(
    "/api/admissions"
)
def create_admission(

    admission_data: AdmissionCreate,

    db: Session = Depends(
        get_db
    )
):

    # -----------------------------------------
    # LAST APPLICATION
    # -----------------------------------------

    last = (
        db.query(Admission)
        .order_by(
            Admission.id.desc()
        )
        .first()
    )


    next_number = (
        last.id + 1
        if last
        else 1
    )


    # -----------------------------------------
    # APPLICATION NUMBER
    # -----------------------------------------

    application_no = (

        f"DSS-ADM-"
        f"{datetime.now().year}-"
        f"{next_number:04d}"
    )


    # -----------------------------------------
    # DATABASE RECORD
    # -----------------------------------------

    admission = Admission(

        application_no=
            application_no,

        student_name=
            admission_data.student_name.strip(),

        father_name=
            admission_data.father_name.strip(),

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

        status="PENDING",

        grade="",

        certificate_status=
            "NOT_GENERATED"
    )


    db.add(
        admission
    )

    db.commit()

    db.refresh(
        admission
    )


    # =====================================================
    # N8N NOTIFICATION
    # =====================================================

    webhook_sent = False

    if N8N_WEBHOOK_URL:

        try:

            response = requests.post(

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

            webhook_sent = (
                response.ok
            )

        except Exception as error:

            print(
                "⚠️ n8n error:",
                error
            )


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
# ADMIN LOGIN PAGE
# =========================================================

@app.get(
    "/admin/login"
)
def admin_login_page(
    request: Request
):

    if admin_is_logged_in(
        request
    ):

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

@app.post(
    "/api/admin/login"
)
def admin_login(

    request: Request,

    email: str = Form(...),

    password: str = Form(...),

    db: Session = Depends(
        get_db
    )
):

    admin = (
        db.query(Admin)
        .filter(
            Admin.email
            == email.strip()
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
            name="admin_login.html",
            context={
                "error":
                    "Invalid email or password"
            },
            status_code=401
        )


    token = secrets.token_hex(
        32
    )

    ADMIN_SESSIONS.add(
        token
    )


    response = RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )


    response.set_cookie(

        key="admin_session",

        value=token,

        httponly=True,

        secure=True,

        samesite="lax",

        max_age=3600
    )


    return response


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.get(
    "/admin/dashboard"
)
def admin_dashboard(

    request: Request,

    db: Session = Depends(
        get_db
    )
):

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )


    admissions = (

        db.query(Admission)

        .order_by(
            Admission.id.desc()
        )

        .all()
    )


    return templates.TemplateResponse(

        request=request,

        name="admin_dashboard.html",

        context={
            "admissions":
                admissions
        }
    )


# =========================================================
# UPDATE STATUS
# =========================================================

@app.post(
    "/admin/admissions/{application_no}/status"
)
def update_status(

    application_no: str,

    request: Request,

    new_status: str = Form(...),

    db: Session = Depends(
        get_db
    )
):

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )


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
                "Application not found"
        )


    new_status = (
        new_status
        .strip()
        .upper()
    )


    allowed = [
        "PENDING",
        "APPROVED",
        "REJECTED"
    ]


    if new_status not in allowed:

        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )


    admission.status = (
        new_status
    )


    db.commit()


    return RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )


# =========================================================
# SAVE / UPDATE GRADE
# =========================================================

@app.post(
    "/admin/admissions/{application_no}/grade"
)
def save_grade(

    application_no: str,

    request: Request,

    grade: str = Form(...),

    db: Session = Depends(
        get_db
    )
):

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )


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
                "Application not found"
        )


    admission.grade = (
        grade.strip().upper()
    )


    db.commit()


    return RedirectResponse(
        url="/admin/dashboard",
        status_code=303
    )


# =========================================================
# CERTIFICATE GENERATOR
# =========================================================

@app.get(
    "/admin/certificate/{application_no}"
)
def generate_certificate(

    application_no: str,

    request: Request,

    db: Session = Depends(
        get_db
    )
):

    # -----------------------------------------
    # ADMIN SECURITY
    # -----------------------------------------

    if not admin_is_logged_in(
        request
    ):

        return RedirectResponse(
            url="/admin/login",
            status_code=303
        )


    # -----------------------------------------
    # FIND STUDENT
    # -----------------------------------------

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
                "Application not found"
        )


    # -----------------------------------------
    # ONLY APPROVED STUDENTS
    # -----------------------------------------

    if admission.status != "APPROVED":

        raise HTTPException(
            status_code=400,
            detail=
                "Certificate can only be generated for approved students"
        )


    # -----------------------------------------
    # PDF MEMORY BUFFER
    # -----------------------------------------

    buffer = BytesIO()


    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )


    width, height = A4


    # -----------------------------------------
    # CERTIFICATE BORDER
    # -----------------------------------------

    pdf.setLineWidth(4)

    pdf.rect(
        40,
        40,
        width - 80,
        height - 80
    )


    pdf.setLineWidth(1)

    pdf.rect(
        50,
        50,
        width - 100,
        height - 100
    )


    # -----------------------------------------
    # HEADER
    # -----------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        26
    )

    pdf.drawCentredString(
        width / 2,
        height - 120,
        "DAHARKI SCHOOL SYSTEM"
    )


    pdf.setFont(
        "Helvetica-Bold",
        22
    )

    pdf.drawCentredString(
        width / 2,
        height - 175,
        "CERTIFICATE OF ACHIEVEMENT"
    )


    # -----------------------------------------
    # CERTIFICATE BODY
    # -----------------------------------------

    pdf.setFont(
        "Helvetica",
        14
    )

    pdf.drawCentredString(
        width / 2,
        height - 235,
        "This certificate is proudly presented to"
    )


    pdf.setFont(
        "Helvetica-Bold",
        24
    )

    pdf.drawCentredString(
        width / 2,
        height - 290,
        admission.student_name
    )


    pdf.setFont(
        "Helvetica",
        14
    )

    pdf.drawCentredString(
        width / 2,
        height - 340,
        f"Father Name: {admission.father_name}"
    )


    pdf.drawCentredString(
        width / 2,
        height - 375,
        f"Class: {admission.applying_class}"
    )


    grade = (
        admission.grade
        if admission.grade
        else "Not Assigned"
    )


    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawCentredString(
        width / 2,
        height - 430,
        f"Grade: {grade}"
    )


    pdf.setFont(
        "Helvetica",
        12
    )

    pdf.drawCentredString(
        width / 2,
        height - 480,
        f"Application No: {admission.application_no}"
    )


    pdf.drawCentredString(
        width / 2,
        height - 510,
        f"Issue Date: {datetime.now().strftime('%d-%m-%Y')}"
    )


    # -----------------------------------------
    # SIGNATURE
    # -----------------------------------------

    pdf.line(
        width - 200,
        170,
        width - 80,
        170
    )


    pdf.drawCentredString(
        width - 140,
        150,
        "Principal Signature"
    )


    pdf.drawCentredString(
        140,
        150,
        "Daharki School System"
    )


    # -----------------------------------------
    # COMPLETE PDF
    # -----------------------------------------

    pdf.showPage()

    pdf.save()


    buffer.seek(0)


    # -----------------------------------------
    # UPDATE CERTIFICATE STATUS
    # -----------------------------------------

    admission.certificate_status = (
        "GENERATED"
    )

    db.commit()


    filename = (
        f"{admission.application_no}"
        f"_certificate.pdf"
    )


    return StreamingResponse(

        buffer,

        media_type=
            "application/pdf",

        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        }
    )


# =========================================================
# LOGOUT
# =========================================================

@app.get(
    "/api/admin/logout"
)
def logout(
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
        url="/admin/login",
        status_code=303
    )


    response.delete_cookie(
        "admin_session"
    )


    return response