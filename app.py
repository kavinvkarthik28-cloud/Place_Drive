from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from collections import defaultdict, deque
import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from models import Student, Company, ShortlistingSystem, InterviewScheduler
from database import (
    init_db, db_login, db_create_user, db_username_exists,
    db_get_registered_rolls, db_add_student, db_get_all_students, db_find_student,
    db_get_registered_company_names, db_add_company, db_get_all_companies,
    db_get_company_applicants,
    db_count_applications, db_has_applied, db_add_application,
    db_clear_shortlist, db_add_shortlist, db_get_shortlist, db_get_student_shortlist,
    db_clear_slots_for_company, db_add_slot, db_get_slots, db_get_slots_for_company,
    db_clear_schedule, db_save_schedule, db_get_schedule,
    db_get_student_schedule, db_get_company_schedule
)

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

app.secret_key = "placedrive_secret_2024"

MAX_APPLICATIONS = 3
AVAILABLE_SKILLS = [
    "Python","Java","C++","C","Machine Learning","Data Science",
    "Web Development","App Development","Cybersecurity","Cloud Computing",
    "React","Django","SQL","Git"
]

init_db()

# ---------------------------------------------------------------------------
# ROLE HELPERS  — strict checks
# ---------------------------------------------------------------------------

def current_user():
    return session.get("user")

def require_role(role):
    u = current_user()
    if not u:
        return redirect(url_for("login_page"))
    if u["role"] != role:
        # Redirect to their own dashboard, not the requested one
        return redirect(url_for("dashboard"))
    return None

# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def root():
    return redirect(url_for("login_page")) if "user" not in session else redirect(url_for("dashboard"))

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role_expected = data.get("role", "").strip()   # which tab they logged in from

    if not username or not password:
        return jsonify({"error": "Enter username and password"}), 400

    user = db_login(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    # Enforce role — must match the tab they used
    if role_expected and user["role"] != role_expected:
        return jsonify({"error": f"This account is not a {role_expected} account"}), 403

    session["user"] = user
    return jsonify({"role": user["role"]})

@app.route("/api/register", methods=["POST"])
def api_register():
    data     = request.json
    role     = data.get("role")
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    # Only student and company can self-register
    if role not in ("student", "company"):
        return jsonify({"error": "Invalid role for registration"}), 400

    if not username or not password:
        return jsonify({"error": "Fill all fields"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if db_username_exists(username):
        return jsonify({"error": "Username already taken"}), 400

    if role == "student":
        roll     = data.get("roll", "").strip()
        name     = data.get("name", "").strip()
        cgpa     = float(data.get("cgpa", 0))
        backlogs = int(data.get("backlogs", 0))
        skills   = data.get("skills", [])
        if not roll or not name or not skills:
            return jsonify({"error": "Fill all student fields"}), 400
        if roll in db_get_registered_rolls():
            return jsonify({"error": "Roll number already registered"}), 400
        db_add_student(Student(roll, name, cgpa, backlogs, skills))
        if not db_create_user(username, password, "student", ref_id=roll):
            return jsonify({"error": "Username already taken"}), 400

    elif role == "company":
        cname            = data.get("company_name", "").strip()
        min_cgpa         = float(data.get("min_cgpa", 0))
        allowed_backlogs = int(data.get("allowed_backlogs", 0))
        skill_weights    = data.get("skill_weights", {})
        if not cname:
            return jsonify({"error": "Company name required"}), 400
        for skill, w in skill_weights.items():
            if not isinstance(w, int) or w < 0 or w > 10:
                return jsonify({"error": f"Skill weight for '{skill}' must be between 0 and 10"}), 400
        if cname in db_get_registered_company_names():
            return jsonify({"error": "Company name already registered"}), 400
        db_add_company(Company(cname, min_cgpa, allowed_backlogs, skill_weights))
        if not db_create_user(username, password, "company", ref_id=cname):
            return jsonify({"error": "Username already taken"}), 400

    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ---------------------------------------------------------------------------
# DASHBOARD  — routes to role-specific dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    u = current_user()
    if not u: return redirect(url_for("login_page"))
    if u["role"] == "admin":   return render_template("admin/dashboard.html")
    if u["role"] == "student": return render_template("student/dashboard.html")
    if u["role"] == "company": return render_template("company/dashboard.html")

# ---------------------------------------------------------------------------
# ADMIN PAGES  — only admin can access
# ---------------------------------------------------------------------------

@app.route("/admin/students")
def admin_students():
    err = require_role("admin")
    if err: return err
    return render_template("admin/students.html", skills=AVAILABLE_SKILLS)

@app.route("/admin/companies")
def admin_companies():
    err = require_role("admin")
    if err: return err
    return render_template("admin/companies.html", skills=AVAILABLE_SKILLS)

@app.route("/admin/applications")
def admin_applications():
    err = require_role("admin")
    if err: return err
    return render_template("admin/applications.html")

@app.route("/admin/shortlist")
def admin_shortlist():
    err = require_role("admin")
    if err: return err
    return render_template("admin/shortlist.html")

@app.route("/admin/schedule")
def admin_schedule():
    err = require_role("admin")
    if err: return err
    return render_template("admin/schedule.html")

# ---------------------------------------------------------------------------
# STUDENT PAGES  — only student can access
# ---------------------------------------------------------------------------

@app.route("/student/profile")
def student_profile():
    err = require_role("student")
    if err: return err
    return render_template("student/profile.html")

@app.route("/student/apply")
def student_apply():
    err = require_role("student")
    if err: return err
    return render_template("student/apply.html")

@app.route("/student/status")
def student_status():
    err = require_role("student")
    if err: return err
    return render_template("student/status.html")

# ---------------------------------------------------------------------------
# COMPANY PAGES  — only company can access
# ---------------------------------------------------------------------------

@app.route("/company/profile")
def company_profile():
    err = require_role("company")
    if err: return err
    return render_template("company/profile.html", skills=AVAILABLE_SKILLS)

@app.route("/company/applicants")
def company_applicants():
    err = require_role("company")
    if err: return err
    return render_template("company/applicants.html")

@app.route("/company/slots")
def company_slots():
    err = require_role("company")
    if err: return err
    return render_template("company/slots.html")

@app.route("/company/schedule")
def company_schedule_page():
    err = require_role("company")
    if err: return err
    return render_template("company/schedule.html")

# ---------------------------------------------------------------------------
# API: ME + SKILLS + STATS
# ---------------------------------------------------------------------------

@app.route("/api/me")
def api_me():
    u = current_user()
    if not u: return jsonify({"error": "Not logged in"}), 401
    return jsonify(u)

@app.route("/api/skills")
def api_skills():
    return jsonify(AVAILABLE_SKILLS)

@app.route("/api/stats")
def api_stats():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    students  = db_get_all_students()
    companies = db_get_all_companies()
    shortlist = db_get_shortlist()
    schedule  = db_get_schedule()
    return jsonify({
        "students":     len(students),
        "companies":    len(companies),
        "applications": sum(len(s.applied_companies) for s in students),
        "shortlisted":  sum(len(v) for v in shortlist.values()),
        "scheduled":    len(schedule)
    })

# ---------------------------------------------------------------------------
# API: STUDENTS
# ---------------------------------------------------------------------------

@app.route("/api/students", methods=["GET"])
def get_students():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    # Students can only see their own data
    if u["role"] == "student":
        s = db_find_student(u["ref_id"])
        return jsonify([{"roll": s.roll, "name": s.name, "cgpa": s.cgpa,
            "backlogs": s.backlogs, "skills": s.skills,
            "applied_companies": s.applied_companies}]) if s else jsonify([])
    return jsonify([{"roll": s.roll, "name": s.name, "cgpa": s.cgpa,
        "backlogs": s.backlogs, "skills": s.skills,
        "applied_companies": s.applied_companies}
        for s in db_get_all_students()])

@app.route("/api/students/me")
def get_my_student():
    u = current_user()
    if not u or u["role"] != "student": return jsonify({"error": "Unauthorized"}), 401
    s = db_find_student(u["ref_id"])
    if not s: return jsonify({"error": "Not found"}), 404
    return jsonify({"roll": s.roll, "name": s.name, "cgpa": s.cgpa,
        "backlogs": s.backlogs, "skills": s.skills,
        "applied_companies": s.applied_companies})

@app.route("/api/students", methods=["POST"])
def add_student():
    u = current_user()
    if not u or u["role"] != "admin": return jsonify({"error": "Unauthorized — admin only"}), 403
    data = request.json
    if data["roll"] in db_get_registered_rolls():
        return jsonify({"error": "Roll already exists"}), 400
    db_add_student(Student(data["roll"], data["name"],
        float(data["cgpa"]), int(data["backlogs"]), data["skills"]))
    return jsonify({"success": True})

# ---------------------------------------------------------------------------
# API: COMPANIES
# ---------------------------------------------------------------------------

@app.route("/api/companies", methods=["GET"])
def get_companies():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    return jsonify([{"name": c.name, "min_cgpa": c.min_cgpa,
        "allowed_backlogs": c.allowed_backlogs, "skill_weights": c.skill_weights}
        for c in db_get_all_companies()])

@app.route("/api/companies/me")
def get_my_company():
    u = current_user()
    if not u or u["role"] != "company": return jsonify({"error": "Unauthorized"}), 401
    c = next((x for x in db_get_all_companies() if x.name == u["ref_id"]), None)
    if not c: return jsonify({"error": "Not found"}), 404
    return jsonify({"name": c.name, "min_cgpa": c.min_cgpa,
        "allowed_backlogs": c.allowed_backlogs, "skill_weights": c.skill_weights})

@app.route("/api/companies", methods=["POST"])
def add_company():
    u = current_user()
    if not u or u["role"] != "admin": return jsonify({"error": "Unauthorized — admin only"}), 403
    data = request.json
    if data["name"] in db_get_registered_company_names():
        return jsonify({"error": "Company already exists"}), 400
    for skill, w in data.get("skill_weights", {}).items():
        if not isinstance(w, int) or w < 0 or w > 10:
            return jsonify({"error": f"Skill weight for '{skill}' must be between 0 and 10"}), 400
    db_add_company(Company(data["name"], float(data["min_cgpa"]),
        int(data["allowed_backlogs"]), data["skill_weights"]))
    return jsonify({"success": True})

@app.route("/api/companies/applicants")
def company_applicants_api():
    u = current_user()
    if not u or u["role"] != "company": return jsonify({"error": "Unauthorized"}), 401
    return jsonify([{"roll": s.roll, "name": s.name, "cgpa": s.cgpa,
        "backlogs": s.backlogs, "skills": s.skills}
        for s in db_get_company_applicants(u["ref_id"])])

# ---------------------------------------------------------------------------
# API: APPLICATIONS
# ---------------------------------------------------------------------------

@app.route("/api/apply", methods=["POST"])
def apply():
    u    = current_user()
    data = request.json
    if u and u["role"] == "student":
        roll, company = u["ref_id"], data["company"]
    elif u and u["role"] == "admin":
        roll, company = data["roll"], data["company"]
    else:
        return jsonify({"error": "Unauthorized"}), 403
    if not db_find_student(roll): return jsonify({"error": "Student not found"}), 404
    if company not in db_get_registered_company_names(): return jsonify({"error": "Company not found"}), 404
    if db_count_applications(roll) >= MAX_APPLICATIONS:
        return jsonify({"error": f"Max {MAX_APPLICATIONS} applications allowed"}), 400
    if db_has_applied(roll, company): return jsonify({"error": "Already applied to this company"}), 400
    db_add_application(roll, company)
    return jsonify({"success": True})

# ---------------------------------------------------------------------------
# API: SHORTLIST  — admin only
# ---------------------------------------------------------------------------

@app.route("/api/shortlist", methods=["POST"])
def run_shortlist():
    u = current_user()
    if not u or u["role"] != "admin": return jsonify({"error": "Unauthorized — admin only"}), 403
    companies    = db_get_all_companies()
    all_students = db_get_all_students()
    if not companies or not all_students:
        return jsonify({"error": "Need both students and companies"}), 400
    system = ShortlistingSystem()
    db_clear_shortlist()
    results = []
    for student in all_students:
        ranked = system.recommend_companies(student, companies)
        if ranked:
            for company_name, score in ranked:
                db_add_shortlist(student.roll, company_name, score)
            results.append({
                "student": student.name,
                "roll":    student.roll,
                "matches": [
                    {"company": cn, "score": round(sc, 2)}
                    for cn, sc in ranked
                ],
            })
        else:
            results.append({
                "student": student.name,
                "roll":    student.roll,
                "matches": [],
            })
    return jsonify(results)

@app.route("/api/shortlist", methods=["GET"])
def get_shortlist():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    if u["role"] == "student":
        return jsonify(db_get_student_shortlist(u["ref_id"]))   # always a list
    if u["role"] == "company":
        shortlist = db_get_shortlist()
        students  = shortlist.get(u["ref_id"], [])
        return jsonify([{"roll": s.roll, "name": s.name, "cgpa": s.cgpa,
            "backlogs": s.backlogs, "skills": s.skills} for s in students])
    shortlist = db_get_shortlist()
    return jsonify([{"company": c, "roll": s.roll, "name": s.name}
        for c, students in shortlist.items() for s in students])

# ---------------------------------------------------------------------------
# API: SLOTS
# ---------------------------------------------------------------------------

@app.route("/api/slots", methods=["POST"])
def add_slots():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    if u["role"] == "student": return jsonify({"error": "Unauthorized"}), 403
    data    = request.json
    company = u["ref_id"] if u["role"] == "company" else data.get("company")
    db_clear_slots_for_company(company)
    for slot in data["slots"]:
        db_add_slot(company, slot["date"], slot["time"])
    return jsonify({"success": True})

@app.route("/api/slots", methods=["GET"])
def get_slots():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    if u["role"] == "company":
        return jsonify([{"date": d, "time": t}
            for d, t in db_get_slots_for_company(u["ref_id"])])
    slots = db_get_slots()
    return jsonify([{"company": c, "date": d, "time": t}
        for c, sl in slots.items() for d, t in sl])

# ---------------------------------------------------------------------------
# API: SCHEDULE
# ---------------------------------------------------------------------------

@app.route("/api/schedule", methods=["POST"])
def run_schedule():
    u = current_user()
    if not u or u["role"] != "admin": return jsonify({"error": "Unauthorized — admin only"}), 403
    shortlist_map = db_get_shortlist()
    company_slots = db_get_slots()
    if not shortlist_map: return jsonify({"error": "Run shortlisting first"}), 400

    # Build per-student rankings: {roll: [(Student, company_name), ...]} in score DESC order
    seen_students = {}                                       # roll -> Student
    for company, students in shortlist_map.items():
        for s in students:
            seen_students[s.roll] = s
    student_rankings = {}
    for roll, s in seen_students.items():
        ranked_rows = db_get_student_shortlist(roll)         # list of {company, score}, score DESC
        student_rankings[roll] = [(s, r["company"]) for r in ranked_rows]

    company_queues = {c: deque(sl) for c, sl in shortlist_map.items()}
    scheduler = InterviewScheduler(company_queues, company_slots)
    scheduler.student_rankings = student_rankings            # attach for the corrected schedule()
    scheduler.schedule()
    db_clear_schedule()
    db_save_schedule(scheduler.final_schedule)
    return jsonify(scheduler.final_schedule)

@app.route("/api/schedule", methods=["GET"])
def get_schedule():
    u = current_user()
    if not u: return jsonify({"error": "Unauthorized"}), 401
    if u["role"] == "student": return jsonify(db_get_student_schedule(u["ref_id"]))
    if u["role"] == "company": return jsonify(db_get_company_schedule(u["ref_id"]))
    return jsonify(db_get_schedule())

if __name__ == "__main__":
    app.run(debug=True)
