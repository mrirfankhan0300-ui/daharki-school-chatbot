from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime

from database import Base


# =========================================================
# ADMISSION MODEL
# =========================================================

class Admission(Base):
    __tablename__ = "admissions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    application_no = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    # Student Information
    student_name = Column(
        String,
        nullable=False
    )

    father_name = Column(
        String,
        nullable=False
    )

    mother_name = Column(
        String,
        nullable=True
    )

    date_of_birth = Column(
        String,
        nullable=True
    )

    gender = Column(
        String,
        nullable=True
    )

    applying_class = Column(
        String,
        nullable=False
    )

    previous_school = Column(
        String,
        nullable=True
    )

    # CNIC / B-Form Information
    parent_cnic = Column(
        String,
        nullable=True
    )

    student_cnic = Column(
        String,
        nullable=True
    )

    # Contact Information
    phone = Column(
        String,
        nullable=False
    )

    whatsapp = Column(
        String,
        nullable=True
    )

    email = Column(
        String,
        nullable=True
    )

    address = Column(
        String,
        nullable=True
    )

    # Admission Status
    status = Column(
        String,
        default="PENDING"
    )

    # Record Creation Time
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# ADMIN MODEL
# =========================================================

class Admin(Base):
    __tablename__ = "admins"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String,
        nullable=False
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    password = Column(
        String,
        nullable=False
    )