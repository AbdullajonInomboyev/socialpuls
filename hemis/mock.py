"""Faqat ishlab chiqish va testlar uchun (HEMIS_MODE=mock, DEBUG=True).

Real HEMIS javobi tuzilishini takrorlaydi. Production'da settings bu rejimni taqiqlaydi.
"""
from .client import HemisAuthError

MOCK_PASSWORD = "hemis-demo"

_FACULTIES = {
    1: {"id": 1, "name": "Iqtisodiyot fakulteti", "code": "IQT"},
    2: {"id": 2, "name": "Filologiya fakulteti", "code": "FIL"},
}
_SPECIALTIES = {
    11: {"id": 11, "code": "60310100", "name": "Iqtisodiyot", "faculty": 1},
    21: {"id": 21, "code": "60230100", "name": "Filologiya va tillarni o‘qitish (o‘zbek tili)", "faculty": 2},
}
_GROUPS = {
    101: {"id": 101, "name": "IQT-AU-25", "specialty": 11, "faculty": 1},
    201: {"id": 201, "name": "UZB-DU-24", "specialty": 21, "faculty": 2},
}


def _student(sid, first, last, third, gender, gid, level, gpa):
    g = _GROUPS[gid]
    sp = _SPECIALTIES[g["specialty"]]
    return {
        "id": int(sid[-5:]),
        "student_id_number": sid,
        "first_name": first,
        "second_name": last,
        "third_name": third,
        "full_name": f"{last} {first} {third}",
        "image": "",
        "email": "",
        "phone": "",
        "gender": {"code": "11" if gender == "m" else "12", "name": "Erkak" if gender == "m" else "Ayol"},
        "faculty": _FACULTIES[g["faculty"]],
        "specialty": {"id": sp["id"], "code": sp["code"], "name": sp["name"]},
        "group": {"id": g["id"], "name": g["name"], "educationLang": {"code": "11", "name": "O‘zbek"}},
        "level": {"code": str(10 + level), "name": f"{level}-kurs"},
        "educationForm": {"code": "11", "name": "Kunduzgi"},
        "educationType": {"code": "11", "name": "Bakalavr"},
        "paymentForm": {"code": "12", "name": "To‘lov-shartnoma"},
        "avg_gpa": gpa,
    }


MOCK_STUDENTS = {
    "309251104208": _student("309251104208", "Ulug‘bek", "Mirzaxalilov", "Akmal o‘g‘li", "m", 101, 1, "4.12"),
    "309251104207": _student("309251104207", "Hilola", "Tog‘ayeva", "Rustam qizi", "f", 201, 2, "4.68"),
}


class MockStudentClient:
    def login(self, login, password):
        if login in MOCK_STUDENTS and password == MOCK_PASSWORD:
            return f"mock-token-{login}"
        raise HemisAuthError("Login yoki parol noto'g'ri.")

    def me(self, token):
        return dict(MOCK_STUDENTS[token.removeprefix("mock-token-")])


class MockDataClient:
    def iter_items(self, path, params=None, **kwargs):
        if path.startswith("data/department-list"):
            yield from ({"id": f["id"], "name": f["name"], "code": f["code"], "structureType": {"code": "11"}} for f in _FACULTIES.values())
        elif path.startswith("data/specialty-list"):
            yield from (
                {"id": s["id"], "code": s["code"], "name": s["name"], "department": {"id": s["faculty"]}}
                for s in _SPECIALTIES.values()
            )
        elif path.startswith("data/group-list"):
            yield from (
                {"id": g["id"], "name": g["name"], "specialty": {"id": g["specialty"]}, "department": {"id": g["faculty"]},
                 "educationLang": {"name": "O‘zbek"}}
                for g in _GROUPS.values()
            )
        elif path.startswith("data/student-list"):
            yield from MOCK_STUDENTS.values()
