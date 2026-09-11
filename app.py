```python
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from config import Config, mysql
import os
import resend

app = Flask(__name__)

# =========================================================
# LOAD CONFIGURATION
# =========================================================

app.config.from_object(Config)

app.secret_key = "smart_classroom_attendance_secret_2026"


# =========================================================
# INITIALIZE MYSQL
# =========================================================

mysql.init_app(app)


# =========================================================
# EMAIL CONFIGURATION
# =========================================================
# Resend is used for email notification.
# RESEND_API_KEY is stored in Render Environment Variables.

resend.api_key = os.environ.get("RESEND_API_KEY")


# Flask-Mail configuration is kept because Flask-Mail
# is already present in the project requirements.

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False

app.config["MAIL_USERNAME"] = Config.MAIL_USERNAME
app.config["MAIL_PASSWORD"] = Config.MAIL_PASSWORD
app.config["MAIL_DEFAULT_SENDER"] = Config.MAIL_DEFAULT_SENDER

mail = Mail(app)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        cur = mysql.connection.cursor()

        cur.execute(
            """
            SELECT *
            FROM admin
            WHERE username = %s
            AND password = %s
            """,
            (username, password)
        )

        admin = cur.fetchone()

        cur.close()

        if admin:

            session["admin_logged_in"] = True

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid Username or Password"
        )

    return render_template("login.html")


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route("/student_login", methods=["GET", "POST"])
def student_login():

    if request.method == "POST":

        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if not roll_number or not password:

            return render_template(
                "student_login.html",
                error="Please enter Roll Number and Password"
            )

        cur = mysql.connection.cursor()

        cur.execute(
            """
            SELECT
                id,
                name,
                roll_number,
                email,
                phone
            FROM students
            WHERE roll_number = %s
            AND password = %s
            """,
            (
                roll_number,
                password
            )
        )

        student = cur.fetchone()

        cur.close()

        if student:

            session["student_id"] = student[0]

            return redirect(
                url_for("student_dashboard")
            )

        return render_template(
            "student_login.html",
            error="Invalid Roll Number or Password"
        )

    return render_template(
        "student_login.html"
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route("/student_logout")
def student_logout():

    session.pop(
        "student_id",
        None
    )

    return redirect(
        url_for("student_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM students
            """
        )

        total_students = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE attendance_date = CURDATE()
            AND status = 'Present'
            """
        )

        present_today = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*)
            FROM attendance
            WHERE attendance_date = CURDATE()
            AND status = 'Absent'
            """
        )

        absent_today = cur.fetchone()[0]

        cur.execute(
            """
            SELECT
                COALESCE(
                    (
                        SUM(
                            CASE
                                WHEN status = 'Present'
                                THEN 1
                                ELSE 0
                            END
                        )
                        / NULLIF(COUNT(*), 0)
                    ) * 100,
                    0
                )
            FROM attendance
            """
        )

        average_attendance = cur.fetchone()[0]

        if average_attendance is None:
            average_attendance = 0

        average_attendance = round(
            float(average_attendance),
            1
        )

    finally:

        cur.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        present_today=present_today,
        absent_today=absent_today,
        average_attendance=average_attendance
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student_dashboard")
def student_dashboard():

    student_id = session.get("student_id")

    if not student_id:

        return redirect(
            url_for("student_login")
        )

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT
            id,
            name,
            roll_number,
            email,
            phone
        FROM students
        WHERE id = %s
        """,
        (student_id,)
    )

    student = cur.fetchone()

    if student is None:

        cur.close()

        session.pop(
            "student_id",
            None
        )

        return redirect(
            url_for("student_login")
        )

    cur.execute(
        """
        SELECT
            COUNT(id),

            COALESCE(
                SUM(
                    CASE
                        WHEN status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN status = 'Absent'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            )

        FROM attendance

        WHERE student_id = %s
        """,
        (student_id,)
    )

    attendance_data = cur.fetchone()

    cur.execute(
        """
        SELECT
            attendance_date,
            status
        FROM attendance
        WHERE student_id = %s
        ORDER BY attendance_date DESC
        """,
        (student_id,)
    )

    attendance_records = cur.fetchall()

    cur.close()

    total_days = attendance_data[0] or 0
    present_days = attendance_data[1] or 0
    absent_days = attendance_data[2] or 0

    if total_days > 0:

        percentage = round(
            (present_days / total_days) * 100,
            1
        )

    else:

        percentage = 0

    return render_template(
        "student_dashboard.html",

        student=student,

        total_days=total_days,

        present_days=present_days,

        absent_days=absent_days,

        percentage=percentage,

        attendance_records=attendance_records
    )


# =========================================================
# STUDENT PROFILE
# =========================================================

@app.route("/student_profile")
def student_profile():

    student_id = session.get("student_id")

    if not student_id:

        return redirect(
            url_for("student_login")
        )

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT
            id,
            name,
            roll_number,
            email,
            phone
        FROM students
        WHERE id = %s
        """,
        (student_id,)
    )

    student = cur.fetchone()

    cur.close()

    if student is None:

        session.pop(
            "student_id",
            None
        )

        return redirect(
            url_for("student_login")
        )

    return render_template(
        "student_profile.html",
        student=student
    )


# =========================================================
# ADD STUDENT
# =========================================================

@app.route("/add_student", methods=["GET", "POST"])
def add_student():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        if not name or not roll_number or not password:

            return """
            <h3>
                Student Name, Roll Number and Password are required.
            </h3>

            <a href="/add_student">
                Go Back
            </a>
            """

        cur = mysql.connection.cursor()

        try:

            cur.execute(
                """
                INSERT INTO students
                (
                    name,
                    roll_number,
                    email,
                    phone,
                    password
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    roll_number,
                    email,
                    phone,
                    password
                )
            )

            mysql.connection.commit()

        except Exception as e:

            mysql.connection.rollback()

            cur.close()

            return f"""
            <h3>
                Student Could Not Be Added
            </h3>

            <pre>{e}</pre>

            <a href="/add_student">
                Go Back
            </a>
            """

        cur.close()

        return redirect(
            url_for("view_students")
        )

    return render_template(
        "add_student.html"
    )


# =========================================================
# VIEW STUDENTS
# =========================================================

@app.route("/view_students", methods=["GET", "POST"])
def view_students():

    cur = mysql.connection.cursor()

    keyword = request.form.get(
        "search",
        ""
    ).strip()

    if keyword:

        search_value = f"%{keyword}%"

        cur.execute(
            """
            SELECT
                id,
                name,
                roll_number,
                email,
                phone
            FROM students
            WHERE name LIKE %s
               OR roll_number LIKE %s
               OR email LIKE %s
            ORDER BY id
            """,
            (
                search_value,
                search_value,
                search_value
            )
        )

    else:

        cur.execute(
            """
            SELECT
                id,
                name,
                roll_number,
                email,
                phone
            FROM students
            ORDER BY id
            """
        )

    students = cur.fetchall()

    cur.close()

    return render_template(
        "view_students.html",
        students=students
    )


# =========================================================
# EDIT STUDENT
# =========================================================

@app.route(
    "/edit_student/<int:id>",
    methods=["GET", "POST"]
)
def edit_student(id):

    cur = mysql.connection.cursor()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        if not name or not roll_number:

            cur.close()

            return """
            <h3>
                Student Name and Roll Number are required.
            </h3>

            <a href="/view_students">
                Back to Students
            </a>
            """

        try:

            cur.execute(
                """
                UPDATE students

                SET
                    name = %s,
                    roll_number = %s,
                    email = %s,
                    phone = %s

                WHERE id = %s
                """,
                (
                    name,
                    roll_number,
                    email,
                    phone,
                    id
                )
            )

            mysql.connection.commit()

        except Exception as e:

            mysql.connection.rollback()

            cur.close()

            return f"""
            <h3>
                Student Could Not Be Updated
            </h3>

            <pre>{e}</pre>

            <a href="/view_students">
                Back to Students
            </a>
            """

        cur.close()

        return redirect(
            url_for("view_students")
        )

    cur.execute(
        """
        SELECT
            id,
            name,
            roll_number,
            email,
            phone
        FROM students
        WHERE id = %s
        """,
        (id,)
    )

    student = cur.fetchone()

    cur.close()

    if student is None:

        return """
        <h3>
            Student Not Found
        </h3>

        <a href="/view_students">
            Back to Students
        </a>
        """

    return render_template(
        "edit_student.html",
        student=student
    )


# =========================================================
# DELETE STUDENT
# =========================================================

@app.route("/delete_student/<int:id>")
def delete_student(id):

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            DELETE FROM students
            WHERE id = %s
            """,
            (id,)
        )

        mysql.connection.commit()

    except Exception as e:

        mysql.connection.rollback()

        cur.close()

        return f"""
        <h3>
            Student Could Not Be Deleted
        </h3>

        <pre>{e}</pre>

        <a href="/view_students">
            Back to Students
        </a>
        """

    cur.close()

    return redirect(
        url_for("view_students")
    )


# =========================================================
# ATTENDANCE
# =========================================================

@app.route(
    "/attendance",
    methods=["GET", "POST"]
)
def attendance():

    cur = mysql.connection.cursor()

    if request.method == "POST":

        attendance_date = request.form.get(
            "attendance_date",
            ""
        ).strip()

        if not attendance_date:

            cur.close()

            return """
            <h3>
                Please select an attendance date.
            </h3>

            <a href="/attendance">
                Go Back
            </a>
            """

        cur.execute(
            """
            SELECT
                id,
                name,
                roll_number
            FROM students
            ORDER BY id
            """
        )

        student_list = cur.fetchall()

        for student in student_list:

            student_id = student[0]

            status = request.form.get(
                f"status_{student_id}"
            )

            if status not in [
                "Present",
                "Absent"
            ]:

                cur.close()

                return f"""
                <h3>
                    Please mark attendance for every student.
                </h3>

                <p>
                    Attendance is missing for:
                    <strong>{student[1]}</strong>
                </p>

                <a href="/attendance">
                    Go Back
                </a>
                """

        try:

            for student in student_list:

                student_id = student[0]

                status = request.form.get(
                    f"status_{student_id}"
                )

                cur.execute(
                    """
                    INSERT INTO attendance
                    (
                        student_id,
                        attendance_date,
                        status
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s
                    )

                    ON DUPLICATE KEY UPDATE

                    status = VALUES(status)
                    """,
                    (
                        student_id,
                        attendance_date,
                        status
                    )
                )

            mysql.connection.commit()

        except Exception as e:

            mysql.connection.rollback()

            cur.close()

            return f"""
            <h3>
                Attendance Could Not Be Saved
            </h3>

            <pre>{e}</pre>

            <a href="/attendance">
                Go Back
            </a>
            """

        cur.close()

        return redirect(
            url_for("attendance_history")
        )

    cur.execute(
        """
        SELECT
            id,
            name,
            roll_number,
            email,
            phone
        FROM students
        ORDER BY id
        """
    )

    students = cur.fetchall()

    cur.close()

    return render_template(
        "attendance.html",
        students=students
    )


# =========================================================
# ATTENDANCE HISTORY
# =========================================================

@app.route("/attendance_history")
def attendance_history():

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT

            attendance.id,

            students.name,

            students.roll_number,

            attendance.attendance_date,

            attendance.status

        FROM attendance

        INNER JOIN students

        ON attendance.student_id = students.id

        ORDER BY

            attendance.attendance_date DESC,

            attendance.id DESC
        """
    )

    records = cur.fetchall()

    cur.close()

    return render_template(
        "attendance_history.html",
        records=records
    )


# =========================================================
# ATTENDANCE PERCENTAGE
# =========================================================

@app.route("/attendance_percentage")
def attendance_percentage():

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT

            students.id,

            students.name,

            students.roll_number,

            COUNT(attendance.id)
            AS total_days,

            COALESCE(
                SUM(
                    CASE
                        WHEN attendance.status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS present_days

        FROM students

        LEFT JOIN attendance

        ON students.id = attendance.student_id

        GROUP BY

            students.id,
            students.name,
            students.roll_number

        ORDER BY students.id
        """
    )

    data = cur.fetchall()

    cur.close()

    return render_template(
        "attendance_percentage.html",
        students=data
    )


# =========================================================
# ATTENDANCE ALERTS
# =========================================================

@app.route("/attendance_alerts")
def attendance_alerts():

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT

            attendance.id,

            students.name,

            students.roll_number,

            students.phone,

            students.email,

            attendance.attendance_date,

            attendance.status

        FROM attendance

        INNER JOIN students

        ON attendance.student_id = students.id

        WHERE attendance.status = 'Absent'

        ORDER BY

            attendance.attendance_date DESC,

            attendance.id DESC
        """
    )

    alerts = cur.fetchall()

    cur.close()

    return render_template(
        "attendance_alerts.html",
        alerts=alerts
    )


# =========================================================
# REAL EMAIL NOTIFICATION - RESEND
# =========================================================

@app.route("/send_email/<int:attendance_id>")
def send_email(attendance_id):

    cur = mysql.connection.cursor()

    # -----------------------------------------------------
    # GET ABSENT STUDENT + EMAIL
    # -----------------------------------------------------

    cur.execute(
        """
        SELECT

            students.name,

            students.email,

            attendance.attendance_date,

            attendance.status

        FROM attendance

        INNER JOIN students

        ON attendance.student_id = students.id

        WHERE attendance.id = %s
        """,
        (attendance_id,)
    )

    record = cur.fetchone()

    cur.close()

    # -----------------------------------------------------
    # RECORD NOT FOUND
    # -----------------------------------------------------

    if record is None:

        return """
        <h3>
            Attendance record not found.
        </h3>

        <a href="/attendance_alerts">
            Back to Attendance Alerts
        </a>
        """

    student_name = record[0]
    parent_email = record[1]
    attendance_date = record[2]
    status = record[3]

    # -----------------------------------------------------
    # ONLY ABSENT STUDENTS
    # -----------------------------------------------------

    if status != "Absent":

        return """
        <h3>
            Email notification is only available
            for absent students.
        </h3>

        <a href="/attendance_alerts">
            Back to Attendance Alerts
        </a>
        """

    # -----------------------------------------------------
    # CHECK EMAIL
    # -----------------------------------------------------

    if not parent_email:

        return """
        <h3>
            Parent email address is not available
            for this student.
        </h3>

        <a href="/attendance_alerts">
            Back to Attendance Alerts
        </a>
        """

    # -----------------------------------------------------
    # CHECK RESEND API KEY
    # -----------------------------------------------------

    if not resend.api_key:

        return """
        <h3 style="color:red;">
            Resend API Key is not configured.
        </h3>

        <p>
            Please add RESEND_API_KEY in Render Environment Variables.
        </p>

        <a href="/attendance_alerts">
            Back to Attendance Alerts
        </a>
        """

    # -----------------------------------------------------
    # EMAIL SUBJECT
    # -----------------------------------------------------

    subject = "Attendance Alert - Smart Classroom Attendance System"

    # -----------------------------------------------------
    # EMAIL MESSAGE
    # -----------------------------------------------------

    message = f"""
Dear Parent/Guardian,

This is an attendance notification from the
Anjuman Islam Janjira Degree College Of Science.

Student Name: {student_name}

Attendance Date: {attendance_date}

Status: Absent

Your child was marked absent on the above date.

Please take note of the attendance record.

Regards,
Anjuman Islam Janjira Degree College Of Science
"""

    # -----------------------------------------------------
    # SEND EMAIL USING RESEND
    # -----------------------------------------------------

    try:

        params = {
            "from": "Smart Classroom Attendance <onboarding@resend.dev>",
            "to": [parent_email],
            "subject": subject,
            "text": message
        }

        resend.Emails.send(params)

    except Exception as e:

        return f"""
        <h3 style="color:red;">
            Email Could Not Be Sent
        </h3>

        <p>
            Resend email service returned an error.
        </p>

        <pre>{e}</pre>

        <a href="/attendance_alerts">
            Back to Attendance Alerts
        </a>
        """

    # -----------------------------------------------------
    # SUCCESS PAGE
    # -----------------------------------------------------

    return render_template(
        "email_success.html",

        student_name=student_name,

        parent_email=parent_email,

        attendance_date=attendance_date,

        message=message
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
def reports():

    cur = mysql.connection.cursor()

    # TOTAL STUDENTS

    cur.execute(
        """
        SELECT COUNT(*)
        FROM students
        """
    )

    total_students = cur.fetchone()[0]

    # TOTAL PRESENT

    cur.execute(
        """
        SELECT COUNT(*)
        FROM attendance
        WHERE status = 'Present'
        """
    )

    total_present = cur.fetchone()[0]

    # TOTAL ABSENT

    cur.execute(
        """
        SELECT COUNT(*)
        FROM attendance
        WHERE status = 'Absent'
        """
    )

    total_absent = cur.fetchone()[0]

    # OVERALL PERCENTAGE

    total_records = (
        total_present +
        total_absent
    )

    if total_records > 0:

        overall_percentage = round(
            (
                total_present /
                total_records
            ) * 100,
            1
        )

    else:

        overall_percentage = 0

    # STUDENT REPORT

    cur.execute(
        """
        SELECT

            students.id,

            students.name,

            students.roll_number,

            COUNT(attendance.id)
            AS total_days,

            COALESCE(
                SUM(
                    CASE
                        WHEN attendance.status = 'Present'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS present_days,

            COALESCE(
                SUM(
                    CASE
                        WHEN attendance.status = 'Absent'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS absent_days

        FROM students

        LEFT JOIN attendance

        ON students.id = attendance.student_id

        GROUP BY

            students.id,

            students.name,

            students.roll_number

        ORDER BY students.id
        """
    )

    student_reports = cur.fetchall()

    cur.close()

    return render_template(
        "reports.html",

        total_students=total_students,

        total_present=total_present,

        total_absent=total_absent,

        overall_percentage=overall_percentage,

        student_reports=student_reports
    )


# =========================================================
# DATABASE CONNECTION TEST
# =========================================================

@app.route("/test_db")
def test_db():

    try:

        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT DATABASE();"
        )

        db = cur.fetchone()

        cur.close()

        return f"""
        <h2 style="color:green;">
            Connected Successfully!
        </h2>

        <h3>
            Current Database:
            {db[0]}
        </h3>
        """

    except Exception as e:

        return f"""
        <h2 style="color:red;">
            Database Connection Failed!
        </h2>

        <pre>{e}</pre>
        """


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
```
