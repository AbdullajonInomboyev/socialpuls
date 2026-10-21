from django.test import TestCase

from accounts.models import Role
from hemis.mock import MOCK_STUDENTS
from hemis.services import _cap, _parse_course, _parse_gpa, upsert_student

from .factories import make_staff, make_structure


class HemisServiceTests(TestCase):
    def setUp(self):
        make_structure()

    def test_upsert_is_idempotent(self):
        u1, created1 = upsert_student(MOCK_STUDENTS["309251104208"])
        u2, created2 = upsert_student(MOCK_STUDENTS["309251104208"])
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(u1.pk, u2.pk)
        self.assertEqual(u1.profile.course, 1)

    def test_staff_hemis_id_is_not_taken_over(self):
        staff = make_staff("x", Role.TUTOR)
        staff.hemis_id = "309251104208"
        staff.save()
        with self.assertRaises(PermissionError):
            upsert_student(MOCK_STUDENTS["309251104208"])

    def test_parsers(self):
        self.assertEqual(_cap("ULUG‘BEK"), "Ulug‘bek")
        self.assertEqual(_cap("AKMAL O‘G‘LI"), "Akmal o‘g‘li")
        self.assertEqual(_parse_course({"code": "13", "name": "3-kurs"}), 3)
        self.assertIsNone(_parse_gpa("7.5"))
        self.assertEqual(str(_parse_gpa("4,5")), "4.50")
