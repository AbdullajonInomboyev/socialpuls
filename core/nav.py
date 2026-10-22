"""Rolga qarab menyu. Faqat mavjud va ruxsat berilgan sahifalar chiqadi."""
from django.urls import NoReverseMatch, reverse

from accounts.models import REVIEWER_ROLES, Role


def _item(label, url_name, icon, key="", match=None):
    try:
        url = reverse(url_name)
    except NoReverseMatch:
        return None
    return {"label": label, "url": url, "icon": icon, "key": key, "match": match or url}


def build_nav(user):
    if not user.is_authenticated:
        return [], []
    if user.role == Role.STUDENT:
        items = [
            _item("Bosh sahifa", "core:home", "home"),
            _item("Yutuqlarim", "achievements:my_list", "award", match="/yutuqlar/"),
            _item("Portfolio", "portfolio:me", "briefcase", match="/portfolio/"),
            _item("TOP-10", "ratings:top10", "trophy"),
            _item("Eslatmalar", "notifications:list", "bell", key="notifications"),
            _item("Profil", "accounts:profile", "user"),
        ]
        items = [i for i in items if i]
        # Yutuq qo'shish tugmasi "Yutuqlarim" sahifasida; pastki panelda 5 ta asosiy bo'lim.
        bottom = [i for i in items if i["icon"] != "trophy"]
        return [("", items)], bottom

    main = [_item("Bosh sahifa", "core:home", "home")]
    if user.role in REVIEWER_ROLES:
        main.append(_item("Tekshiruv navbati", "achievements:queue", "clipboard", key="queue"))
        main.append(_item("Qo‘lda baholash", "achievements:manual", "edit"))
    else:
        main.append(_item("Yutuqlar", "achievements:queue", "award"))
    main.append(_item("Eslatmalar", "notifications:list", "bell", key="notifications"))
    main.append(_item("Ommaviy xabar", "core:manage_broadcasts", "megaphone"))
    groups = [("", main)]
    groups.append(("Reyting", [
        _item("Reyting", "ratings:rating", "list", match="/reyting/"),
        _item("TOP-10", "ratings:top10", "trophy"),
        _item("Tahlil", "ratings:analytics", "chart"),
    ]))
    if user.role in (Role.LEADERSHIP, Role.MODERATOR) or user.is_superuser:
        manage = []
        if user.role == Role.LEADERSHIP or user.is_superuser:
            manage.append(_item("Mezonlar", "achievements:criteria", "layers", match="/sozlamalar/mezonlar/"))
        manage += [
            _item("HEMIS", "core:manage_hemis", "database", match="/boshqaruv/hemis/"),
            _item("Xodimlar", "core:manage_staff", "users", match="/boshqaruv/xodimlar/"),
            _item("Tizim sozlamalari", "core:manage_settings", "settings"),
            _item("Amallar jurnali", "core:manage_audit", "scroll"),
        ]
        groups.append(("Boshqaruv", manage))
    account = [_item("Profil", "accounts:profile", "user")]
    if user.is_superuser:
        account.append(_item("Django admin", "admin:index", "shield"))
    groups.append(("Hisob", account))
    groups = [(title, [i for i in items if i]) for title, items in groups]
    return [g for g in groups if g[1]], []
