import heapq
from collections import defaultdict


class Student:
    def __init__(self, roll, name, cgpa, backlogs, skills):
        self.roll = roll
        self.name = name
        self.cgpa = cgpa
        self.backlogs = backlogs
        self.skills = skills
        self.applied_companies = []


class Node:
    def __init__(self, student):
        self.student = student
        self.next = None


class StudentLinkedList:
    def __init__(self):
        self.head = None

    def add_student(self, student):
        new_node = Node(student)
        new_node.next = self.head
        self.head = new_node

    def get_all_students(self):
        students = []
        temp = self.head
        while temp:
            students.append(temp.student)
            temp = temp.next
        return students

    def find_student(self, roll):
        temp = self.head
        while temp:
            if temp.student.roll == roll:
                return temp.student
            temp = temp.next
        return None

    def load_from_db(self, db_students):
        self.head = None
        for s in reversed(db_students):
            new_node = Node(s)
            new_node.next = self.head
            self.head = new_node


class Company:
    def __init__(self, name, min_cgpa, allowed_backlogs, skill_weights):
        self.name = name
        self.min_cgpa = min_cgpa
        self.allowed_backlogs = allowed_backlogs
        self.skill_weights = skill_weights


class ShortlistingSystem:
    def calculate_skill_score(self, student, company):
        score = 0
        for skill in student.skills:
            if skill in company.skill_weights:
                score += company.skill_weights[skill]
        return score

    def total_score(self, student, company):
        skill_score = self.calculate_skill_score(student, company)
        return skill_score + (2 * student.cgpa) - (5 * student.backlogs)

    def recommend_companies(self, student, companies):
        # Only consider companies the student actually applied to
        applied = set(student.applied_companies)
        heap = []
        for company in companies:
            if company.name not in applied:
                continue
            if student.cgpa < company.min_cgpa:
                continue
            if student.backlogs > company.allowed_backlogs:
                continue
            score = self.total_score(student, company)
            heapq.heappush(heap, (-score, company.name))
        # Pop all in score order — highest first
        ranked = []
        while heap:
            neg_score, name = heapq.heappop(heap)
            ranked.append((name, -neg_score))
        return ranked   # list of (company_name, score) — possibly empty


class InterviewScheduler:
    def __init__(self, company_queues, company_slots):
        self.company_queues   = company_queues
        self.company_slots    = company_slots
        self.student_schedule = defaultdict(list)
        self.final_schedule   = []

    def slot_available(self, student_roll, date, time):
        for company, d, t in self.student_schedule[student_roll]:
            if d == date and t == time:
                return False
        return True

    def schedule(self):
        if not self.company_queues:
            print("No students shortlisted")
            return

        # Build per-student company list in shortlist rank order.
        # The caller is expected to attach scheduler.student_rankings = {roll: [(student, company), ...]}
        # ordered by score DESC. If absent, derive a reasonable fallback from company_queues.
        student_rankings = getattr(self, "student_rankings", None)
        if student_rankings is None:
            student_rankings = {}
            for company, students in self.company_queues.items():
                for s in students:
                    student_rankings.setdefault(s.roll, []).append((s, company))

        # Track which slot indices are already used per company
        used = {company: set() for company in self.company_slots}

        for student_roll, ranked in student_rankings.items():
            for student, company in ranked:
                slots = self.company_slots.get(company, [])
                if not slots:
                    continue
                if len(used.get(company, set())) >= len(slots):
                    continue   # this company is fully booked
                if company not in used:
                    used[company] = set()
                for i in range(len(slots)):
                    if i in used[company]:
                        continue
                    date, time = slots[i]
                    if self.slot_available(student_roll, date, time):
                        self.student_schedule[student_roll].append((company, date, time))
                        self.final_schedule.append({
                            "student": student_roll,
                            "company": company,
                            "date":    date,
                            "time":    time,
                        })
                        used[company].add(i)
                        break
                # If no non-conflicting slot at this company, fall through to the
                # next-ranked company in the student's list.

    def display_schedule(self):
        if not self.final_schedule:
            print("No interview schedule created")
            return
        print("\nFinal Interview Schedule\n")
        for entry in self.final_schedule:
            print("Student", entry["student"], "->", entry["company"],
                  "|", entry["date"], entry["time"])
