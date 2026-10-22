# Social Puls (Ijtimoiy Faollik): yakuniy hisobot

Sana: 2026-yil 22-oktabr. Loyiha noldan yozilgan (prototip kodi ishlatilmagan), 5 bosqichda topshirildi.

## 1. Nima tayyor

| Rol | Imkoniyatlar |
| --- | --- |
| Talaba | HEMIS login/paroli bilan kirish (parol saqlanmaydi), bosh sahifada ball va o‘rin, avtomatik portfolio (sahifa va PDF), yutuq yuklash (mezon, daraja, sana, 1–5 hujjat), qoralama, tahrirlash/o‘chirish (tekshiruvgacha), qaytarilganini tuzatib qayta yuborish, TOP-10 va o‘z o‘rni, eslatmalar, Telegram ulash |
| Tyutor | Faqat biriktirilgan guruhlar: tekshiruv navbati, talaba portfoliosini ko‘rish va yuklab olish, tasdiqlash/rad etish/qaytarish/izoh, qo‘lda baholash, reyting, tahlil, eksport, ommaviy xabar |
| Fakultet mas’uli | Xuddi shu, o‘z fakulteti doirasida |
| Rahbariyat | Butun universitet: reyting, tahlil, PDF/Excel, mezonlar muharriri, boshqaruv bo‘limi (yutuqlarni faqat ko‘radi, baholamaydi) |
| Moderator | HEMIS sinxron va Excel import, xodimlar, tizim sozlamalari, semestrlar, amallar jurnali (rahbariyat hisobiga tegolmaydi) |

Umumiy: 11 mezon, 100 ball; semestr va o‘quv yili (semestrlar o‘rtachasi) bo‘yicha reyting; GPA balli = GPA/5×10;
yopilgan semestr ballari o‘zgarmaydi; email, Telegram va tizim ichidagi bildirishnomalar; oylik eslatma; amallar
jurnali; ochiq JSON statistika (`/api/ochiq/statistika/`); kunduzgi/tungi rejim; telefon ekraniga moslashgan.

## 2. Texnologiya

Python 3.13, Django 5.2, PostgreSQL 16 (lokalda SQLite), server tomonida render qilinadigan sahifalar va oddiy
JavaScript (tashqi CDN yo‘q), Gunicorn + Nginx, reportlab (PDF), openpyxl (Excel), cron. Celery yoki Redis shart emas.

## 3. Fayllar

Loyiha noldan yozilgani uchun barcha fayllar yangi. Jami 198 ta fayl (shriftlar bilan).

| Papka | Vazifasi | Asosiy fayllar |
| --- | --- | --- |
| `config/` | sozlamalar (`.env` dan), URL’lar, WSGI | `settings.py`, `urls.py` |
| `accounts/` | foydalanuvchi va rollar, HEMIS va xodim kirishi, urinishlar cheklovi, profil, parol | `models.py`, `backends.py`, `ratelimit.py`, `views.py`, `management/commands/create_staff.py` |
| `structure/` | fakultet, yo‘nalish, guruh, o‘quv yili, semestr | `models.py` |
| `achievements/` | mezonlar, yutuqlar, hujjatlar, tekshiruv, qo‘lda ball, mezonlar muharriri | `models.py`, `validators.py`, `services.py`, `views.py`, `criteria_views.py`, `migrations/0002_seed_criteria.py` |
| `ratings/` | ball hisoblash, reyting tanlovi, TOP-10, tahlil, ochiq statistika | `services.py`, `selection.py`, `views.py` |
| `reports/` | PDF va Excel eksport, Outfit shrifti (OFL) | `exports.py`, `fonts/` |
| `notifications/` | bildirishnomalar, email/Telegram yetkazish, webhook, oylik eslatma | `delivery.py`, `telegram.py`, `reminders.py`, `views.py` |
| `hemis/` | HEMIS API mijozi, sinxron, Excel import, sinov (mock) ma’lumoti | `client.py`, `services.py`, `sync.py`, `mock.py` |
| `audit/` | amallar jurnali | `models.py`, `services.py` |
| `core/` | bosh sahifalar, menyu, ruxsat yordamchilari, xavfsizlik middleware, boshqaruv sahifalari, deploy tekshiruvlari | `permissions.py`, `middleware.py`, `manage_views.py`, `manage_forms.py`, `nav.py`, `checks.py` |
| `templates/` | 47 ta shablon | `layouts/`, `achievements/`, `ratings/`, `manage/`, `accounts/`, `errors/` |
| `static/` | CSS, JS, logo, shriftlar | `css/app.css`, `js/app.js`, `js/theme.js` |
| `tests/` | 133 ta test | `test_*.py`, `factories.py` |
| `deploy/` | production fayllari | `nginx-socialpuls.conf`, `socialpuls.service`, `gunicorn.conf.py`, `cron-socialpuls`, `backup.sh` |
| `docs/` | yo‘riqnoma va hisobot | `DEPLOY.md`, `HISOBOT.md` |
| ildiz | | `README.md`, `requirements.txt`, `requirements.lock`, `.env.example`, `.gitignore`, `manage.py` |

### 5-bosqichda o‘zgargan fayllar

* Yangi: `accounts/management/commands/create_staff.py`, `core/checks.py`, `requirements.lock`, `deploy/*` (5 ta), `docs/DEPLOY.md`,
  `docs/HISOBOT.md`, `tests/test_security.py`.
* O‘zgargan: `.env.example`, `README.md`, `requirements.txt`, `accounts/ratelimit.py`, `accounts/views.py`,
  `config/settings.py`, `config/urls.py`, `core/apps.py`, `core/middleware.py`.

5-bosqichda topilgan va tuzatilgan xatolar:

* `.env.example` da qiymat yonidagi izohlar (`SECRET_KEY=   # ...`) qiymatga qo‘shilib ketardi: nusxa olingan fayl
  bilan `SECRET_KEY` izoh matniga teng bo‘lib qolardi. Izohlar alohida qatorga ko‘chirildi, ilova esa bunday kalit
  bilan endi ishga tushmaydi.
* PostgreSQL qayta ishga tushganda yoki ulanish uzilganda Gunicorn jarayonlari 500 qaytarardi
  (`CONN_HEALTH_CHECKS` yoqildi, sinab ko‘rildi).
* Django admin kirish formasi urinishlar cheklovini chetlab o‘tardi: endi asosiy kirish sahifasiga yo‘naltiriladi.
* Parol tiklash xatlari cheklanmagan edi; harakatsizlikdan keyingi qayta yo‘naltirishda manzil kodlanmagan edi.
* Production uchun tavsiya qilingan fayl keshi bir nechta jarayonda ishonchsiz edi: baza keshiga almashtirildi.
* O‘chirilgan: `static/vendor/` (ishlatilmagan Chart.js; grafiklar HTML/CSS da) va oldingi zip’ga tasodifan tushib qolgan
  `fonttools` paketi.

## 4. Test natijalari

| Tekshiruv | Natija |
| --- | --- |
| Avtomatik testlar, SQLite | 133 ta, hammasi o‘tdi (230 s) |
| Avtomatik testlar, PostgreSQL 16 | 133 ta, hammasi o‘tdi (234 s) |
| Toza muhitda `pip install -r requirements.txt` (eng yangi versiyalar) + testlar | 133 ta o‘tdi; aniq versiyalar `requirements.lock` da |
| README bo‘yicha lokal ishga tushirish (toza nusxada) | `migrate`, `seed_demo`, `check` xatosiz |
| `manage.py check --deploy` (production `.env`) | faqat `socialpuls.W003`: HEMIS tokeni berilmagan |
| Brauzer ssenariysi production rejimida (Nginx + HTTPS + Gunicorn 4 jarayon + PostgreSQL, `DEBUG=False`) | 22/22 |
| Zaxira (`deploy/backup.sh`) va yangi bazaga tiklash | ishladi, ma’lumot to‘liq tiklandi |
| PostgreSQL qayta ishga tushganda ilova | xatosiz davom etdi |

Brauzer ssenariysi: rahbar o‘quv yili va semestr ochadi, Excel’dan 3 talabani import qiladi, fakultet mas’ulini
yaratadi; talaba telefonda yutuq va rasm yuklaydi, faylini ko‘radi (Nginx X-Accel orqali), reytingga kira olmaydi;
boshqa fakultet talabasi bu yutuq va faylni ocha olmaydi (404); fakultet mas’uli tasdiqlaydi, reytingda faqat o‘z
fakultetini ko‘radi, boshqaruvga kira olmaydi (403); rahbar PDF va Excel yuklaydi, amallar jurnalida qaror, import va
eksport yozilgan; 5 marta noto‘g‘ri paroldan keyin to‘g‘ri parol ham vaqtincha qabul qilinmaydi. Barcha sahifalarda
brauzer konsolida JavaScript xatosi yo‘q.

Testlar qamrovi: kirish va bloklash, rollar va doiralar (tyutor faqat o‘z guruhi), fayl tekshiruvi (soxta kengaytma,
PDF ichidagi JavaScript), ish jarayoni va bir vaqtda baholash, ball hisoblash va qayta hisoblash, reyting va teng
o‘rinlar, eksport (Excel formula hujumidan himoya), HEMIS ma’lumotini o‘qish, sinxron va import, email/Telegram
yetkazish, webhook imzosi, oylik eslatma, ommaviy xabar doirasi va limiti, xodim va semestr boshqaruvi, audit
filtrlari, xavfsizlik sarlavhalari.

## 5. Xavfsizlik

* Maxfiy qiymatlar faqat `.env` da (git’ga kirmaydi); `DEBUG=False` da qisqa yoki noto‘g‘ri `SECRET_KEY` bilan ilova
  ishga tushmaydi; `HEMIS_MODE=mock` production’da taqiqlangan.
* HTTPS majburiy, HSTS, xavfsiz cookie, CSP (`script-src 'self'`), clickjacking va MIME himoyasi.
* Har bir ruxsat server tomonida tekshiriladi (`core/permissions.py`); menyu faqat qulaylik uchun.
* Hujjatlar ochiq papkada emas: ruxsat tekshiruvidan keyin X-Accel orqali beriladi; fayl turi ichidagi baytlardan
  aniqlanadi; xavfli PDF’lar rad etiladi.
* Kirish urinishlari IP va login bo‘yicha cheklanadi (umumiy kesh orqali barcha jarayonlarda); Django admin ham shu
  sahifa orqali kiradi va manzili `.env` da o‘zgartiriladi; parol tiklash xatlari soatiga cheklangan.
* Excel import XML hujumlaridan himoyalangan (`defusedxml`); eksportda formula hujumi oldi olinadi.
* Muhim amallar (kirish, qaror, eksport, sozlama, xodim, semestr, import, xabar) o‘chirib bo‘lmaydigan jurnalga yoziladi.

## 6. Cheklovlar va ochiq masalalar

1. **HEMIS haqiqiy API bilan sinalmagan.** Token berilmagan. Talaba kirishi va sinxron HEMIS’ning ochiq hujjatlaridagi
   formatga (`/auth/login`, `/account/me`, `data/student-list` va boshqalar) qarab yozilgan va sinov ma’lumotida
   tekshirilgan. Token berilgach birinchi sinxronni kuzatib, maydon nomlarini tasdiqlash kerak.
2. **SMTP va Telegram haqiqiy hisob bilan sinalmagan**: testlarda soxta (mock) javob ishlatilgan.
3. **Rasmiy NamDU logotipi yo‘q**: `static/img/logo.svg` vaqtinchalik belgi.
4. Mezon va daraja ballari texnik topshiriqdan olingan; universitet nizomiga mosligini rahbariyat tekshirib,
   `Mezonlar` sahifasida to‘g‘rilashi mumkin.
5. Yuklangan fayllar antivirusdan o‘tkazilmaydi (faqat tur va PDF tarkibi tekshiriladi). Kerak bo‘lsa ClamAV qo‘shiladi.
6. Bitta server uchun mo‘ljallangan (cron, baza keshi). Bir nechta serverga kengaytirishda Redis va umumiy fayl ombori kerak.
7. Yuklama (load) testi o‘tkazilmagan; brauzer sinovi faqat Chromium’da qilingan.
8. Interfeys faqat o‘zbek (lotin) tilida.
9. Oylik eslatma o‘tgan oyda yutuq yubormaganlarning hammasiga ketadi, shu oy ichida tizimga endi qo‘shilgan talabalarga ham.
