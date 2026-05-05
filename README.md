# PlaceDrive — Placement Drive Management System

A full-stack web application that automates the end-to-end lifecycle of a campus placement drive — from student registration and company onboarding, through eligibility-based shortlisting, all the way to conflict-free interview scheduling.

Built with **Python + Flask** and a **dark-theme glassmorphism UI**, with classical data structures powering the core algorithms.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Data Structures & Algorithms](#data-structures--algorithms)
- [System Architecture](#system-architecture)
- [Database Schema](#database-schema)
- [Modules](#modules)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Team](#team)

---

## Overview

Manual placement workflows — spreadsheets, email chains, phone calls — break down fast under the load of hundreds of students and dozens of companies. PlaceDrive replaces that patchwork with a single integrated system where:

- Students register, build profiles with skills, and apply to companies
- Companies post eligibility criteria, skill weights, and interview slots
- Admins run a deterministic shortlisting algorithm and a conflict-free scheduler with one click

Every piece of state lives in a normalised PostgreSQL database. Every stakeholder gets a real-time role-specific dashboard. The matching and scheduling logic is powered by classical DSA — not operator judgement.

---

## Features

- **Three-role authenticated login** — Admin, Student, Company with strict server-side role enforcement
- **Student registration** with skill-chip selection from a canonical catalogue
- **Company registration** with eligibility criteria (min CGPA, allowed backlogs) and per-skill weights
- **Application submission** with eligibility checking, duplicate detection, and per-student cap (default: 3)
- **Automated shortlisting** using a greedy + min-heap algorithm against a defined scoring formula
- **Conflict-free interview scheduling** using a queue-based FCFS allocator with hash-based conflict detection
- **Role-specific dashboards** with real-time data via REST API + `fetch()`
- **Three-layer form validation** — JavaScript, Flask, and PostgreSQL constraints
- **Salted SHA-256 password hashing** — passwords never stored or transmitted as plaintext
- **Parameterised SQL** — immune to SQL injection by construction

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+, Flask 3.x |
| Database | PostgreSQL 13+, psycopg2-binary |
| Frontend | Vanilla HTML, CSS, JavaScript, Jinja2 |
| Fonts | Google Fonts — Syne, DM Sans |
| Algorithms | Python `heapq`, `collections.deque`, `defaultdict` |

~1,800 lines of code across 3 Python modules, 16 templates, 1 CSS file, and 1 shared JS file.

---

## Data Structures & Algorithms

### Scoring Formula (Shortlisting)

```
score = Σ company.skill_weights[s] + 2 × student.cgpa − 5 × student.backlogs
```

CGPA is weighted ×2 as the primary placement metric. Backlogs carry a −5 penalty as the most common disqualification reason. Both coefficients are configurable in source.

### Data Structures Used

| Structure | Role | Complexity |
|---|---|---|
| Singly Linked List | Student storage | Insert O(1) · Search O(n) |
| Min-Heap (`heapq`) | Best company selection per student | Push/Pop O(log n) |
| Queue (`collections.deque`) | FCFS student processing per company | Enqueue/Dequeue O(1) |
| Hash Map (`defaultdict`) | Per-student conflict detection | Lookup O(1) average |
| Hash Set | Duplicate roll/company detection at registration | Lookup O(1) |

### Shortlisting Algorithm

```python
for each student S:
    heap = []
    for each company C:
        if S.cgpa < C.min_cgpa: continue
        if S.backlogs > C.allowed_backlogs: continue
        heapq.heappush(heap, (-score(S, C), C.name))
    if heap:
        best = heapq.heappop(heap)   # highest score
```

**Complexity:** O(S × C log C) for S students and C companies.

### Scheduling Algorithm

```python
for company, queue in company_queues.items():
    for student in queue:                          # FCFS order
        for (date, time) in company_slots[company]:
            if slot_available(student.roll, date, time):   # O(1) hash check
                assign(student, company, date, time)
                break
```

**Complexity:** O(S × K) for S shortlisted students and K average slots per company.

---

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Presentation Tier                  │
│         HTML + CSS + JS + Jinja2 Templates           │
│   (role dashboards, forms, fetch() API calls)        │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼─────────────────────────────┐
│                  Application Tier                    │
│              Python + Flask                          │
│   (routing, role enforcement, business logic,        │
│    shortlisting & scheduling algorithms)             │
└───────────────────────┬─────────────────────────────┘
                        │ psycopg2
┌───────────────────────▼─────────────────────────────┐
│                   Data Tier                          │
│              PostgreSQL                              │
│   (9 normalised tables, UNIQUE constraints,          │
│    foreign keys, cascading deletes, transactions)    │
└─────────────────────────────────────────────────────┘
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | Authentication accounts for all three roles |
| `students` | Student profile — roll, name, CGPA, backlogs |
| `student_skills` | Many-to-many: student ↔ skill |
| `companies` | Company profile — name, min CGPA, allowed backlogs |
| `company_skill_weights` | Per-skill weight per company |
| `applications` | Student-to-company applications with timestamp |
| `shortlist` | Shortlisting result with score per student |
| `interview_slots` | Available slots entered by each company |
| `interview_schedule` | Final assigned interviews — `UNIQUE(roll, date, time)` |

---

## Modules

### Admin
Full read/write access to all entities. Only role authorised to invoke shortlisting and scheduling. Has an aggregate dashboard showing system-wide counts.

### Student
Can register, browse companies with eligibility hints, apply (max 3), and view their own shortlist outcome and assigned interview slot.

### Company
Can register, post interview slots, and view their own applicants, shortlisted students, and scheduled interviews. Cannot access other companies' data.

---

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 13+

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/placedrive.git
cd placedrive

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up PostgreSQL
createdb placedrive

# 5. Configure the database connection
# Edit database.py and set your PostgreSQL connection string
DB_URL = "postgresql://user:password@localhost/placedrive"

# 6. Initialise the schema
python -c "from database import init_db; init_db()"

# 7. Run the app
flask run
```

The app will be available at `http://localhost:5000`.

---

## Usage

1. **Register** as a Student or Company from the login page (use the appropriate tab)
2. **Students** — complete your profile with skills, browse companies, and apply
3. **Companies** — set your eligibility criteria, skill weights, and upload interview slots
4. **Admin** — once applications are in, click **Run Shortlisting**, then **Run Scheduling**
5. **Students and Companies** — view results on their respective dashboards immediately after

---

## Project Structure

```
placedrive/
├── app.py              # Flask routes, role enforcement, REST API
├── models.py           # DSA core — Linked List, Heap, Queue, Greedy scheduler
├── database.py         # PostgreSQL persistence layer (all db_ functions)
├── requirements.txt
├── static/
│   ├── css/
│   │   └── main.css    # Dark-theme glassmorphism design system
│   └── js/
│       └── main.js     # Shared fetch() wrappers, toast notifications, user cache
└── templates/
    ├── base.html        # Shared shell — sidebar, nav, font imports
    ├── login.html       # Three-tab role login
    ├── admin/
    │   ├── dashboard.html
    │   ├── students.html
    │   ├── companies.html
    │   ├── shortlist.html
    │   └── schedule.html
    ├── student/
    │   ├── dashboard.html
    │   ├── apply.html
    │   ├── shortlist.html
    │   └── schedule.html
    └── company/
        ├── dashboard.html
        ├── applicants.html
        ├── slots.html
        └── schedule.html
```

---

## Team

**Team No. 04 — Department of Computer Science and Engineering (Artificial Intelligence)**
Academic Year 2025–2026

| Name | Roll Number |
|---|---|
| Harsith Ramprakash | CB.SC.U4AIE25120 |
| Kavin Karthik V | CB.SC.U4AIE25128 |
| Siva Krithick | CB.SC.U4AIE25157 |
| Sahesh Karthikeyan | CB.SC.U4AIE25149 |

---

*Data Structures & Algorithms / UI Development Project*
