from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import date

app = Flask(__name__)
DB_NAME = "attendance.db"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS faculty (
                    username TEXT PRIMARY KEY,
                    password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    branch TEXT,
                    year INTEGER,
                    section TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    date TEXT,
                    status TEXT,
                    FOREIGN KEY(student_id) REFERENCES students(id))''')
    # Add a default faculty
    c.execute("INSERT OR IGNORE INTO faculty VALUES (?,?)", ('admin','admin123'))
    conn.commit()
    conn.close()

init_db()

# Home page
@app.route('/')
def home():
    return render_template('home.html')

# Faculty login
@app.route('/faculty', methods=['GET', 'POST'])
def faculty_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM faculty WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        conn.close()
        if result:
            return redirect(url_for('faculty_dashboard'))
        else:
            return "Invalid Credentials"
    return render_template('faculty_login.html')

# Faculty dashboard
@app.route('/faculty/dashboard')
def faculty_dashboard():
    return render_template('faculty_dashboard.html')

# Add student
@app.route('/faculty/add_student', methods=['GET','POST'])
def add_student():
    if request.method == 'POST':
        sid = request.form['id']
        name = request.form['name']
        email = request.form['email']
        branch = request.form['branch']
        year = request.form['year']
        section = request.form['section']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO students VALUES (?,?,?,?,?,?)",(sid,name,email,branch,year,section))
        conn.commit()
        conn.close()
        return "Student Added Successfully! <a href='/faculty/dashboard'>Back to Dashboard</a>"
    return render_template('add_student.html')

# View students
@app.route('/faculty/view_students', methods=['GET','POST'])
def view_students():
    students = []
    if request.method == 'POST':
        branch = request.form['branch']
        year = request.form['year']
        section = request.form['section']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE branch=? AND year=? AND section=?",(branch,year,section))
        students = c.fetchall()
        conn.close()
    return render_template('view_students.html', students=students)

# Take attendance
@app.route('/faculty/take_attendance', methods=['POST'])
def take_attendance():
    student_ids = request.form.getlist('student_id')
    statuses = request.form.getlist('status')
    today = date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for sid, status in zip(student_ids, statuses):
        c.execute("INSERT INTO attendance (student_id,date,status) VALUES (?,?,?)",(sid,today,status))
    conn.commit()
    conn.close()
    return "Attendance Saved! <a href='/faculty/dashboard'>Back to Dashboard</a>"

# Student login
@app.route('/student', methods=['GET','POST'])
def student_login():
    if request.method == 'POST':
        sid = request.form['id']
        password = request.form['password']
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM students WHERE id=? AND name=?", (sid, password))
        student = c.fetchone()
        conn.close()
        if student:
            return redirect(url_for('student_dashboard', student_id=sid))
        else:
            return "Invalid Credentials"
    return render_template('student_login.html')

# Student dashboard
@app.route('/student/dashboard/<student_id>')
def student_dashboard(student_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE id=?",(student_id,))
    student = c.fetchone()
    c.execute("SELECT date,status FROM attendance WHERE student_id=?",(student_id,))
    attendance = c.fetchall()
    conn.close()

    return render_template('student_dashboard.html', student=student, attendance=attendance)
@app.route('/faculty/monthly/<int:month>', methods=['POST'])
def faculty_month_result(month):
    student_id = request.form['student_id']

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT date, status
        FROM attendance
        WHERE student_id = ?
        AND strftime('%m', date) = ?
    """, (student_id, f"{month:02d}"))

    records = c.fetchall()

    total = len(records)
    present = sum(1 for r in records if r[1] == 'P')
    percentage = (present / total * 100) if total > 0 else 0

    conn.close()

    return render_template(
        'faculty_month_result.html',
        records=records,
        month=month,
        total=total,
        present=present,
        percentage=percentage
    )
@app.route('/student/monthly/<student_id>/<int:month>')
def student_monthly(student_id, month):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT date, status
        FROM attendance
        WHERE student_id = ?
        AND strftime('%m', date) = ?
    """, (student_id, f"{month:02d}"))

    records = c.fetchall()

    total = len(records)
    present = sum(1 for r in records if r[1] == 'P')
    percentage = (present / total * 100) if total > 0 else 0

    conn.close()

    return render_template(
        'student_monthly.html',
        records=records,
        month=month,
        total=total,
        present=present,
        percentage=percentage
    )

    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
