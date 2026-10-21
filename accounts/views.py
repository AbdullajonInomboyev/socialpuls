from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from audit.services import client_ip, log_action

from . import ratelimit
from .forms import NotificationSettingsForm, StaffLoginForm, StaffPasswordResetForm, StudentLoginForm


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return None


@sensitive_post_parameters("password")
@csrf_protect
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    mode = "staff" if request.GET.get("xodim") or request.POST.get("mode") == "staff" else "student"
    FormClass = StaffLoginForm if mode == "staff" else StudentLoginForm
    ip = client_ip(request)
    locked = False

    if request.method == "POST":
        ident = request.POST.get("username" if mode == "staff" else "login", "")[:150]
        if ratelimit.is_locked(ip, ident):
            locked = True
            form = FormClass(request)
            log_action(request, "login.locked", f"Kirish vaqtincha bloklandi: {ident}", login=ident)
        else:
            form = FormClass(request, data=request.POST)
            if form.is_valid():
                user = form.user
                ratelimit.reset(ip, ident)
                login(request, user)
                log_action(request, "login.success", f"Tizimga kirdi ({'xodim' if mode == 'staff' else 'HEMIS'})")
                return redirect(_safe_next(request) or "core:home")
            ratelimit.register_failure(ip, ident)
            log_action(request, "login.failed", f"Muvaffaqiyatsiz kirish urinishi: {ident}", login=ident, mode=mode)
    else:
        form = FormClass(request)

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "mode": mode,
            "locked": locked,
            "next": _safe_next(request) or "",
        },
    )


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_action(request, "logout", "Tizimdan chiqdi")
    logout(request)
    messages.success(request, "Tizimdan chiqdingiz.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    user = request.user
    form = NotificationSettingsForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(request, "profile.update", "Bildirishnoma sozlamalarini o'zgartirdi", obj=user)
        messages.success(request, "Sozlamalar saqlandi.")
        return redirect("accounts:profile")
    profile = getattr(user, "profile", None) if user.is_student else None
    from notifications import telegram

    return render(
        request, "accounts/profile.html",
        {"form": form, "profile": profile, "telegram_link": telegram.link_url(user), "telegram_ready": telegram.is_configured()},
    )


class PasswordResetView(auth_views.PasswordResetView):
    form_class = StaffPasswordResetForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "password.reset", "Parolni email orqali tikladi", actor=form.user, obj=form.user)
        return response


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_student:
            messages.info(request, "Talabalar parolni HEMIS tizimida o'zgartiradi.")
            return redirect("accounts:profile")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_action(self.request, "password.change", "Parolini o'zgartirdi", obj=self.request.user)
        messages.success(self.request, "Parol o'zgartirildi.")
        return response
