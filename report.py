"""PDF report generation (ReportLab)."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

INK = colors.HexColor("#101a33")
COBALT = colors.HexColor("#3157ff")
MUTED = colors.HexColor("#5b6478")


def _p(text, style):
    return Paragraph(escape(str(text)), style)


def build_report(entry: dict) -> BytesIO:
    f, q, m = entry["fields"], entry["quality"], entry.get("last_match")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=INK, fontSize=20, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=COBALT, fontSize=13, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13, textColor=INK)
    muted = ParagraphStyle("m", parent=body, textColor=MUTED)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="Resume report")
    s = [_p("Resume analysis report", h1),
         _p(f"{f['name']}  |  {f['email']}  |  {f['phone']}", muted), Spacer(1, 6)]

    s.append(_p(f"ATS quality score: {q['score']}/100  (grade {q['grade']})", h2))
    rows = [["Category", "Score"]] + [[b["label"], f"{b['score']} / {b['max']}"] for b in q["breakdown"]]
    t = Table(rows, colWidths=[110 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dae6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5fa")]),
    ]))
    s.append(t)

    s.append(_p("What to improve", h2))
    for r in q["feedback"] or [{"priority": "low", "text": "Nothing major. Well structured resume."}]:
        s.append(_p(f"[{r['priority'].upper()}] {r['text']}", body))
        s.append(Spacer(1, 2))

    if q.get("bullet_coaching"):
        s.append(_p("Bullet points to rewrite", h2))
        for c in q["bullet_coaching"]:
            s.append(_p(f"“{c['original']}”", muted))
            s.append(_p(f"{c['issue']}. {c['tip']}", body))
            s.append(Spacer(1, 3))

    s.append(_p("Detected skills", h2))
    s.append(_p(", ".join(f["skills"]) or "None detected", body))

    if m:
        s.append(_p(f"Job match: {m['score']}%", h2))
        s.append(_p(m["explanation"], body))
        s.append(_p("Matched: " + (", ".join(x["skill"] for x in m["matched_skills"]) or "none"), body))
        s.append(_p("Missing: " + (", ".join(x["skill"] for x in m["missing_skills"]) or "none"), body))
        if m.get("what_if"):
            w = m["what_if"]
            s.append(_p(f"Adding {', '.join(w['skills'])} could lift the match to about {w['new_score']}%.", body))

    doc.build(s)
    buf.seek(0)
    return buf
