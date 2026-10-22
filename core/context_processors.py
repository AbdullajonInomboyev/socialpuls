from django.conf import settings

from accounts.models import REVIEWER_ROLES
from structure.models import Semester

from .models import SiteSettings
from .nav import build_nav


def site(request):
    ctx = {"site": SiteSettings.load(), "demo_site": settings.DEMO_SITE}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        groups, bottom = build_nav(user)
        unread = user.notifications.filter(is_read=False).count()
        counts = {"notifications": unread}
        if user.role in REVIEWER_ROLES:
            from achievements.models import Achievement
            from core.permissions import scope_filter

            counts["queue"] = Achievement.objects.filter(
                status=Achievement.Status.PENDING, semester__is_closed=False, **scope_filter(user)
            ).count()
        path = request.path
        # Eng uzun mos keladigan manzil faol bo'ladi ("/yutuqlar/yangi/" da "Yutuqlarim" emas, "Qo'shish").
        all_items = [i for _, items in groups for i in items] + list(bottom)
        best = max((i["match"] for i in all_items if path == i["match"] or (i["match"] != "/" and path.startswith(i["match"]))),
                   key=len, default=None)
        for item in all_items:
            item["active"] = item["match"] == best
            item["count"] = counts.get(item["key"], 0)
        ctx.update(
            nav_groups=groups,
            bottom_nav=bottom,
            unread_count=unread,
            current_semester=Semester.current(),
        )
    return ctx
