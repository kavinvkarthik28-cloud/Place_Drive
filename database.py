import psycopg2
import psycopg2.extras
import os, hashlib, secrets


# ── UPDATE YOUR PASSWORD HERE ─────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(
        host     = "localhost",
        port     = "5432",
        dbname   = "placement_db",
        user     = "postgres",
        password = "postgres123"   # <-- change this to your actual password
    )
# ─────────────────────────────────────────────────────────────────────────


def hash_password(password):
    salt   = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, stored):
    try:
        salt, hashed = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except:
        return False


def init_db():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(200) NOT NULL,
        role VARCHAR(20) NOT NULL CHECK (role IN ('admin','student','company')),
        ref_id VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")

    cur.execute("""CREATE TABLE IF NOT EXISTS students (
        roll VARCHAR(20) PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        cgpa NUMERIC(4,2) NOT NULL CHECK (cgpa>=0.0 AND cgpa<=10.0),
        backlogs INTEGER NOT NULL CHECK (backlogs>=0));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS student_skills (
        roll VARCHAR(20) REFERENCES students(roll) ON DELETE CASCADE,
        skill VARCHAR(50) NOT NULL,
        skill_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (roll, skill));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS companies (
        name VARCHAR(100) PRIMARY KEY,
        min_cgpa NUMERIC(4,2) NOT NULL CHECK (min_cgpa>=0.0 AND min_cgpa<=10.0),
        allowed_backlogs INTEGER NOT NULL CHECK (allowed_backlogs>=0));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS company_skill_weights (
        company_name VARCHAR(100) REFERENCES companies(name) ON DELETE CASCADE,
        skill VARCHAR(50) NOT NULL,
        weight INTEGER NOT NULL CHECK (weight>0),
        PRIMARY KEY (company_name, skill));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS applications (
        roll VARCHAR(20) REFERENCES students(roll) ON DELETE CASCADE,
        company_name VARCHAR(100) REFERENCES companies(name) ON DELETE CASCADE,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (roll, company_name));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS shortlist (
        roll VARCHAR(20) REFERENCES students(roll) ON DELETE CASCADE,
        company_name VARCHAR(100) REFERENCES companies(name) ON DELETE CASCADE,
        score NUMERIC(10,4),
        shortlisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (roll, company_name));""")

    cur.execute("""CREATE TABLE IF NOT EXISTS interview_slots (
        id SERIAL PRIMARY KEY,
        company_name VARCHAR(100) REFERENCES companies(name) ON DELETE CASCADE,
        slot_date VARCHAR(30) NOT NULL,
        slot_time VARCHAR(20) NOT NULL);""")

    cur.execute("""CREATE TABLE IF NOT EXISTS interview_schedule (
        id SERIAL PRIMARY KEY,
        roll VARCHAR(20) REFERENCES students(roll) ON DELETE CASCADE,
        company_name VARCHAR(100) REFERENCES companies(name) ON DELETE CASCADE,
        slot_date VARCHAR(30) NOT NULL,
        slot_time VARCHAR(20) NOT NULL,
        UNIQUE (roll, slot_date, slot_time));""")

    # Create default admin account if not exists
    cur.execute("SELECT id FROM users WHERE role='admin' LIMIT 1;")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s);",
            ("admin", hash_password("admin123"), "admin")
        )

    conn.commit()
    cur.close()
    conn.close()


# ── USER AUTH ─────────────────────────────────────────────────────────────

def db_create_user(username, password, role, ref_id=None):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password, role, ref_id) VALUES (%s,%s,%s,%s);",
            (username, hash_password(password), role, ref_id)
        )
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        cur.close(); conn.close()


def db_login(username, password):
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE username=%s;", (username,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if user and verify_password(password, user["password"]):
        return {"id": user["id"], "username": user["username"],
                "role": user["role"], "ref_id": user["ref_id"]}
    return None


def db_username_exists(username):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username=%s;", (username,))
    exists = cur.fetchone() is not None
    cur.close(); conn.close()
    return exists


# ── STUDENTS ──────────────────────────────────────────────────────────────

def db_get_registered_rolls():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT roll FROM students;")
    rolls = {row[0] for row in cur.fetchall()}
    cur.close(); conn.close()
    return rolls


def db_add_student(student):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO students (roll, name, cgpa, backlogs) VALUES (%s,%s,%s,%s);",
            (student.roll, student.name, student.cgpa, student.backlogs)
        )
        for order, skill in enumerate(student.skills):
            cur.execute(
                "INSERT INTO student_skills (roll, skill, skill_order) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING;",
                (student.roll, skill, order)
            )
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


def db_get_all_students():
    from models import Student
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT roll, name, cgpa, backlogs FROM students ORDER BY name;")
    rows = cur.fetchall(); students = []
    for row in rows:
        roll = row["roll"]
        cur.execute("SELECT skill FROM student_skills WHERE roll=%s ORDER BY skill_order;", (roll,))
        skills = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT company_name FROM applications WHERE roll=%s ORDER BY applied_at;", (roll,))
        applied = [r[0] for r in cur.fetchall()]
        s = Student(roll, row["name"], float(row["cgpa"]), row["backlogs"], skills)
        s.applied_companies = applied
        students.append(s)
    cur.close(); conn.close()
    return students


def db_find_student(roll):
    from models import Student
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT roll, name, cgpa, backlogs FROM students WHERE roll=%s;", (roll,))
    row = cur.fetchone()
    if row is None:
        cur.close(); conn.close(); return None
    cur.execute("SELECT skill FROM student_skills WHERE roll=%s ORDER BY skill_order;", (roll,))
    skills = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT company_name FROM applications WHERE roll=%s ORDER BY applied_at;", (roll,))
    applied = [r[0] for r in cur.fetchall()]
    s = Student(row["roll"], row["name"], float(row["cgpa"]), row["backlogs"], skills)
    s.applied_companies = applied
    cur.close(); conn.close()
    return s


# ── COMPANIES ─────────────────────────────────────────────────────────────

def db_get_registered_company_names():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT name FROM companies;")
    names = {row[0] for row in cur.fetchall()}
    cur.close(); conn.close()
    return names


def db_add_company(company):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO companies (name, min_cgpa, allowed_backlogs) VALUES (%s,%s,%s);",
            (company.name, company.min_cgpa, company.allowed_backlogs)
        )
        for skill, weight in company.skill_weights.items():
            cur.execute(
                "INSERT INTO company_skill_weights (company_name, skill, weight) VALUES (%s,%s,%s);",
                (company.name, skill, weight)
            )
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


def db_get_all_companies():
    from models import Company
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT name, min_cgpa, allowed_backlogs FROM companies;")
    rows = cur.fetchall(); companies = []
    for row in rows:
        cur.execute("SELECT skill, weight FROM company_skill_weights WHERE company_name=%s;", (row["name"],))
        weights = {r["skill"]: r["weight"] for r in cur.fetchall()}
        companies.append(Company(row["name"], float(row["min_cgpa"]), row["allowed_backlogs"], weights))
    cur.close(); conn.close()
    return companies


def db_get_company_applicants(company_name):
    from models import Student
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT s.roll, s.name, s.cgpa, s.backlogs FROM applications a
        JOIN students s ON s.roll=a.roll WHERE a.company_name=%s ORDER BY a.applied_at;""", (company_name,))
    rows = cur.fetchall(); result = []
    for row in rows:
        cur.execute("SELECT skill FROM student_skills WHERE roll=%s ORDER BY skill_order;", (row["roll"],))
        skills = [r[0] for r in cur.fetchall()]
        result.append(Student(row["roll"], row["name"], float(row["cgpa"]), row["backlogs"], skills))
    cur.close(); conn.close()
    return result


# ── APPLICATIONS ──────────────────────────────────────────────────────────

def db_count_applications(roll):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM applications WHERE roll=%s;", (roll,))
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    return count


def db_has_applied(roll, company_name):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT 1 FROM applications WHERE roll=%s AND company_name=%s;", (roll, company_name))
    exists = cur.fetchone() is not None
    cur.close(); conn.close()
    return exists


def db_add_application(roll, company_name):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("INSERT INTO applications (roll, company_name) VALUES (%s,%s);", (roll, company_name))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


# ── SHORTLIST ─────────────────────────────────────────────────────────────

def db_clear_shortlist():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM shortlist;")
    conn.commit(); cur.close(); conn.close()


def db_add_shortlist(roll, company_name, score):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""INSERT INTO shortlist (roll, company_name, score)
            VALUES (%s,%s,%s) ON CONFLICT (roll,company_name) DO UPDATE SET score=EXCLUDED.score;""",
            (roll, company_name, score))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


def db_get_shortlist():
    from models import Student
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT s.roll, st.name, st.cgpa, st.backlogs, s.company_name, s.score
        FROM shortlist s JOIN students st ON st.roll=s.roll
        ORDER BY s.company_name, s.score DESC;""")
    rows = cur.fetchall(); result = {}
    for row in rows:
        roll    = row["roll"]
        company = row["company_name"]
        cur.execute("SELECT skill FROM student_skills WHERE roll=%s ORDER BY skill_order;", (roll,))
        skills  = [r[0] for r in cur.fetchall()]
        student = Student(roll, row["name"], float(row["cgpa"]), row["backlogs"], skills)
        if company not in result:
            result[company] = []
        result[company].append(student)
    cur.close(); conn.close()
    return result


def db_get_student_shortlist(roll):
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT company_name, score FROM shortlist WHERE roll=%s ORDER BY score DESC;", (roll,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"company": r["company_name"], "score": float(r["score"])} for r in rows]


# ── SLOTS ─────────────────────────────────────────────────────────────────

def db_clear_slots_for_company(company_name):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM interview_slots WHERE company_name=%s;", (company_name,))
    conn.commit(); cur.close(); conn.close()


def db_add_slot(company_name, slot_date, slot_time):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("INSERT INTO interview_slots (company_name, slot_date, slot_time) VALUES (%s,%s,%s);",
            (company_name, slot_date, slot_time))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


def db_get_slots():
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT company_name, slot_date, slot_time FROM interview_slots ORDER BY id;")
    rows = cur.fetchall(); slots = {}
    for row in rows:
        c = row["company_name"]
        if c not in slots: slots[c] = []
        slots[c].append((row["slot_date"], row["slot_time"]))
    cur.close(); conn.close()
    return slots


def db_get_slots_for_company(company_name):
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT slot_date, slot_time FROM interview_slots WHERE company_name=%s ORDER BY id;", (company_name,))
    slots = [(r["slot_date"], r["slot_time"]) for r in cur.fetchall()]
    cur.close(); conn.close()
    return slots


# ── SCHEDULE ──────────────────────────────────────────────────────────────

def db_clear_schedule():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM interview_schedule;")
    conn.commit(); cur.close(); conn.close()


def db_save_schedule(entries):
    conn = get_connection()
    cur  = conn.cursor()
    try:
        for e in entries:
            cur.execute("""INSERT INTO interview_schedule (roll, company_name, slot_date, slot_time)
                VALUES (%s,%s,%s,%s) ON CONFLICT (roll, slot_date, slot_time) DO NOTHING;""",
                (e["student"], e["company"], e["date"], e["time"]))
        conn.commit()
    except Exception as e:
        conn.rollback(); raise e
    finally:
        cur.close(); conn.close()


def db_get_schedule():
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT roll, company_name, slot_date, slot_time FROM interview_schedule
        ORDER BY company_name, slot_date, slot_time;""")
    rows = cur.fetchall()
    result = [{"student": r["roll"], "company": r["company_name"],
               "date": r["slot_date"], "time": r["slot_time"]} for r in rows]
    cur.close(); conn.close()
    return result


def db_get_student_schedule(roll):
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT company_name, slot_date, slot_time FROM interview_schedule
        WHERE roll=%s ORDER BY slot_date, slot_time;""", (roll,))
    result = [{"company": r["company_name"], "date": r["slot_date"], "time": r["slot_time"]}
              for r in cur.fetchall()]
    cur.close(); conn.close()
    return result


def db_get_company_schedule(company_name):
    conn = get_connection()
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT i.roll, s.name, i.slot_date, i.slot_time
        FROM interview_schedule i JOIN students s ON s.roll=i.roll
        WHERE i.company_name=%s ORDER BY i.slot_date, i.slot_time;""", (company_name,))
    result = [{"roll": r["roll"], "name": r["name"], "date": r["slot_date"], "time": r["slot_time"]}
              for r in cur.fetchall()]
    cur.close(); conn.close()
    return result
