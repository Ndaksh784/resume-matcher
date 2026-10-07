"""Job-description analysis and resume↔JD matching."""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from skills_data import SKILL_PATTERNS, find_skills, resource_for

REQ_CUE = re.compile(r"\b(must|required|requirements?|essential|mandatory|minimum|proficien\w+|strong|hands-on|expert\w*)\b", re.I)
NICE_CUE = re.compile(r"\b(preferred|nice to have|bonus|plus|good to have|desirable|optional|familiarity|exposure|a plus)\b", re.I)

LEVELS = {"critical": "Critical", "important": "Important", "nice": "Nice to have"}


def jd_skill_weights(jd: str) -> dict:
    """Weight every skill in the JD by how loudly the posting asks for it."""
    lines = [l for l in re.split(r"\n|•|;|(?<=[a-z])\.\s", jd) if l.strip()]
    result = {}
    for skill in find_skills(jd):
        pat = SKILL_PATTERNS[skill]
        hits = [l for l in lines if pat.search(l)]
        count = sum(len(pat.findall(l)) for l in hits)
        has_req = any(REQ_CUE.search(l) for l in hits)
        all_nice = bool(hits) and all(NICE_CUE.search(l) for l in hits) and not has_req
        weight = 1.0 + (1.0 if count >= 3 else 0.5 if count == 2 else 0) + (0.5 if has_req else 0)
        level = "nice" if all_nice else "critical" if weight >= 1.5 else "important"
        if all_nice:
            weight = 0.5
        result[skill] = {"weight": weight, "level": level}
    return result


def required_years(jd: str):
    vals = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)", jd, re.I) if 0 < int(x) <= 20]
    return max(vals) if vals else None


def _text_similarity(a: str, b: str) -> float:
    try:
        tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True).fit_transform([a, b])
        sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
    except ValueError:  # empty vocabulary
        return 0.0
    return min(1.0, sim / 0.45)  # raw cosine on resumes rarely exceeds ~0.45


def _coverage(weights: dict, have: set) -> float:
    total = sum(v["weight"] for v in weights.values())
    return sum(v["weight"] for s, v in weights.items() if s in have) / total if total else 0.0


def _combine(skill_cov, text_sim, exp_fit, has_skills, has_exp):
    parts = []
    if has_skills:
        parts.append((0.60 if not has_exp else 0.55, skill_cov))
        parts.append((0.40 if not has_exp else 0.25, text_sim))
    else:
        parts.append((1.0 if not has_exp else 0.8, text_sim))
    if has_exp:
        parts.append((0.20 if has_skills else 0.2, exp_fit))
    tw = sum(w for w, _ in parts)
    return sum(w * v for w, v in parts) / tw


def explain(score: float, matched: list, missing: list) -> str:
    top_m = ", ".join(m["skill"] for m in matched[:3]) or "key skills"
    top_x = ", ".join(m["skill"] for m in missing[:3]) or "a few missing terms"
    if score >= 75:
        return f"Strong match. You clearly cover the core requirements ({top_m})."
    if score >= 45:
        return f"Moderate match. Closing gaps such as {top_x} would noticeably improve your fit."
    return f"Low match. Several primary requirements are missing, starting with {top_x}."


def analyze_match(entry: dict, jd: str) -> dict:
    fields = entry["fields"]
    have = set(fields["skills"])
    weights = jd_skill_weights(jd)
    req_years = required_years(jd)
    years = fields.get("years_experience", 0)

    skill_cov = _coverage(weights, have)
    text_sim = _text_similarity(entry["raw_text"], jd)
    has_exp = req_years is not None
    exp_fit = 0.5 if (has_exp and years == 0) else (min(1.0, years / req_years) if has_exp else 0)
    score = round(_combine(skill_cov, text_sim, exp_fit, bool(weights), has_exp) * 100, 1)

    ordered = sorted(weights.items(), key=lambda kv: -kv[1]["weight"])
    matched = [{"skill": s, "level": LEVELS[v["level"]]} for s, v in ordered if s in have]
    missing = [{"skill": s, "level": LEVELS[v["level"]], "resource": resource_for(s)}
               for s, v in ordered if s not in have]
    bonus = [s for s in fields["skills"] if s not in weights][:8]

    breakdown = []
    if weights:
        breakdown.append({"label": "Weighted skill coverage", "value": round(skill_cov * 100)})
    breakdown.append({"label": "Keyword relevance", "value": round(text_sim * 100)})
    if has_exp:
        breakdown.append({"label": f"Experience ({years:g} of {req_years}+ yrs)", "value": round(exp_fit * 100)})

    what_if = None
    if missing and weights:
        top = [m["skill"] for m in missing[:3]]
        new = round(_combine(_coverage(weights, have | set(top)), text_sim, exp_fit, True, has_exp) * 100, 1)
        what_if = {"skills": top, "new_score": new, "gain": round(new - score, 1)}

    return {
        "score": score,
        "explanation": explain(score, matched, missing),
        "breakdown": breakdown,
        "matched_skills": matched,
        "missing_skills": missing,
        "bonus_skills": bonus,
        "what_if": what_if,
        "jd_skill_count": len(weights),
        "required_years": req_years,
    }


def interview_focus(match: dict, unproven: list) -> list:
    """Questions a recruiter could ask to probe the gaps in this specific candidate."""
    qs = []
    for m in [x for x in match["missing_skills"] if x["level"] != "Nice to have"][:2]:
        qs.append(f"No {m['skill']} on the resume. Ask about adjacent experience and how quickly they could ramp up.")
    for s in unproven[:2]:
        qs.append(f"{s} is listed but not evidenced. Ask them to walk through a project where they used it.")
    if match["matched_skills"]:
        qs.append(f"Ask for a measurable result they achieved using {match['matched_skills'][0]['skill']}.")
    return qs[:4]
