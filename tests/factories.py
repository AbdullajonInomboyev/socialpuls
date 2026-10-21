from datetime import date
from decimal import Decimal

from accounts.models import Role, StudentProfile, User
from structure.models import AcademicYear, Faculty, Group, Semester, Specialty

PASSWORD = "Test-parol-2026!"


def make_structure():
    year = AcademicYear.objects.create(name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 6, 30), is_current=True)
    sem1 = Semester.objects.create(academic_year=year, number=1, start_date=date(2026, 9, 1), end_date=date(2027, 1, 31), is_current=True)
    sem2 = Semester.objects.create(academic_year=year, number=2, start_date=date(2027, 2, 1), end_date=date(2027, 6, 30))
    f1 = Faculty.objects.create(name="Iqtisodiyot fakulteti", hemis_id=1)
    f2 = Faculty.objects.create(name="Filologiya fakulteti", hemis_id=2)
    sp1 = Specialty.objects.create(name="Iqtisodiyot", faculty=f1, hemis_id=11)
    sp2 = Specialty.objects.create(name="Filologiya", faculty=f2, hemis_id=21)
    g1 = Group.objects.create(name="IQT-AU-25", faculty=f1, specialty=sp1, hemis_id=101)
    g2 = Group.objects.create(name="UZB-DU-24", faculty=f2, specialty=sp2, hemis_id=201)
    return {"year": year, "sem1": sem1, "sem2": sem2, "f1": f1, "f2": f2, "g1": g1, "g2": g2}


def make_staff(username, role, faculty=None, groups=()):
    u = User.objects.create_user(username=username, password=PASSWORD, role=role, faculty=faculty, email=f"{username}@namdu.uz", first_name=username.title())
    if groups:
        u.tutor_groups.set(groups)
    return u


def make_student(sid, group, gpa="4.00"):
    u = User.objects.create(username=f"s{sid}", hemis_id=sid, role=Role.STUDENT, first_name="Ali", last_name="Valiyev")
    u.set_unusable_password()
    u.save()
    StudentProfile.objects.create(user=u, student_id_number=sid, faculty=group.faculty, specialty=group.specialty, group=group, course=1, gpa=Decimal(gpa))
    return u
