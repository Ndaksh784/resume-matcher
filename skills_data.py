"""Skills taxonomy, aliases, detection helper and learning resources."""
import re
from urllib.parse import quote_plus

SKILL_CATEGORIES = {
    "Languages": [
        "Python", "Java", "C++", "C", "C#", "JavaScript", "TypeScript", "SQL",
        "Kotlin", "Swift", "PHP", "Ruby", "Rust", "Golang", "Bash", "R",
    ],
    "Web & Mobile": [
        "HTML", "CSS", "React", "Angular", "Vue", "Next.js", "Node.js", "Express",
        "Flask", "Django", "FastAPI", "Spring Boot", "REST API", "GraphQL",
        "Tailwind", "Bootstrap", "Android", "iOS", "Flutter", "React Native",
    ],
    "Data & AI": [
        "Machine Learning", "Deep Learning", "NLP", "Computer Vision", "LLM",
        "Generative AI", "scikit-learn", "TensorFlow", "PyTorch", "Keras",
        "Pandas", "NumPy", "OpenCV", "Matplotlib", "Hugging Face", "Jupyter",
        "Data Analysis", "Statistics", "ETL", "Spark", "Hadoop", "Airflow", "Kafka",
    ],
    "Databases": [
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Firebase", "SQLite", "Oracle",
        "Cassandra", "DynamoDB", "Elasticsearch", "Snowflake", "BigQuery",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Jenkins",
        "Terraform", "Ansible", "Nginx", "Linux", "Microservices", "RabbitMQ",
    ],
    "Tools & Practices": [
        "Git", "GitHub", "Agile", "Scrum", "Jira", "Postman", "Figma", "Selenium",
        "Unit Testing", "TDD", "Data Structures", "Algorithms", "System Design", "OOP",
    ],
    "Analytics": ["Tableau", "Power BI", "Excel"],
    "Soft Skills": [
        "Leadership", "Communication", "Teamwork", "Problem Solving", "Mentoring",
        "Project Management",
    ],
}

SKILLS_DB = [s for group in SKILL_CATEGORIES.values() for s in group]
SKILL_TO_CATEGORY = {s: c for c, group in SKILL_CATEGORIES.items() for s in group}

SKILL_ALIASES = {
    "JavaScript": ["JS", "ES6", "Vanilla JS"],
    "TypeScript": ["TS"],
    "Golang": ["Go lang"],
    "React": ["React.js", "ReactJS"],
    "Vue": ["Vue.js", "VueJS"],
    "Angular": ["AngularJS"],
    "Node.js": ["NodeJS", "Node"],
    "Next.js": ["NextJS"],
    "Express": ["Express.js", "ExpressJS"],
    "Spring Boot": ["Spring"],
    "REST API": ["REST", "RESTful", "REST APIs", "RESTful API", "RESTful APIs"],
    "Machine Learning": ["ML"],
    "Deep Learning": ["Neural Networks"],
    "NLP": ["Natural Language Processing"],
    "Computer Vision": ["CV"],
    "LLM": ["LLMs", "Large Language Models"],
    "Generative AI": ["GenAI", "Gen AI"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "PostgreSQL": ["Postgres"],
    "MongoDB": ["Mongo"],
    "AWS": ["Amazon Web Services"],
    "GCP": ["Google Cloud", "Google Cloud Platform"],
    "Kubernetes": ["K8s"],
    "CI/CD": ["CI CD", "Continuous Integration", "Continuous Deployment"],
    "Data Structures": ["DSA"],
    "OOP": ["Object Oriented", "Object-Oriented", "Object Oriented Programming"],
    "Power BI": ["PowerBI"],
    "Unit Testing": ["Unit Tests", "Pytest", "JUnit"],
    "Problem Solving": ["Problem-Solving"],
    "Elasticsearch": ["Elastic Search"],
    "Hugging Face": ["HuggingFace", "Transformers"],
    "Microservices": ["Micro-services", "Microservice"],
}


def _compile(skill):
    terms = [skill] + SKILL_ALIASES.get(skill, [])
    body = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    flags = 0 if len(skill) == 1 else re.IGNORECASE  # "C" / "R" are case sensitive
    return re.compile(rf"(?<![\w+#]){'(?:' + body + ')'}(?![\w+#])", flags)


SKILL_PATTERNS = {s: _compile(s) for s in SKILLS_DB}


def find_skills(text: str) -> list:
    """Return the sorted list of canonical skills mentioned in text."""
    return sorted(s for s, pat in SKILL_PATTERNS.items() if pat.search(text))


LEARNING_RESOURCES = {
    "Python": "https://docs.python.org/3/tutorial/",
    "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
    "React": "https://react.dev/learn",
    "Docker": "https://docs.docker.com/get-started/",
    "AWS": "https://aws.amazon.com/getting-started/",
    "SQL": "https://www.sqltutorial.org/",
    "Machine Learning": "https://www.coursera.org/learn/machine-learning",
    "Git": "https://git-scm.com/doc",
    "Flask": "https://flask.palletsprojects.com/",
    "Kubernetes": "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
    "TypeScript": "https://www.typescriptlang.org/docs/",
    "Node.js": "https://nodejs.org/en/learn",
    "Django": "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
    "PostgreSQL": "https://www.postgresqltutorial.com/",
    "MongoDB": "https://learn.mongodb.com/",
    "PyTorch": "https://pytorch.org/tutorials/",
    "TensorFlow": "https://www.tensorflow.org/tutorials",
    "Pandas": "https://pandas.pydata.org/docs/getting_started/index.html",
    "Linux": "https://linuxjourney.com/",
    "Tableau": "https://www.tableau.com/learn/training",
}


def resource_for(skill: str) -> dict:
    """Curated link when we have one, otherwise a search link that always works."""
    if skill in LEARNING_RESOURCES:
        return {"url": LEARNING_RESOURCES[skill], "curated": True}
    return {"url": f"https://www.google.com/search?q={quote_plus('learn ' + skill + ' free course tutorial')}", "curated": False}
