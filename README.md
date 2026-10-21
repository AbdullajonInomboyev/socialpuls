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

## Yutuqlar va baholash (2-bosqich)

* Talaba: `Yutuqlarim` va `Yutuq qo‘shish`. Mezon, daraja, sana (joriy semestr ichida, kelajakda emas), izoh va
  1–5 ta hujjat (PDF, JPG, PNG, WEBP; har biri `UPLOAD_MAX_MB` gacha). Qoralama sifatida saqlash yoki tekshiruvga yuborish.
  Qaytarilgan yutuqni tuzatib qayta yuboradi; qoralama va hali tekshirilmaganini o‘chira oladi.
* Fayl turi kengaytmaga emas, birinchi baytlarga qarab aniqlanadi; rasm Pillow bilan ochib ko‘riladi, ichida skript yoki
  biriktirilgan fayl bor PDF rad etiladi. Fayllar `PRIVATE_MEDIA_ROOT` da (ochiq URL’siz) saqlanadi va faqat egasi hamda
  doirasidagi xodimlarga `/fayl/<id>/` orqali ruxsat tekshiruvidan keyin beriladi.
* Fakultet mas’uli va tyutor: `Tekshiruv navbati` (eng eski yuborilgan birinchi), tasdiqlash (ball mezon maksimumidan
  oshmaydi), rad etish va qaytarish (izoh majburiy), tasdiqlangan ballni o‘zgartirish. Har qaror tarixga, audit jurnaliga
  yoziladi, talabaga bildirishnoma boradi va ball darhol qayta hisoblanadi. Ikki mas’ul bir vaqtda baholasa, ikkinchisiga
  “o‘zgartirilgan” xabari chiqadi.
* `Qo‘lda baholash`: odob-axloq va davomat ballari guruh jadvalida kiritiladi (bo‘sh katak = ball yo‘q).
* Rahbariyat va moderator yutuqlarni faqat ko‘radi. Yopilgan semestrda hech narsa o‘zgarmaydi.

Production’da fayllarni Nginx beradi (`USE_X_ACCEL_REDIRECT=True`):

```nginx
location /protected/ {
    internal;
    alias /var/lib/socialpuls/private_media/;
}
client_max_body_size 60m;
```

## Testlar

```bash
python manage.py test tests
```

To'liq o'rnatish va production yo'riqnomasi 5-bosqichda qo'shiladi.
