from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Achievement, Criterion, CriterionLevel
from .validators import ACCEPT_ATTR, MAX_FILES, validate_upload


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ACCEPT_ATTR}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        items = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        single = super().clean
        return [single(d, initial) for d in items if d]


class AchievementForm(forms.ModelForm):
    """Talaba yutug'i. Semestr va talaba view da belgilanadi, foydalanuvchidan olinmaydi."""

    files = MultipleFileField(label="Tasdiqlovchi hujjatlar", required=False)
    remove_files = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Achievement
        fields = ["criterion", "level", "title", "event_date", "description"]
        widgets = {
            "criterion": forms.RadioSelect,
            "event_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 4, "maxlength": 2000}),
            "title": forms.TextInput(attrs={"maxlength": 200, "placeholder": "Masalan: “Yosh kitobxon” tanlovi, fakultet bosqichi"}),
        }
        labels = {"level": "Daraja (ishtirok turi)", "description": "Qisqacha izoh (ixtiyoriy)"}

    def __init__(self, *args, semester, **kwargs):
        super().__init__(*args, **kwargs)
        self.semester = semester
        self.fields["criterion"].queryset = Criterion.objects.filter(is_active=True, input_mode=Criterion.InputMode.UPLOAD)
        self.fields["criterion"].empty_label = None
        self.fields["criterion"].error_messages["required"] = "Mezonni tanlang."
        self.fields["level"].queryset = CriterionLevel.objects.filter(criterion__in=self.fields["criterion"].queryset)
        self.fields["level"].required = False
        self.fields["level"].empty_label = "Daraja tanlanmagan"
        self.fields["event_date"].help_text = (
            f"{semester.start_date:%d.%m.%Y} dan bugungacha bo‘lgan sana" if semester else ""
        )
        if self.instance.pk:
            self.fields["remove_files"].choices = [(str(f.pk), f.original_name) for f in self.instance.files.all()]

    def clean_level(self):
        level = self.cleaned_data.get("level")
        criterion = self.cleaned_data.get("criterion")
        if level and criterion and level.criterion_id != criterion.pk:
            raise ValidationError("Daraja tanlangan mezonga tegishli emas.")
        return level

    def clean_event_date(self):
        d = self.cleaned_data["event_date"]
        today = timezone.localdate()
        if d > today:
            raise ValidationError("Sana kelajakda bo‘lishi mumkin emas.")
        if self.semester and not (self.semester.start_date <= d <= self.semester.end_date):
            raise ValidationError(
                f"Sana joriy semestr oralig‘ida bo‘lishi kerak ({self.semester.start_date:%d.%m.%Y} – "
                f"{self.semester.end_date:%d.%m.%Y})."
            )
        return d

    def clean_files(self):
        files = self.cleaned_data.get("files") or []
        self.file_types = []
        errors = []
        for f in files:
            try:
                self.file_types.append((f, validate_upload(f)))
            except ValidationError as e:
                errors.extend(e.messages)
        if errors:
            raise ValidationError(errors)
        return files

    def clean(self):
        cleaned = super().clean()
        kept = 0
        if self.instance.pk:
            removing = set(cleaned.get("remove_files") or [])
            kept = sum(1 for f in self.instance.files.all() if str(f.pk) not in removing)
        new = len(cleaned.get("files") or [])
        if kept + new > MAX_FILES:
            self.add_error("files", f"Bitta yutuqqa ko‘pi bilan {MAX_FILES} ta fayl biriktiriladi.")
        self.total_files = kept + new
        return cleaned


class ReviewForm(forms.Form):
    ACTIONS = {
        "approve": "Tasdiqlash",
        "reject": "Rad etish",
        "return": "Qayta ishlashga qaytarish",
        "comment": "Izoh qoldirish",
    }

    action = forms.ChoiceField(choices=list(ACTIONS.items()))
    points = forms.DecimalField(
        label="Ball", required=False, min_value=Decimal("0"), max_digits=5, decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.5", "inputmode": "decimal"}),
    )
    comment = forms.CharField(
        label="Izoh", required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Talabaga ko‘rinadi. Rad etish va qaytarishda majburiy."}),
    )
    version = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, achievement, **kwargs):
        super().__init__(*args, **kwargs)
        self.achievement = achievement
        self.fields["points"].max_value = achievement.criterion.max_points
        self.fields["points"].widget.attrs["max"] = achievement.criterion.max_points
        if not self.is_bound:
            self.initial["version"] = version_of(achievement)
            if achievement.points is not None:
                self.initial["points"] = achievement.points
            elif achievement.level:
                self.initial["points"] = achievement.level.points

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get("action")
        comment = (cleaned.get("comment") or "").strip()
        cleaned["comment"] = comment
        if action == "approve":
            pts = cleaned.get("points")
            if pts is None:
                self.add_error("points", "Tasdiqlash uchun ball kiriting.")
            elif pts <= 0:
                self.add_error("points", "Ball 0 dan katta bo‘lishi kerak.")
            elif pts > self.achievement.criterion.max_points:
                self.add_error("points", f"Bu mezonda ko‘pi bilan {self.achievement.criterion.max_points} ball.")
        elif action in ("reject", "return", "comment") and not comment:
            self.add_error("comment", "Izoh yozing: talaba nimani tuzatishi kerakligini bilishi kerak.")
        if cleaned.get("version") and cleaned["version"] != version_of(self.achievement):
            raise ValidationError("Bu yutuq siz sahifani ochganingizdan keyin o‘zgartirilgan. Yangilangan holatni ko‘rib, qaytadan qaror qiling.")
        return cleaned


def version_of(achievement):
    """Bir vaqtda ikki mas'ul baholaganda ustma-ust yozilmasligi uchun."""
    return f"{achievement.updated_at.timestamp():.6f}"


class CriterionRowForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ["short_title", "max_points", "order", "is_active"]
        widgets = {
            "short_title": forms.TextInput(attrs={"maxlength": 40}),
            "max_points": forms.NumberInput(attrs={"min": 1, "max": 100, "inputmode": "numeric"}),
            "order": forms.NumberInput(attrs={"min": 0, "max": 99, "inputmode": "numeric"}),
        }


class BaseCriterionFormSet(forms.BaseModelFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        total = sum(f.cleaned_data["max_points"] for f in self.forms if f.cleaned_data.get("is_active"))
        if total != 100:
            raise ValidationError(f"Faol mezonlar maksimal ballari yig‘indisi 100 bo‘lishi kerak, hozir {total}.")


CriterionFormSet = forms.modelformset_factory(Criterion, form=CriterionRowForm, formset=BaseCriterionFormSet, extra=0)


class CriterionDetailForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ["title", "short_title", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class BaseLevelFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for f in self.forms:
            if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("points") is not None:
                if f.cleaned_data["points"] > self.instance.max_points:
                    f.add_error("points", f"Mezon maksimumidan ({self.instance.max_points}) oshmasin.")


LevelFormSet = forms.inlineformset_factory(
    Criterion, CriterionLevel, formset=BaseLevelFormSet, fields=["title", "points", "order"], extra=2, can_delete=True,
    widgets={"points": forms.NumberInput(attrs={"step": "0.5", "min": 0}), "order": forms.NumberInput(attrs={"min": 0})},
)
