# Resume Matcher

Upload a resume to get an **ATS score** with prioritised fixes, check it against a job
description, or upload many resumes and **rank candidates**. Flask backend, plain
HTML/CSS/JS frontend, **no database** (everything is kept in memory while the app runs).

## What it does

**For job seekers**
- ATS score out of 100 with a six-part breakdown (contact, sections, skills, impact, length, online presence)
- Prioritised recommendations (high / medium / low) on what to fix
- **Bullet coach**: flags weak openers ("Responsible for…") and bullets with no numbers
- **Evidence check**: skills listed in your Skills section but never proven in a job or project
- **Weighted job match**: skills are weighted by how the posting words them ("must have" vs "nice to have")
- **What-if estimate**: how much your fit rises if you add the top missing skills
- Learning plan for every missing skill, plus a downloadable PDF report

**For recruiters**
- Upload up to 25 resumes, paste the role, get a ranked shortlist (75% job match + 25% resume quality)
- Skill matrix and talent-pool coverage (shows which required skills are scarce)
- Auto-generated interview questions per candidate, based on their gaps
- **Blind screening** toggle (hides names) and CSV export

## Project structure

```
resume-matcher/
├── app.py            Flask app + routes
├── parser_utils.py   text extraction, field parsing, ATS score, bullet coach
├── matcher.py        JD analysis, weighted matching, what-if, interview questions
├── report.py         PDF report
├── skills_data.py    skills taxonomy, aliases (e.g. K8s -> Kubernetes), learning links
├── requirements.txt
├── templates/index.html
├── static/style.css
├── static/script.js
└── uploads/          temporary, files are deleted right after parsing
```

> `index.html` must live in `templates/` and `style.css` / `script.js` in `static/`.

## Run it

```bash
cd resume-matcher
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Notes

- Scanned/image-only PDFs have no text layer, so they can't be read (you'll get a clear message).
- Scores are heuristics, not a real ATS. Use them as guidance.
- Resumes expire when the server restarts (no database by design).
