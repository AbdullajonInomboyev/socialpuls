"""HEMIS REST API mijozi.

Ikki xil kirish:
* Talaba API (`/auth/login`, `/account/me`) — talabaning o'z login/paroli bilan, tizimga kirishda.
* Ma'lumotlar API (`/data/...`) — universitet API tokeni bilan, ommaviy sinxronizatsiya uchun.

HEMIS_MODE=mock bo'lsa (faqat DEBUG), tarmoqqa chiqmasdan `hemis.mock` dagi test ma'lumotlari ishlatiladi.
"""
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger("socialpuls.hemis")


class HemisError(Exception):
    """HEMIS bilan bog'lanishda umumiy xatolik."""


class HemisAuthError(HemisError):
    """Login yoki parol noto'g'ri."""


class HemisUnavailable(HemisError):
    """HEMIS javob bermadi yoki kutilmagan javob qaytardi."""


def _url(base, path):
    return urljoin(base if base.endswith("/") else base + "/", path.lstrip("/"))


def _json(resp):
    try:
        return resp.json()
    except ValueError as exc:
        raise HemisUnavailable("HEMIS JSON bo'lmagan javob qaytardi.") from exc


class HemisStudentClient:
    def __init__(self, base_url=None, timeout=None):
        self.base_url = base_url or settings.HEMIS_STUDENT_API_URL
        self.timeout = timeout or settings.HEMIS_TIMEOUT

    def login(self, login, password):
        """Muvaffaqiyatli bo'lsa token qaytaradi."""
        try:
            resp = requests.post(
                _url(self.base_url, "auth/login"),
                json={"login": login, "password": password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("HEMIS login so'rovi bajarilmadi: %s", exc)
            raise HemisUnavailable("HEMIS bilan bog'lanib bo'lmadi.") from exc
        if resp.status_code in (400, 401, 403, 422):
            raise HemisAuthError("Login yoki parol noto'g'ri.")
        if resp.status_code >= 500:
            raise HemisUnavailable(f"HEMIS xatolik qaytardi ({resp.status_code}).")
        data = _json(resp)
        if not data.get("success"):
            raise HemisAuthError(data.get("error") or "Login yoki parol noto'g'ri.")
        token = (data.get("data") or {}).get("token")
        if not token:
            raise HemisUnavailable("HEMIS token qaytarmadi.")
        return token

    def me(self, token):
        try:
            resp = requests.get(
                _url(self.base_url, "account/me"),
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise HemisUnavailable("HEMIS bilan bog'lanib bo'lmadi.") from exc
        if resp.status_code != 200:
            raise HemisUnavailable(f"HEMIS profilni bermadi ({resp.status_code}).")
        data = _json(resp)
        if not data.get("success") or not isinstance(data.get("data"), dict):
            raise HemisUnavailable("HEMIS profil javobi noto'g'ri.")
        return data["data"]


class HemisDataClient:
    """Universitet API tokeni bilan sahifalab ma'lumot oluvchi mijoz."""

    def __init__(self, base_url=None, token=None, timeout=None):
        self.base_url = base_url or settings.HEMIS_DATA_API_URL
        self.token = token if token is not None else settings.HEMIS_API_TOKEN
        self.timeout = timeout or settings.HEMIS_TIMEOUT

    def iter_items(self, path, params=None, limit=200, max_pages=500):
        if not self.token:
            raise HemisError("HEMIS_API_TOKEN sozlanmagan.")
        page = 1
        while page <= max_pages:
            query = {"limit": limit, "page": page, **(params or {})}
            try:
                resp = requests.get(
                    _url(self.base_url, path),
                    params=query,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                raise HemisUnavailable("HEMIS bilan bog'lanib bo'lmadi.") from exc
            if resp.status_code == 401:
                raise HemisError("HEMIS API tokeni yaroqsiz.")
            if resp.status_code != 200:
                raise HemisUnavailable(f"HEMIS xatolik qaytardi ({resp.status_code}).")
            data = _json(resp)
            payload = data.get("data") or {}
            items = payload.get("items") if isinstance(payload, dict) else payload
            for item in items or []:
                yield item
            pagination = payload.get("pagination") if isinstance(payload, dict) else None
            if not pagination or page >= int(pagination.get("pageCount") or 1):
                break
            page += 1


def get_student_client():
    if settings.HEMIS_MODE == "mock":
        from .mock import MockStudentClient

        return MockStudentClient()
    return HemisStudentClient()


def get_data_client():
    if settings.HEMIS_MODE == "mock":
        from .mock import MockDataClient

        return MockDataClient()
    return HemisDataClient()
