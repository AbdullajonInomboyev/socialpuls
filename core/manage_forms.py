from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import Role, User
from structure.models import AcademicYear, Faculty, Group

from .models import SiteSettings


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "system_name", "university_name", "university_short", "contact_email", "idle_timeout_minutes",
            "student_upload_enabled", "monthly_reminder_enabled", "public_stats_enabled", "maintenance_mode",
        ]
        widgets = {"idle_timeout_minutes": forms.NumberInput(attrs={"min": 0, "max": 480})}

    def clean_idle_timeout_minutes(self):
        v = self.cleaned_data["idle_timeout_minutes"]
        if v and not 5 <= v <= 480:
            raise ValidationError("5 dan 480 daqiqagacha yoki 0 (o‘chirilgan).")
        return v


class AcademicYearForm(forms.Form):
    """Yangi o'quv yili ikki semestri bilan birga yaratiladi."""

    name = forms.RegexField(label="O‘quv yili", regex=r"^\d{4}-\d{4}$", widget=forms.TextInput(attrs={"placeholder": "2027-2028"}), error_messages={"invalid": "Masalan: 2027-2028"})
    sem1_start = forms.DateField(label="1-semestr boshlanishi", widget=forms.DateInput(attrs={"type": "date"}))
    sem1_end = forms.DateField(label="1-semestr tugashi", widget=forms.DateInput(attrs={"type": "date"}))
    sem2_start = forms.DateField(label="2-semestr boshlanishi", widget=forms.DateInput(attrs={"type": "date"}))
    sem2_end = forms.DateField(label="2-semestr tugashi", widget=forms.DateInput(attrs={"type": "date"}))

    def clean_name(self):
        name = self.cleaned_data["name"]
        a, b = (int(x) for x in name.split("-"))
        if b != a + 1:
            raise ValidationError("Yillar ketma-ket bo‘lishi kerak, masalan 2027-2028.")
        if AcademicYear.objects.filter(name=name).exists():
            raise ValidationError("Bu o‘quv yili allaqachon bor.")
        return name

    def clean(self):
        c = super().clean()
        keys = ["sem1_start", "sem1_end", "sem2_start", "sem2_end"]
        if all(c.get(k) for k in keys):
            d = [c[k] for k in keys]
            if not (d[0] < d[1] < d[2] < d[3]):
                raise ValidationError("Sanalar tartibi: 1-semestr boshlanishi < tugashi < 2-semestr boshlanishi < tugashi.")
        return c


class StaffForm(forms.ModelForm):
    password = forms.CharField(
        label="Boshlang‘ich parol", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Bo‘sh qoldirsangiz, xodim emailiga parol o‘rnatish havolasi yuboriladi.",
    )

    class Meta:
        model = User
        fields = ["username", "last_name", "first_name", "middle_name", "email", "phone", "role", "faculty", "tutor_groups", "is_active"]
        widgets = {"tutor_groups": forms.SelectMultiple(attrs={"size": 8})}
        labels = {"username": "Login", "last_name": "Familiya", "first_name": "Ism", "email": "Email",
                  "is_active": "Faol (tizimga kira oladi)"}
        help_texts = {"username": "Lotin harflari, raqamlar va . _ - belgilari; 150 belgigacha."}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        roles = [(r.value, r.label) for r in Role if r != Role.STUDENT]
        if actor is not None and actor.role == Role.MODERATOR and not actor.is_superuser:
            roles = [r for r in roles if r[0] != Role.LEADERSHIP]  # moderator rahbariyat hisobini yarata olmaydi
        self.fields["role"].choices = roles
        self.fields["faculty"].queryset = Faculty.objects.filter(is_active=True)
        self.fields["tutor_groups"].queryset = Group.objects.select_related("faculty").order_by("faculty__name", "name")
        self.fields["tutor_groups"].required = False
        self.fields["email"].required = True
        self.fields["last_name"].required = True
        self.fields["first_name"].required = True
        if self.instance.pk:
            self.fields["password"].help_text = "Faqat o‘zgartirmoqchi bo‘lsangiz to‘ldiring."

    def clean_username(self):
        u = self.cleaned_data["username"].strip().lower()
        if u.startswith("s") and u[1:].isdigit():
            raise ValidationError("“s” va raqamlar bilan boshlanadigan login talabalar uchun band.")
        return u

    def clean(self):
        c = super().clean()
        role = c.get("role")
        if role == Role.FACULTY_ADMIN and not c.get("faculty"):
            self.add_error("faculty", "Fakultet mas’uli uchun fakultet tanlang.")
        if role == Role.TUTOR and not c.get("tutor_groups"):
            self.add_error("tutor_groups", "Tyutorga kamida bitta guruh biriktiring.")
        if role not in (Role.FACULTY_ADMIN,):
            c["faculty"] = None
        if role != Role.TUTOR:
            c["tutor_groups"] = []
        pw = c.get("password")
        if pw:
            validate_password(pw, self.instance)
        return c


class BroadcastForm(forms.Form):
    title = forms.CharField(label="Mavzu", max_length=200)
    body = forms.CharField(label="Matn", max_length=4000, widget=forms.Textarea(attrs={"rows": 6}))
    faculty = forms.ModelChoiceField(label="Fakultet", queryset=Faculty.objects.none(), required=False, empty_label="Barcha fakultetlar")
    groups = forms.ModelMultipleChoiceField(label="Guruhlar", queryset=Group.objects.none(), required=False,
                                            widget=forms.SelectMultiple(attrs={"size": 6}), help_text="Tanlanmasa, doirangizdagi barcha guruhlar.")
    course = forms.TypedChoiceField(label="Kurs", choices=[("", "Barcha kurslar")] + [(i, f"{i}-kurs") for i in range(1, 7)],
                                    coerce=int, empty_value=None, required=False)
    only_inactive = forms.BooleanField(label="Faqat joriy semestrda yutug‘i tasdiqlanmaganlarga", required=False)
    via_email = forms.BooleanField(label="Email orqali ham yuborish", required=False)
    via_telegram = forms.BooleanField(label="Telegram orqali ham yuborish", required=False, initial=True)
    confirm = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if user.is_superuser or user.role in (Role.LEADERSHIP, Role.MODERATOR):
            self.fields["faculty"].queryset = Faculty.objects.filter(is_active=True)
            del self.fields["groups"]
        else:
            del self.fields["faculty"]
            if user.role == Role.FACULTY_ADMIN:
                self.fields["groups"].queryset = Group.objects.filter(faculty_id=user.faculty_id).order_by("name")
            else:
                self.fields["groups"].queryset = user.tutor_groups.order_by("name")
