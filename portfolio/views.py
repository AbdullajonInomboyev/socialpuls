from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header

from accounts.models import Role, User
from audit.services import log_action
from core.models import SiteSettings
from core.permissions import scoped_students

from .pdf import build_pdf
from .services import build


def _student_for(request, pk):
    """Talaba faqat o'zini, xodim faqat o'z doirasidagi talabani ko'radi; boshqa holat 404."""
    user = request.user
    if user.pk == pk and user.role == Role.STUDENT:
        return User.objects.select_related("profile__faculty", "profile__specialty", "profile__group").get(pk=pk)
    if user.role == Role.STUDENT:
        raise Http404
    return get_object_or_404(
        scoped_students(user).select_related("profile__faculty", "profile__specialty", "profile__group"), pk=pk
    )


@login_required
def me(request):
    if request.user.role != Role.STUDENT:
        return redirect("ratings:rating")
    return detail(request, request.user.pk)


@login_required
def detail(request, pk):
    student = _student_for(request, pk)
    pf = build(student)
    return render(request, "portfolio/detail.html", {"pf": pf, "own": student.pk == request.user.pk})


@login_required
def download(request, pk):
    student = _student_for(request, pk)
    pf = build(student)
    data = build_pdf(pf, SiteSettings.load().university_name)
    if student.pk != request.user.pk:
        log_action(request, "portfolio.download", f"Portfolio yuklab olindi: {student.full_name}", obj=student)
    name = f"portfolio-{student.hemis_id or student.pk}-{timezone.localdate():%Y%m%d}.pdf"
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = content_disposition_header(request.GET.get("ochish") != "1", name)
    return resp
