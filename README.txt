DAHARKI SCHOOL ADMISSION SYSTEM
===============================

1. Open this folder in VS Code.

2. Open Terminal and run:

   python -m venv venv

3. Activate:

   Windows:
   venv\Scripts\activate

4. Install packages:

   pip install -r requirements.txt

5. Run server:

   python -m uvicorn app:app --reload

6. Open:

   Admission Form:
   http://127.0.0.1:8000

   Admin Login:
   http://127.0.0.1:8000/admin

   API Health:
   http://127.0.0.1:8000/health

DEFAULT ADMIN
-------------
Email: admin@daharkischool.edu.pk
Password: admin123

CURRENT FEATURES
----------------
- Student admission form
- SQLite database
- Automatic application number
- Pending status
- Admin login
- Admin dashboard
- Total / Pending / Approved / Rejected statistics
- Search applications
- View full student details
- Approve application
- Reject application
- Logout

NEXT PHASE
----------
SMS notification to admin can be connected after this phase is tested.
