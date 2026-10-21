from structure.models import Semester

from .models import SiteSettings
from .nav import build_nav


def site(request):
    ctx = {"site": SiteSettings.load()}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        groups, bottom = build_nav(user)
        path = request.path
        for _, items in groups:
            for item in items:
                item["active"] = path == item["match"] or (item["match"] != "/" and path.startswith(item["match"]))
        ctx.update(
            nav_groups=groups,
            bottom_nav=bottom,
            unread_count=user.notifications.filter(is_read=False).count(),
            current_semester=Semester.current(),
        )
    return ctx
