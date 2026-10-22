# Render’da namoyish sayti

`render.yaml` loyihani Render’da **namoyish (demo) sayti** sifatida ko‘taradi: sinov talabalari, demo xodimlar va
avtomatik yaratilgan ma’lumotlar bilan. Har sahifada “Namoyish versiyasi” ogohlantirishi ko‘rinadi, kirish sahifasida
demo loginlar yoziladi. Haqiqiy foydalanish uchun `docs/DEPLOY.md` dagi server yo‘li tavsiya etiladi.

## Joylash

1. Kod GitHub repozitoriyasida bo‘lsin (`render.yaml` ildizda).
2. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → GitHub’ni ulang va repozitoriyani tanlang.
3. Render `socialpuls` veb-xizmatini va `socialpuls-db` PostgreSQL bazasini ko‘rsatadi → **Apply**.
4. Birinchi build 3–5 daqiqa davom etadi. Tugagach, sayt `https://socialpuls-XXXX.onrender.com` manzilida ochiladi
   (aniq manzil xizmat sahifasining yuqorisida).

`SECRET_KEY` ni Render o‘zi yaratadi; `.env` fayli kerak emas, barcha sozlamalar `render.yaml` da.

## Demo loginlar

| Kim | Login | Parol |
| --- | --- | --- |
| Rahbariyat | `rahbar` | `Puls-demo-2026` |
| Moderator | `moderator` | `Puls-demo-2026` |
| Fakultet mas’uli | `dekan_iqt`, `dekan_fil` | `Puls-demo-2026` |
| Tyutor | `tyutor` | `Puls-demo-2026` |
| Talaba (Filologiya) | `309251104207` | `hemis-demo` |
| Talaba (Iqtisodiyot) | `309251104208` | `hemis-demo` |

Xodimlar “Xodim” yorlig‘idan, talabalar “Talaba” yorlig‘idan kiradi.

## Bepul tarifning cheklovlari

* **Uyquga ketadi.** 15 daqiqa so‘rov bo‘lmasa xizmat to‘xtaydi, keyingi ochilish ~1 daqiqa kutadi. Namoyishdan oldin
  saytni bir marta ochib qo‘ying.
* **Yuklangan fayllar saqlanmaydi.** Xizmat qayta ishga tushganda diskdagi fayllar o‘chadi. Demo sertifikatlar har
  ishga tushishda avtomatik qayta chiziladi, lekin namoyish paytida yuklangan yangi hujjat keyin ochilmaydi
  (yozuv va ball qoladi).
* **Bepul baza 30 kundan keyin o‘chadi.** Render oldindan email yuboradi. Davom ettirish uchun bazani pullik tarifga
  o‘tkazing yoki yangi Blueprint yarating.
* **Email yuborilmaydi.** Xatlar faqat Render loglarida ko‘rinadi (`EMAIL_BACKEND` console).
* **Rejali vazifalar yo‘q.** Tungi HEMIS sinxroni va oylik eslatmalar ishlamaydi (namoyish uchun kerak emas).

## Doimiy foydalanishga o‘tkazish (pullik tarif)

1. Veb-xizmat tarifini **Starter** ga, bazani **Basic** ga o‘tkazing.
2. Xizmatga disk qo‘shing: **Disks** → mount path `/var/data`, 1 GB.
3. Environment’da o‘zgartiring:
   * `PRIVATE_MEDIA_ROOT=/var/data/private_media`
   * `DEMO_SITE=False`, `HEMIS_MODE=live`, `HEMIS_API_TOKEN=...`
   * `EMAIL_BACKEND` ni o‘chiring va `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` ni kiriting
   * `ADMIN_URL` ga taxmin qilinmaydigan qiymat bering
4. Demo ma’lumotlarsiz toza baza kerak bo‘lsa, yangi baza yarating va Shell’da birinchi rahbarni yarating:
   `python manage.py create_staff --username rahbar --email ... --last-name ... --first-name ... --superuser`
5. O‘z domeningiz bo‘lsa: **Settings → Custom Domains**, so‘ng `ALLOWED_HOSTS` va `CSRF_TRUSTED_ORIGINS` ga qo‘shing.

## Texnik izohlar

* Build: `deploy/render/build.sh` (paketlar, `collectstatic`, `migrate`, `createcachetable`).
  Start: `deploy/render/start.sh` (`DEMO_SITE=True` bo‘lsa `seed_demo --if-empty`, so‘ng gunicorn).
* Mijoz IP manzili `X-Forwarded-For` ning Render qo‘shgan oxirgi yozuvidan olinadi (`CLIENT_IP_SOURCE`,
  `PROXY_COUNT`); boshidagi qismni foydalanuvchi soxtalashtirishi mumkin, shuning uchun u e’tiborga olinmaydi.
* Render domeni (`RENDER_EXTERNAL_HOSTNAME`) `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` va `SITE_URL` ga avtomatik qo‘shiladi.
