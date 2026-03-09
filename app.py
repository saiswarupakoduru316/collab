from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = "secret_key"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

DATABASE = "database.db"

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/login")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        conn.execute("INSERT INTO users (username,email,password) VALUES (?,?,?)",
                     (username, email, password))
        conn.commit()
        conn.close()

        flash("Registered Successfully")
        return redirect("/login")

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?",
                            (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")
        else:
            flash("Invalid Credentials")

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    connection_count = conn.execute("""
        SELECT COUNT(DISTINCT 
            CASE 
                WHEN sender_id < receiver_id 
                THEN sender_id || '-' || receiver_id
                ELSE receiver_id || '-' || sender_id
            END
        ) as total
        FROM join_requests
        WHERE sender_id=? OR receiver_id=?
    """, (session["user_id"], session["user_id"])).fetchone()["total"]

    conn.close()

    return render_template("dashboard.html",
                           connection_count=connection_count)
# ---------------- ADD PROJECT ----------------
@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form.get("title")
        tech_stack = request.form.get("tech_stack")
        team_members = request.form.get("team_members")
        status = request.form.get("status")

        file = request.files.get("document")
        filename = None

        if file and file.filename != "":
            filename = secure_filename(file.filename)

            # Make filename unique
            import time
            filename = str(int(time.time())) + "_" + filename

            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = get_db()
        conn.execute("""
            INSERT INTO projects 
            (user_id, title, tech_stack, team_members, document, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            title,
            tech_stack,
            team_members,
            filename,
            status
        ))
        conn.commit()
        conn.close()

        flash("Project Added Successfully")
        return redirect("/my_projects")

    return render_template("add_project.html")

# ---------------- MY PROJECTS ----------------
@app.route("/my_projects")
def my_projects():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    projects = conn.execute("SELECT * FROM projects WHERE user_id=?",
                            (session["user_id"],)).fetchall()
    conn.close()

    return render_template("my_projects.html", projects=projects)

# ---------------- VIEW ALL PROJECTS ----------------
@app.route("/view_projects")
def view_projects():
    if "user_id" not in session:
        return redirect("/login")

    status_filter = request.args.get("status")

    conn = get_db()

    if status_filter and status_filter != "All":
        projects = conn.execute("""
            SELECT projects.*, users.username 
            FROM projects
            JOIN users ON projects.user_id = users.id
            WHERE projects.status = ?
            ORDER BY created_at DESC
        """, (status_filter,)).fetchall()
    else:
        projects = conn.execute("""
            SELECT projects.*, users.username 
            FROM projects
            JOIN users ON projects.user_id = users.id
            ORDER BY created_at DESC
        """).fetchall()

    conn.close()

    return render_template("view_projects.html",
                           projects=projects,
                           selected_status=status_filter)
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route("/send_request/<int:project_id>")
def send_request(project_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    project = conn.execute(
        "SELECT * FROM projects WHERE id=?",
        (project_id,)
    ).fetchone()

    if not project:
        flash("Project not found")
        return redirect("/view_projects")

    # prevent duplicate request
    existing = conn.execute("""
        SELECT * FROM join_requests 
        WHERE project_id=? AND sender_id=?
    """, (project_id, session["user_id"])).fetchone()

    if existing:
        flash("You already sent request")
        return redirect("/view_projects")

    conn.execute("""
        INSERT INTO join_requests (project_id, sender_id, receiver_id)
        VALUES (?,?,?)
    """, (project_id, session["user_id"], project["user_id"]))

    conn.commit()
    conn.close()

    flash("Request Sent Successfully!")
    return redirect("/view_projects")
@app.route("/received_requests")
def received_requests():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    requests = conn.execute("""
        SELECT join_requests.*, users.username, projects.title
        FROM join_requests
        JOIN users ON join_requests.sender_id = users.id
        JOIN projects ON join_requests.project_id = projects.id
        WHERE receiver_id=?
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("received_requests.html", requests=requests)
@app.route("/update_request/<int:req_id>/<action>")
def update_request(req_id, action):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if action == "accept":
        status = "Accepted"
    elif action == "reject":
        status = "Rejected"
    else:
        return redirect("/received_requests")

    conn.execute("""
        UPDATE join_requests 
        SET status=? 
        WHERE id=? AND receiver_id=?
    """, (status, req_id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("Request Updated")
    return redirect("/received_requests")
@app.route("/sent_requests")
def sent_requests():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    requests = conn.execute("""
        SELECT join_requests.*, projects.title, users.username
        FROM join_requests
        JOIN projects ON join_requests.project_id = projects.id
        JOIN users ON join_requests.receiver_id = users.id
        WHERE sender_id=?
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("sent_requests.html", requests=requests)
@app.route("/connections")
def connections():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    connections = conn.execute("""
        SELECT DISTINCT users.username
        FROM join_requests
        JOIN users
        ON users.id =
            CASE
                WHEN join_requests.sender_id = ?
                THEN join_requests.receiver_id
                ELSE join_requests.sender_id
            END
        WHERE join_requests.sender_id=? OR join_requests.receiver_id=?
    """, (session["user_id"], session["user_id"], session["user_id"])).fetchall()

    conn.close()

    return render_template("connections.html",
                           connections=connections)
@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        group_name = request.form['group_name']
        description = request.form['description']
        owner_id = session['user_id']

        conn = get_db()
        cursor = conn.cursor()

        # Insert into groups table
        cursor.execute("""
            INSERT INTO groups (group_name, description, owner_id)
            VALUES (?, ?, ?)
        """, (group_name, description, owner_id))

        # Get created group id
        group_id = cursor.lastrowid

        # Add owner automatically as joined
        cursor.execute("""
            INSERT INTO group_members (group_id, user_id, status, joined_at)
            VALUES (?, ?, 'Joined', CURRENT_TIMESTAMP)
        """, (group_id, owner_id))

        conn.commit()
        conn.close()

        return redirect(url_for('show_invite_page', group_id=group_id))

    return render_template('create_group.html')
@app.route('/my_groups')
def my_groups():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    groups = conn.execute("""
        SELECT g.*
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id=? AND gm.status='Joined'
    """, (user_id,)).fetchall()

    conn.close()
    return render_template('my_groups.html', groups=groups)
@app.route('/invite_members/<int:group_id>', methods=['POST'])
def invite_members(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    selected_members = request.form.getlist('members')

    conn = get_db()
    cursor = conn.cursor()

    for member_id in selected_members:
        cursor.execute("""
            INSERT INTO group_members (group_id, user_id, status)
            VALUES (?, ?, 'Pending')
        """, (group_id, member_id))

    conn.commit()
    conn.close()

    return redirect(url_for('my_groups'))
@app.route('/invitations')
def invitations():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    invites = conn.execute("""
        SELECT g.id, g.group_name, u.username AS owner_name
        FROM group_members gm
        JOIN groups g ON gm.group_id = g.id
        JOIN users u ON g.owner_id = u.id
        WHERE gm.user_id=? AND gm.status='Pending'
    """, (user_id,)).fetchall()

    conn.close()
    return render_template("invitations.html", invites=invites)
@app.route('/join_group/<int:group_id>')
def join_group(group_id):
    user_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE group_members
        SET status='Joined', joined_at=CURRENT_TIMESTAMP
        WHERE group_id=? AND user_id=?
    """, (group_id, user_id))

    conn.commit()
    conn.close()

    return redirect(url_for('my_groups'))
@app.route('/invite_page/<int:group_id>')
def show_invite_page(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    owner_id = session['user_id']

    conn = get_db()
    cursor = conn.cursor()

    # Get owner connections
    cursor.execute("""
        SELECT id, username FROM users
        WHERE id != ?
    """, (owner_id,))

    connections = cursor.fetchall()

    conn.close()

    return render_template(
        'invite_members.html',
        connections=connections,
        group_id=group_id
    )
@app.route('/all_groups')
def all_groups():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()

    groups = conn.execute("""
        SELECT g.*, u.username
        FROM groups g
        JOIN users u ON g.owner_id = u.id
        ORDER BY g.created_at DESC
    """).fetchall()

    conn.close()

    return render_template('all_groups.html', groups=groups)
@app.route('/group_chat/<int:group_id>', methods=['GET', 'POST'])
def group_chat(group_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    # Check if user is joined member
    member = conn.execute("""
        SELECT * FROM group_members
        WHERE group_id=? AND user_id=? AND status='Joined'
    """, (group_id, user_id)).fetchone()

    if not member:
        conn.close()
        flash("You are not part of this group")
        return redirect('/my_groups')

    if request.method == 'POST':
        message = request.form.get('message')
        file = request.files.get('file')

        file_name = None

        if file and file.filename != '':
            file_name = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))

        conn.execute("""
            INSERT INTO group_messages (group_id, sender_id, message, file_name)
            VALUES (?, ?, ?, ?)
        """, (group_id, user_id, message, file_name))

        conn.commit()

    messages = conn.execute("""
        SELECT gm.*, u.username
        FROM group_messages gm
        JOIN users u ON gm.sender_id = u.id
        WHERE gm.group_id=?
        ORDER BY gm.created_at
    """, (group_id,)).fetchall()

    conn.close()

    return render_template('group_chat.html', messages=messages, group_id=group_id)
@app.route('/group/<int:group_id>')
def group_details(group_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    # Check if user is joined member
    membership = conn.execute("""
        SELECT * FROM group_members
        WHERE group_id=? AND user_id=? AND status='Joined'
    """, (group_id, user_id)).fetchone()

    if not membership:
        conn.close()
        flash("You are not a member of this group")
        return redirect('/my_groups')

    # Get group info
    group = conn.execute("""
        SELECT g.*, u.username AS owner_name
        FROM groups g
        JOIN users u ON g.owner_id = u.id
        WHERE g.id=?
    """, (group_id,)).fetchone()

    # Get joined members
    members = conn.execute("""
        SELECT users.username
        FROM group_members
        JOIN users ON group_members.user_id = users.id
        WHERE group_members.group_id=? 
        AND group_members.status='Joined'
    """, (group_id,)).fetchall()

    conn.close()

    return render_template(
        'group_details.html',
        group=group,
        members=members
    )
@app.route('/accept_invite/<int:group_id>')
def accept_invite(group_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    conn.execute("""
        UPDATE group_members
        SET status='Joined'
        WHERE group_id=? AND user_id=?
    """, (group_id, user_id))

    conn.commit()
    conn.close()

    flash("You joined the group successfully")
    return redirect('/my_groups')
@app.route('/reject_invite/<int:group_id>')
def reject_invite(group_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = get_db()

    conn.execute("""
        UPDATE group_members
        SET status='Rejected'
        WHERE group_id=? AND user_id=?
    """, (group_id, user_id))

    conn.commit()
    conn.close()

    flash("Invitation rejected")
    return redirect('/invitations')

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)