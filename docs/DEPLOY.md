# Production’ga o‘rnatish

Ubuntu 22.04/24.04 serverga o‘rnatish ketma-ketligi: Nginx (HTTPS), Gunicorn (systemd), PostgreSQL. Bu qadamlar
sinov serverida (Ubuntu 24.04, nginx 1.24, PostgreSQL 16) boshidan oxirigacha bajarib tekshirilgan.

Quyidagi misollarda domen `puls.namdu.uz`, kod `/srv/socialpuls`, maxfiy hujjatlar `/var/lib/socialpuls/private_media`.

## 1. Paketlar va foydalanuvchi

```bash
sudo apt update
sudo apt install -y python3 python3-venv postgresql nginx certbot
sudo useradd --system --home /srv/socialpuls --shell /usr/sbin/nologin socialpuls
sudo mkdir -p /srv/socialpuls /var/lib/socialpuls/private_media /var/log/socialpuls /var/backups/socialpuls
```

Python 3.12 yoki undan yangisi kerak (ishlab chiqish 3.13 da bo‘lgan).

## 2. PostgreSQL

```bash
sudo -u postgres psql -c "CREATE ROLE socialpuls LOGIN PASSWORD 'KUCHLI_PAROL';"
sudo -u postgres psql -c "CREATE DATABASE socialpuls OWNER socialpuls;"
```

## 3. Kod va virtual muhit

```bash
sudo unzip socialpuls.zip -d /tmp && sudo cp -r /tmp/socialpuls/. /srv/socialpuls/
cd /srv/socialpuls
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.lock   # sinovdan o‘tgan aniq versiyalar
sudo cp .env.example .env
sudo nano .env        # quyidagi bo‘limga qarang
sudo chown -R socialpuls:socialpuls /srv/socialpuls /var/lib/socialpuls /var/log/socialpuls /var/backups/socialpuls
sudo chmod 600 /srv/socialpuls/.env
```

### `.env` da albatta to‘ldiriladiganlar

| Kalit | Izoh |
| --- | --- |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`. Kamida 40 belgi, aks holda ilova ishga tushmaydi. |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL` | domen; `SITE_URL` email va Telegram xabaridagi havolalar uchun |
| `ADMIN_URL` | Django admin manzili, taxmin qilinmaydigan qiymat (masalan `boshqaruv-7f3k9q/`) |
| `DATABASE_URL` | `postgres://socialpuls:KUCHLI_PAROL@127.0.0.1:5432/socialpuls` |
| `CACHE_URL` | `dbcache://socialpuls_cache` (barcha gunicorn jarayonlari uchun umumiy kesh) |
| `HEMIS_API_TOKEN` | HEMIS ma’lumot API tokeni (talabalar ro‘yxatini sinxronlash uchun) |
| `EMAIL_*` | SMTP: parol o‘rnatish havolalari va bildirishnomalar |
| `TELEGRAM_*` | ixtiyoriy; bot ulanmasa Telegram tugmasi ko‘rinmaydi |

Izohlarni faqat alohida qatorga yozing: `KALIT=qiymat  # izoh` ko‘rinishida izoh qiymatning bir qismi bo‘lib qoladi.
`.env` ni ilova o‘zi o‘qiydi (`manage.py`, gunicorn), uni `source` qilish shart emas.

## 4. Baza, statik fayllar va birinchi rahbar hisobi

```bash
cd /srv/socialpuls
sudo -u socialpuls bash -c '.venv/bin/python manage.py migrate
  .venv/bin/python manage.py createcachetable
  .venv/bin/python manage.py collectstatic --noinput
  .venv/bin/python manage.py check --deploy'
```

`check --deploy` da faqat sozlanmagan narsalar haqida ogohlantirish qolishi kerak (masalan, token hali berilmagan bo‘lsa
`socialpuls.W003`).

Birinchi rahbariyat hisobi (parol ikki marta so‘raladi; `--superuser` Django admin panelini ham ochadi):

```bash
sudo -u socialpuls bash -c '.venv/bin/python manage.py create_staff --username rahbar --email rahbar@namdu.uz \
    --last-name Familiya --first-name Ism --superuser'
```

Qolgan xodimlar tizim ichida yaratiladi: `Boshqaruv → Xodimlar`.

## 5. Gunicorn (systemd)

```bash
sudo cp deploy/socialpuls.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now socialpuls
sudo systemctl status socialpuls
```

Kod yangilangandan keyin: `sudo systemctl reload socialpuls`.

## 6. Nginx va HTTPS

```bash
sudo mkdir -p /var/www/letsencrypt
sudo certbot certonly --webroot -w /var/www/letsencrypt -d puls.namdu.uz   # birinchi marta 80-port ochiq bo‘lsin
sudo cp deploy/nginx-socialpuls.conf /etc/nginx/sites-available/socialpuls
sudo ln -s /etc/nginx/sites-available/socialpuls /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Sertifikat hali bo‘lmasa, avval faqat 80-port blokini qoldirib sertifikat oling, keyin to‘liq faylni qo‘ying.
Server IPv6 ni qo‘llamasa, `listen [::]:...` qatorlarini o‘chiring.

Konfiguratsiyadagi muhim joylar:

* `/protected/` `internal`: yutuq hujjatlari faqat Django ruxsat bergandan keyin `X-Accel-Redirect` orqali beriladi.
* `proxy_set_header X-Real-IP $remote_addr`: ilova mijoz IP sini faqat shu sarlavhadan oladi (kirish cheklovi va audit).
  Gunicorn tashqariga ochilmasin: u faqat `unix:/run/socialpuls/gunicorn.sock` da tinglaydi.
* `client_max_body_size 60m`: 5 ta fayl × 10 MB.

## 7. Rejalashtirilgan vazifalar va zaxira

```bash
sudo cp deploy/cron-socialpuls /etc/cron.d/socialpuls
sudo chmod 644 /etc/cron.d/socialpuls
```

Ishlaydigan vazifalar: kechasi HEMIS sinxroni, oyning 1-kuni eslatma, kunlik zaxira (`deploy/backup.sh`: `pg_dump` +
hujjatlar arxivi, 14 kun saqlanadi), haftalik sessiya tozalash. Zaxirani boshqa serverga ham nusxalab turing.

Zaxiradan tiklash:

```bash
sudo -u postgres createdb -O socialpuls socialpuls_restore
pg_restore --no-owner -d postgres://socialpuls:PAROL@127.0.0.1/socialpuls_restore /var/backups/socialpuls/db-YYYYMMDD-HHMM.dump
sudo tar -xzf /var/backups/socialpuls/files-YYYYMMDD-HHMM.tar.gz -C /var/lib/socialpuls/
```

## 8. Birinchi kun sozlamalari (brauzerda, rahbar hisobi bilan)

1. `Boshqaruv → Tizim sozlamalari`: o‘quv yili va ikki semestr sanalarini kiriting, kerakli semestrda “Joriy qilish”.
2. `Boshqaruv → HEMIS`: “Hozir sinxronlash” (token bo‘lsa) yoki Excel shablon orqali talabalarni yuklash.
3. `Boshqaruv → Xodimlar`: fakultet mas’ullari, tyutorlar va moderatorlar.
4. `Mezonlar`: ballar va darajalarni universitet nizomiga moslang (faol mezonlar yig‘indisi 100).
5. Telegram bot bo‘lsa, webhook’ni o‘rnating (README, “Telegram bot” bo‘limi).

## 9. Yangilash

```bash
cd /srv/socialpuls
sudo -u socialpuls deploy/backup.sh
# yangi kodni ustidan ko‘chiring (.env, .venv tegilmaydi)
sudo .venv/bin/pip install -r requirements.lock
sudo -u socialpuls bash -c '.venv/bin/python manage.py migrate && .venv/bin/python manage.py collectstatic --noinput'
sudo systemctl reload socialpuls
```

## Loglar

* Ilova: `/var/log/socialpuls/socialpuls.log` (5 MB × 5 aylanma), `journalctl -u socialpuls`
* Cron va zaxira: `/var/log/socialpuls/cron.log`, `backup.log`
* Nginx: `/var/log/nginx/socialpuls.*.log`
