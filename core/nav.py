"""Rolga qarab menyu. Faqat mavjud va ruxsat berilgan sahifalar chiqadi."""
from django.urls import NoReverseMatch, reverse

from accounts.models import Role


def _item(label, url_name, icon, match=None):
    try:
        url = reverse(url_name)
    except NoReverseMatch:
        return None
    return {"label": label, "url": url, "icon": icon, "match": match or url}


def build_nav(user):
    if not user.is_authenticated:
        return [], []
    if user.role == Role.STUDENT:
        items = [
            _item("Bosh sahifa", "core:home", "home"),
            _item("Eslatmalar", "notifications:list", "bell"),
            _item("Profil", "accounts:profile", "user"),
        ]
        items = [i for i in items if i]
        return [("", items)], items  # pastki mobil menyu uchun ham shu ro'yxat

    groups = [("", [_item("Bosh sahifa", "core:home", "home"), _item("Eslatmalar", "notifications:list", "bell")])]
    account = [_item("Profil", "accounts:profile", "user")]
    if user.is_superuser:
        account.append(_item("Django admin", "admin:index", "shield"))
    groups.append(("Hisob", account))
    groups = [(title, [i for i in items if i]) for title, items in groups]
    return [g for g in groups if g[1]], []
