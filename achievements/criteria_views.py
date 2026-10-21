"""Rahbariyat uchun mezonlar muharriri. Maksimal ball o'zgarsa joriy semestr ballari qayta hisoblanadi."""
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from audit.services import log_action
from core.permissions import leadership_required
from ratings.services import recalculate_semester
from structure.models import Semester

from .forms import CriterionDetailForm, CriterionFormSet, LevelFormSet
from .models import Criterion


def _recalc_current():
    sem = Semester.current()
    if sem and not sem.is_closed:
        return recalculate_semester(sem)
    return 0


@leadership_required
def criteria_list(request):
    qs = Criterion.objects.order_by("order", "id")
    formset = CriterionFormSet(request.POST or None, queryset=qs)
    if request.method == "POST" and formset.is_valid():
        changed = [f for f in formset.forms if f.has_changed()]
        if changed:
            with transaction.atomic():
                formset.save()
                n = _recalc_current()
            names = ", ".join(f.instance.short_title for f in changed)
            log_action(request, "criteria.update", f"Mezonlar o‘zgartirildi: {names}")
            messages.success(request, f"Saqlandi. Joriy semestrda {n} talaba bali qayta hisoblandi.")
        else:
            messages.info(request, "O‘zgarish yo‘q.")
        return redirect("achievements:criteria")
    total = sum(c.max_points for c in qs if c.is_active)
    return render(request, "achievements/criteria_list.html", {"formset": formset, "total": total})


@leadership_required
def criterion_edit(request, pk):
    criterion = get_object_or_404(Criterion, pk=pk)
    form = CriterionDetailForm(request.POST or None, instance=criterion)
    levels = LevelFormSet(request.POST or None, instance=criterion)
    if request.method == "POST" and form.is_valid() and levels.is_valid():
        with transaction.atomic():
            form.save()
            levels.save()
        log_action(request, "criteria.update", f"Mezon tahrirlandi: {criterion.short_title}", obj=criterion)
        messages.success(request, "Mezon saqlandi.")
        return redirect("achievements:criteria")
    return render(request, "achievements/criterion_edit.html", {"criterion": criterion, "form": form, "levels": levels})
