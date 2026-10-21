"""TZ dagi 11 ta baholash mezoni (jami 100 ball) va namunaviy darajalar."""
from decimal import Decimal

from django.db import migrations

CRITERIA = [
    ("kitobxonlik", "Kitobxonlik madaniyati", "Kitobxonlik", 20, "upload"),
    ("tashabbus", "“5 muhim tashabbus” doirasidagi to‘garaklarda faol ishtiroki", "5 tashabbus", 20, "upload"),
    ("akademik", "Talabaning akademik o‘zlashtirishi", "Akademik o‘zlashtirish", 10, "auto"),
    ("odob", "Oliy ta’lim tashkilotining ichki tartib qoidalari va Odob-axloq kodeksiga rioya etishi", "Odob-axloq", 5, "manual"),
    ("tanlov", "Xalqaro, respublika, viloyat miqyosidagi ko‘rik-tanlov, fan olimpiadalari va sport musobaqalarida erishgan natijalari", "Tanlov va olimpiadalar", 10, "upload"),
    ("davomat", "Darslarga to‘liq va kechikmasdan kelishi", "Davomat", 5, "manual"),
    ("marifat", "“Ma’rifat darslari”dagi faol ishtiroki", "Ma’rifat darslari", 10, "upload"),
    ("volontyorlik", "Volontyorlik va jamoat ishlaridagi faolligi", "Volontyorlik", 5, "upload"),
    ("madaniyat", "Teatr va muzey, xiyobon, kino, tarixiy qadamjolarga tashriflar", "Teatr va muzey", 5, "upload"),
    ("sport", "Sport bilan shug‘ullanishi va sog‘lom turmush tarziga amal qilishi", "Sport", 5, "upload"),
    ("boshqa", "Ma’naviy-ma’rifiy sohaga oid boshqa yo‘nalishlardagi faolligi", "Boshqa faollik", 5, "upload"),
]

LEVELS = {
    "tanlov": [
        ("Xalqaro miqyosda g‘olib yoki sovrindor", "10"),
        ("Respublika miqyosida g‘olib yoki sovrindor", "8"),
        ("Viloyat miqyosida g‘olib yoki sovrindor", "5"),
        ("Ishtirokchi", "2"),
    ],
    "volontyorlik": [("Loyiha rahbari", "5"), ("Ishtirokchi", "3")],
    "tashabbus": [("To‘garak sardori", "10"), ("Faol a’zo", "5")],
}


def seed(apps, schema_editor):
    Criterion = apps.get_model("achievements", "Criterion")
    Level = apps.get_model("achievements", "CriterionLevel")
    for order, (code, title, short, max_points, mode) in enumerate(CRITERIA, start=1):
        c, _ = Criterion.objects.update_or_create(
            code=code,
            defaults={"title": title, "short_title": short, "max_points": max_points, "input_mode": mode, "order": order},
        )
        for i, (lt, pts) in enumerate(LEVELS.get(code, []), start=1):
            Level.objects.get_or_create(criterion=c, title=lt, defaults={"points": Decimal(pts), "order": i})


def unseed(apps, schema_editor):
    apps.get_model("achievements", "Criterion").objects.filter(code__in=[c[0] for c in CRITERIA]).delete()


class Migration(migrations.Migration):
    dependencies = [("achievements", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
