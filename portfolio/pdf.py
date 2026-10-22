"""Portfolio PDF (A4, Outfit shrifti). Ma'lumot `services.build` dan olinadi."""
import io

from django.utils import timezone

from reports.exports import _num, _pdf_text, _register_fonts


def build_pdf(pf, university):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _register_fonts()
    orange, ink, muted, line, soft = (colors.HexColor(h) for h in ("#C25700", "#1E293B", "#64748B", "#E8EDF4", "#FFF2E5"))
    st = {
        "kicker": ParagraphStyle("k", fontName="Outfit-Bold", fontSize=8.5, leading=11, textColor=orange),
        "name": ParagraphStyle("n", fontName="Outfit-Bold", fontSize=20, leading=24, textColor=ink),
        "meta": ParagraphStyle("m", fontName="Outfit", fontSize=9, leading=13, textColor=muted),
        "h2": ParagraphStyle("h2", fontName="Outfit-Bold", fontSize=12.5, leading=16, textColor=ink, spaceBefore=10, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="Outfit-Bold", fontSize=10, leading=13, textColor=orange),
        "cell": ParagraphStyle("c", fontName="Outfit", fontSize=8.5, leading=11, textColor=ink),
        "small": ParagraphStyle("s", fontName="Outfit", fontSize=7.5, leading=10, textColor=muted),
        "statv": ParagraphStyle("sv", fontName="Outfit-Bold", fontSize=16, leading=19, textColor=ink, alignment=1),
        "statl": ParagraphStyle("sl", fontName="Outfit", fontSize=7.5, leading=10, textColor=muted, alignment=1),
    }
    T = _pdf_text
    s, p = pf.student, pf.profile
    generated = timezone.localtime(pf.generated_at)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Outfit", 7)
        canvas.setFillColor(muted)
        canvas.drawString(16 * mm, 9 * mm, T(f"{university} · Ijtimoiy Faollik tizimi avtomatik yaratgan · {generated:%d.%m.%Y %H:%M}"))
        canvas.drawRightString(A4[0] - 16 * mm, 9 * mm, f"{doc.page}-sahifa")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                            title=f"Portfolio: {s.full_name}", author=university)
    width = A4[0] - 32 * mm
    story = [Paragraph("TALABA PORTFOLIOSI", st["kicker"]), Spacer(1, 2 * mm), Paragraph(T(s.full_name), st["name"])]
    meta = []
    if p:
        meta = [p.faculty.name if p.faculty else "", p.specialty.name if p.specialty else "",
                f"{p.group.name} guruh" if p.group else "", f"{p.course}-kurs" if p.course else "",
                f"GPA {_num(p.gpa)}" if p.gpa is not None else ""]
    meta.append(f"HEMIS ID {s.hemis_id}" if s.hemis_id else "")
    story += [Spacer(1, 1 * mm), Paragraph(T(" · ".join(m for m in meta if m)), st["meta"]), Spacer(1, 5 * mm)]

    cur = pf.current
    stats = [
        (str(pf.total_approved), "tasdiqlangan yutuq"),
        (str(pf.criteria_covered), "yo‘nalishda faol"),
        (f"{_num(cur.total)} / 100" if cur else "–", f"ball ({cur.semester.number}-semestr)" if cur else "joriy ball"),
        (f"{cur.faculty_rank} / {cur.faculty_size}" if cur and cur.faculty_rank else "–", "fakultetdagi o‘rin"),
    ]
    box = Table([[Paragraph(T(v), st["statv"]) for v, _ in stats], [Paragraph(T(lbl), st["statl"]) for _, lbl in stats]],
                colWidths=[width / 4] * 4)
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), soft), ("TOPPADDING", (0, 0), (-1, 0), 8),
                             ("BOTTOMPADDING", (0, 1), (-1, 1), 8), ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.white)]))
    story.append(box)

    if pf.bars and cur:
        story.append(Paragraph(T(f"Mezonlar bo‘yicha ({cur.semester})"), st["h2"]))
        rows = [[Paragraph("Mezon", st["small"]), Paragraph("Ball", st["small"])]]
        for b in pf.bars:
            rows.append([Paragraph(T(b["criterion"].title), st["cell"]), f"{_num(b['points'])} / {b['max']}"])
        t = Table(rows, colWidths=[width - 28 * mm, 28 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (1, 1), (1, -1), "Outfit-Bold", 8.5), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.4, line), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.append(t)

    story.append(Paragraph("Yutuqlar", st["h2"]))
    if not pf.groups:
        story.append(Paragraph("Hozircha tasdiqlangan yutuq yo‘q.", st["meta"]))
    for g in pf.groups:
        rows = [[Paragraph("Yutuq", st["small"]), Paragraph("Daraja", st["small"]), Paragraph("Sana", st["small"]), Paragraph("Ball", st["small"])]]
        for a in g.items:
            rows.append([Paragraph(T(a.title), st["cell"]), Paragraph(T(a.level.title if a.level else "–"), st["cell"]),
                         a.event_date.strftime("%d.%m.%Y"), _num(a.points or 0)])
        t = Table(rows, colWidths=[width * 0.5, width * 0.28, 22 * mm, width * 0.22 - 22 * mm], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (2, 1), (-1, -1), "Outfit", 8.5), ("FONT", (3, 1), (3, -1), "Outfit-Bold", 8.5),
                               ("ALIGN", (3, 0), (3, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.4, line), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        head = Paragraph(T(f"{g.criterion.title} · {len(g.items)} ta"), st["h3"])
        story += [KeepTogether([head, Spacer(1, 1.5 * mm), t]), Spacer(1, 4 * mm)]

    if pf.semesters:
        story.append(Paragraph("Semestrlar bo‘yicha natijalar", st["h2"]))
        rows = [[Paragraph(h, st["small"]) for h in ("Semestr", "Ball", "Yutuqlar", "Fakultetda", "Universitetda")]]
        for line_ in pf.semesters:
            rows.append([T(str(line_.semester)), _num(line_.total), str(line_.approved),
                         f"{line_.faculty_rank} / {line_.faculty_size}" if line_.faculty_rank else "–",
                         f"{line_.university_rank} / {line_.university_size}"])
        t = Table(rows, colWidths=[width * 0.36, width * 0.14, width * 0.14, width * 0.18, width * 0.18], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 1), (-1, -1), "Outfit", 8.5), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                               ("LINEBELOW", (0, 0), (-1, -1), 0.4, line), ("TOPPADDING", (0, 0), (-1, -1), 3),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.append(t)

    story += [Spacer(1, 6 * mm), Paragraph(
        "Portfolio tizim tomonidan avtomatik tuzilgan. Unga faqat fakultet mas’uli yoki tyutor hujjat asosida tasdiqlagan "
        "yutuqlar kiritilgan.", st["small"])]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
