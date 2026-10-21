# Social Puls (Ijtimoiy Faollik)

Namangan davlat universiteti talabalarining ijtimoiy faolligini 11 mezon bo'yicha (jami 100 ball) baholash platformasi.
Django 5.2, server tomonda render qilinadigan sahifalar, PostgreSQL (lokalda SQLite).

## Lokal ishga tushirish

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # keyin .env da: DEBUG=True, HEMIS_MODE=mock, SECRET_KEY=...
python manage.py migrate
python manage.py seed_demo    # demo fakultetlar, xodimlar, talabalar (faqat DEBUG)
python manage.py runserver
```

Demo kirish (faqat `seed_demo` dan keyin):

| Rol | Login | Parol |
| --- | --- | --- |
| Rahbariyat | `rahbar` | `Puls-demo-2026` |
| Moderator | `moderator` | `Puls-demo-2026` |
| Fakultet mas'uli | `dekan_iqt` | `Puls-demo-2026` |
| Tyutor | `tyutor` | `Puls-demo-2026` |
| Talaba (HEMIS test) | `309251104207` yoki `309251104208` | `hemis-demo` |

## Testlar

```bash
python manage.py test tests
```

To'liq o'rnatish va production yo'riqnomasi 5-bosqichda qo'shiladi.
