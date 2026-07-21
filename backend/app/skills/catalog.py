"""The Skill Academy catalog: a large, diverse set of paid, AI-guided skill
courses. Each course (a "path") is broken into step-by-step modules and lessons
with hands-on exercises, integrated external tools, and AI support at every step.

The catalog lives in code (not the DB) so it's easy to expand and needs no
migration to grow — enrollments and per-lesson progress are the only persisted
state (see models.SkillEnrollment / SkillProgress). Lesson bodies are generated
from structured templates; the real depth comes from the AI assistant woven into
each lesson (see routers/academy.py `assist`).
"""

from __future__ import annotations

# Reusable external tools, referenced by skills below.
T = {
    "vscode": {"name": "VS Code", "url": "https://code.visualstudio.com/"},
    "replit": {"name": "Replit", "url": "https://replit.com/"},
    "jupyter": {"name": "Jupyter", "url": "https://jupyter.org/"},
    "colab": {"name": "Google Colab", "url": "https://colab.research.google.com/"},
    "github": {"name": "GitHub", "url": "https://github.com/"},
    "figma": {"name": "Figma", "url": "https://figma.com/"},
    "canva": {"name": "Canva", "url": "https://canva.com/"},
    "notion": {"name": "Notion", "url": "https://notion.so/"},
    "chatgpt": {"name": "ChatGPT", "url": "https://chat.openai.com/"},
    "kaggle": {"name": "Kaggle", "url": "https://kaggle.com/"},
    "codepen": {"name": "CodePen", "url": "https://codepen.io/"},
    "postman": {"name": "Postman", "url": "https://www.postman.com/"},
    "davinci": {"name": "DaVinci Resolve", "url": "https://www.blackmagicdesign.com/products/davinciresolve"},
    "ableton": {"name": "Ableton Live", "url": "https://www.ableton.com/"},
    "lightroom": {"name": "Lightroom", "url": "https://www.adobe.com/products/photoshop-lightroom.html"},
    "anki": {"name": "Anki", "url": "https://apps.ankiweb.net/"},
    "sheets": {"name": "Google Sheets", "url": "https://sheets.google.com/"},
    "analytics": {"name": "Google Analytics", "url": "https://analytics.google.com/"},
    "hubspot": {"name": "HubSpot", "url": "https://www.hubspot.com/"},
    "blender": {"name": "Blender", "url": "https://www.blender.org/"},
    "obsidian": {"name": "Obsidian", "url": "https://obsidian.md/"},
}


# Each skill: title, category, difficulty, price (cents), hours, summary, tools,
# and modules -> lesson titles. Content/steps/exercises are generated below.
_SKILLS: list[dict] = [
    # --- Programming ---
    {
        "slug": "python-programming", "title": "Python Programming",
        "category": "Programming", "difficulty": "Beginner", "price_cents": 4900, "hours": 22,
        "summary": "Go from zero to writing real Python programs, scripts, and automations.",
        "tools": ["vscode", "replit", "github"],
        "modules": [
            ("Python Foundations", ["Variables and data types", "Control flow and loops", "Functions and scope"]),
            ("Working with Data", ["Lists, dicts, and sets", "Files, JSON, and CSV", "Errors and debugging"]),
            ("Build Real Things", ["Build a command-line tool", "Call a web API", "Automate a boring task"]),
        ],
    },
    {
        "slug": "javascript-web", "title": "JavaScript & Modern Web",
        "category": "Programming", "difficulty": "Beginner", "price_cents": 4900, "hours": 24,
        "summary": "Master JavaScript and build interactive websites from scratch.",
        "tools": ["vscode", "codepen", "github"],
        "modules": [
            ("JavaScript Core", ["Values, variables, and types", "Functions and arrow syntax", "Arrays and objects"]),
            ("The Browser & DOM", ["Selecting and changing the DOM", "Events and interactivity", "Fetch and async/await"]),
            ("Ship a Project", ["Build a to-do app", "Consume a public API", "Deploy to the web"]),
        ],
    },
    {
        "slug": "react-development", "title": "React Development",
        "category": "Programming", "difficulty": "Intermediate", "price_cents": 6900, "hours": 26,
        "summary": "Build fast, component-based interfaces with React and hooks.",
        "tools": ["vscode", "codepen", "github"],
        "modules": [
            ("React Fundamentals", ["Components and JSX", "Props and state", "Handling events"]),
            ("Hooks & Data", ["useState and useEffect", "Fetching data", "Lists, keys, and forms"]),
            ("Real Application", ["Design a component tree", "Add routing", "Build and deploy a SPA"]),
        ],
    },
    {
        "slug": "sql-databases", "title": "SQL & Databases",
        "category": "Programming", "difficulty": "Beginner", "price_cents": 4400, "hours": 16,
        "summary": "Query, model, and reason about data with SQL.",
        "tools": ["replit", "sheets"],
        "modules": [
            ("Querying Data", ["SELECT, WHERE, ORDER BY", "Aggregations and GROUP BY", "Joins across tables"]),
            ("Designing Schemas", ["Tables, keys, and types", "Normalization basics", "Indexes and performance"]),
            ("Applied SQL", ["Analyze a real dataset", "Write a reporting query", "Optimize a slow query"]),
        ],
    },
    {
        "slug": "git-github", "title": "Git & GitHub",
        "category": "Programming", "difficulty": "Beginner", "price_cents": 2900, "hours": 10,
        "summary": "Version control and collaboration the way real teams work.",
        "tools": ["github", "vscode"],
        "modules": [
            ("Git Basics", ["Commits and history", "Branches and merging", "Undoing mistakes"]),
            ("Collaboration", ["Remotes and push/pull", "Pull requests and reviews", "Resolving conflicts"]),
            ("Pro Workflow", ["Rebase and clean history", "Automate with Actions", "Ship an open-source PR"]),
        ],
    },
    # --- Data & AI ---
    {
        "slug": "data-analysis-pandas", "title": "Data Analysis with Pandas",
        "category": "Data & AI", "difficulty": "Intermediate", "price_cents": 5900, "hours": 20,
        "summary": "Turn messy data into insights with pandas and Python.",
        "tools": ["jupyter", "colab", "kaggle"],
        "modules": [
            ("Pandas Essentials", ["Series and DataFrames", "Selecting and filtering", "Cleaning messy data"]),
            ("Analysis", ["Grouping and aggregation", "Merging datasets", "Time series basics"]),
            ("Real Insight", ["Explore a real dataset", "Answer a business question", "Present your findings"]),
        ],
    },
    {
        "slug": "machine-learning", "title": "Machine Learning Foundations",
        "category": "Data & AI", "difficulty": "Advanced", "price_cents": 7900, "hours": 30,
        "summary": "Understand and build real machine-learning models end to end.",
        "tools": ["colab", "kaggle", "jupyter"],
        "modules": [
            ("ML Concepts", ["What learning means", "Features and labels", "Training vs testing"]),
            ("Core Models", ["Linear and logistic regression", "Trees and forests", "Evaluating models"]),
            ("Real Project", ["Frame an ML problem", "Train and tune a model", "Ship a prediction"]),
        ],
    },
    {
        "slug": "prompt-engineering", "title": "Prompt Engineering",
        "category": "Data & AI", "difficulty": "Beginner", "price_cents": 3900, "hours": 8,
        "summary": "Get reliably great results from AI models through better prompts.",
        "tools": ["chatgpt", "notion"],
        "modules": [
            ("Prompt Basics", ["Anatomy of a great prompt", "Roles and instructions", "Few-shot examples"]),
            ("Advanced Techniques", ["Chain-of-thought prompting", "Structured output", "Guardrails and evals"]),
            ("Applied Prompting", ["Build a writing assistant", "Automate a workflow", "Design a prompt library"]),
        ],
    },
    {
        "slug": "data-visualization", "title": "Data Visualization",
        "category": "Data & AI", "difficulty": "Intermediate", "price_cents": 4900, "hours": 14,
        "summary": "Design charts and dashboards that make data obvious.",
        "tools": ["sheets", "colab", "figma"],
        "modules": [
            ("Chart Foundations", ["Choosing the right chart", "Color and encoding", "Removing clutter"]),
            ("Building Visuals", ["Charts in Python", "Interactive dashboards", "Annotating for insight"]),
            ("Tell a Story", ["Design a dashboard", "Build a data narrative", "Present to stakeholders"]),
        ],
    },
    # --- Design ---
    {
        "slug": "ui-ux-figma", "title": "UI/UX Design with Figma",
        "category": "Design", "difficulty": "Beginner", "price_cents": 5400, "hours": 18,
        "summary": "Design beautiful, usable product interfaces in Figma.",
        "tools": ["figma"],
        "modules": [
            ("Design Foundations", ["Layout and spacing", "Typography and color", "Design systems"]),
            ("Figma Skills", ["Components and variants", "Auto layout", "Prototyping interactions"]),
            ("Real Product", ["Design a mobile app", "Run a usability test", "Hand off to developers"]),
        ],
    },
    {
        "slug": "graphic-design", "title": "Graphic Design Basics",
        "category": "Design", "difficulty": "Beginner", "price_cents": 3900, "hours": 12,
        "summary": "Create striking visuals for brands, social, and print.",
        "tools": ["canva", "figma"],
        "modules": [
            ("Design Principles", ["Balance and hierarchy", "Color theory", "Choosing fonts"]),
            ("Creating Assets", ["Logos and marks", "Social media graphics", "Posters and flyers"]),
            ("Brand Project", ["Build a brand kit", "Design a campaign", "Assemble a portfolio piece"]),
        ],
    },
    {
        "slug": "video-editing", "title": "Video Editing",
        "category": "Design", "difficulty": "Intermediate", "price_cents": 5900, "hours": 20,
        "summary": "Edit engaging videos for YouTube, social, and clients.",
        "tools": ["davinci"],
        "modules": [
            ("Editing Foundations", ["The editing workflow", "Cuts, pacing, and rhythm", "Audio and music"]),
            ("Polish", ["Color correction", "Titles and motion", "Transitions that work"]),
            ("Real Deliverable", ["Edit a short film", "Cut a social reel", "Export and publish"]),
        ],
    },
    # --- Marketing ---
    {
        "slug": "digital-marketing", "title": "Digital Marketing",
        "category": "Marketing", "difficulty": "Beginner", "price_cents": 5400, "hours": 18,
        "summary": "Reach, convert, and retain customers across channels.",
        "tools": ["analytics", "hubspot", "canva"],
        "modules": [
            ("Marketing Foundations", ["Audience and positioning", "The marketing funnel", "Channels overview"]),
            ("Channels", ["Email marketing", "Paid ads basics", "Landing pages"]),
            ("Grow a Brand", ["Plan a campaign", "Measure and iterate", "Build a growth report"]),
        ],
    },
    {
        "slug": "seo-fundamentals", "title": "SEO Fundamentals",
        "category": "Marketing", "difficulty": "Beginner", "price_cents": 4400, "hours": 14,
        "summary": "Rank higher and earn organic traffic that compounds.",
        "tools": ["analytics", "notion"],
        "modules": [
            ("How Search Works", ["Crawling and indexing", "Keywords and intent", "On-page SEO"]),
            ("Content & Links", ["Writing for search", "Technical SEO basics", "Link building"]),
            ("SEO Project", ["Audit a website", "Plan a content calendar", "Track rankings"]),
        ],
    },
    {
        "slug": "content-writing", "title": "Content Writing",
        "category": "Marketing", "difficulty": "Beginner", "price_cents": 3900, "hours": 12,
        "summary": "Write content people actually want to read and share.",
        "tools": ["notion", "chatgpt"],
        "modules": [
            ("Writing Foundations", ["Finding your angle", "Structure and flow", "Editing for clarity"]),
            ("Formats", ["Blog posts", "Newsletters", "Social copy"]),
            ("Real Portfolio", ["Write a flagship article", "Build a content system", "Pitch a client"]),
        ],
    },
    {
        "slug": "social-media-growth", "title": "Social Media Growth",
        "category": "Marketing", "difficulty": "Beginner", "price_cents": 4400, "hours": 12,
        "summary": "Build an engaged audience on the platforms that fit you.",
        "tools": ["canva", "analytics"],
        "modules": [
            ("Strategy", ["Pick your platform and niche", "Content pillars", "Hooks and formats"]),
            ("Creating", ["Batching content", "Short-form video", "Community and engagement"]),
            ("Growth Project", ["Plan a 30-day calendar", "Analyze what works", "Scale a winner"]),
        ],
    },
    # --- Business ---
    {
        "slug": "product-management", "title": "Product Management",
        "category": "Business", "difficulty": "Intermediate", "price_cents": 6900, "hours": 20,
        "summary": "Discover, prioritize, and ship products people love.",
        "tools": ["notion", "figma"],
        "modules": [
            ("Discovery", ["Talking to users", "Defining the problem", "Opportunity sizing"]),
            ("Delivery", ["Prioritization frameworks", "Writing specs", "Working with engineers"]),
            ("Real PM Work", ["Write a PRD", "Run a launch", "Measure impact"]),
        ],
    },
    {
        "slug": "freelancing", "title": "Freelancing & Consulting",
        "category": "Business", "difficulty": "Beginner", "price_cents": 4900, "hours": 12,
        "summary": "Turn your skills into paying clients and repeatable income.",
        "tools": ["notion", "hubspot"],
        "modules": [
            ("Getting Started", ["Packaging your service", "Pricing your work", "Your first offer"]),
            ("Finding Clients", ["Where clients hang out", "Cold outreach that works", "Proposals and calls"]),
            ("Running the Business", ["Contracts and scope", "Delivering great work", "Getting referrals"]),
        ],
    },
    {
        "slug": "personal-finance", "title": "Personal Finance",
        "category": "Business", "difficulty": "Beginner", "price_cents": 3400, "hours": 10,
        "summary": "Take control of your money, debt, and investing.",
        "tools": ["sheets", "notion"],
        "modules": [
            ("Money Foundations", ["Budgeting that sticks", "Emergency funds", "Killing debt"]),
            ("Growing Wealth", ["Investing basics", "Index funds and risk", "Retirement accounts"]),
            ("Your Plan", ["Build a personal budget", "Design an investing plan", "Automate your finances"]),
        ],
    },
    {
        "slug": "public-speaking", "title": "Public Speaking",
        "category": "Business", "difficulty": "Beginner", "price_cents": 3900, "hours": 8,
        "summary": "Speak with confidence and hold any room.",
        "tools": ["notion"],
        "modules": [
            ("Foundations", ["Beating stage fright", "Structuring a talk", "Voice and body"]),
            ("Delivery", ["Storytelling", "Handling Q&A", "Slides that help"]),
            ("Real Talk", ["Write a 5-minute talk", "Record and review", "Deliver it live"]),
        ],
    },
    # --- Creative ---
    {
        "slug": "music-production", "title": "Music Production",
        "category": "Creative", "difficulty": "Intermediate", "price_cents": 5900, "hours": 22,
        "summary": "Produce, mix, and finish your own tracks.",
        "tools": ["ableton"],
        "modules": [
            ("Producing", ["Your DAW and workflow", "Beats and drums", "Melody and chords"]),
            ("Arranging & Mixing", ["Arrangement", "Mixing basics", "Adding effects"]),
            ("Finish a Track", ["Produce a full song", "Mix it down", "Master and release"]),
        ],
    },
    {
        "slug": "photography", "title": "Photography",
        "category": "Creative", "difficulty": "Beginner", "price_cents": 4400, "hours": 14,
        "summary": "Take striking photos and edit them like a pro.",
        "tools": ["lightroom"],
        "modules": [
            ("Camera Craft", ["Exposure triangle", "Composition", "Light and timing"]),
            ("Editing", ["Lightroom basics", "Color and tone", "Developing a style"]),
            ("Real Shoot", ["Plan a photo shoot", "Edit a set", "Build a portfolio"]),
        ],
    },
    {
        "slug": "digital-illustration", "title": "Digital Illustration",
        "category": "Creative", "difficulty": "Intermediate", "price_cents": 5400, "hours": 18,
        "summary": "Draw and illustrate digitally from sketch to finished piece.",
        "tools": ["figma", "blender"],
        "modules": [
            ("Fundamentals", ["Line and shape", "Value and light", "Color in illustration"]),
            ("Technique", ["Sketching digitally", "Inking and lineart", "Coloring and shading"]),
            ("Finished Work", ["Illustrate a character", "Create a scene", "Prep for print/web"]),
        ],
    },
    # --- Languages & Growth ---
    {
        "slug": "spanish-conversation", "title": "Conversational Spanish",
        "category": "Languages", "difficulty": "Beginner", "price_cents": 3900, "hours": 20,
        "summary": "Hold real conversations in Spanish, fast.",
        "tools": ["anki", "chatgpt"],
        "modules": [
            ("Survival Spanish", ["Greetings and intros", "Numbers and time", "Everyday phrases"]),
            ("Real Conversations", ["Ordering and shopping", "Directions and travel", "Small talk"]),
            ("Fluency Habits", ["Building vocabulary", "Speaking practice", "Immersion routine"]),
        ],
    },
    {
        "slug": "business-english", "title": "Business English",
        "category": "Languages", "difficulty": "Intermediate", "price_cents": 4400, "hours": 16,
        "summary": "Communicate clearly and professionally at work in English.",
        "tools": ["notion", "chatgpt"],
        "modules": [
            ("Workplace English", ["Emails that get replies", "Meetings and calls", "Clear writing"]),
            ("Presenting", ["Presentations", "Negotiation language", "Small talk and rapport"]),
            ("Real Scenarios", ["Write a proposal", "Run a mock meeting", "Give a status update"]),
        ],
    },
    {
        "slug": "productivity-habits", "title": "Productivity & Habits",
        "category": "Personal Growth", "difficulty": "Beginner", "price_cents": 2900, "hours": 8,
        "summary": "Build systems that make good work inevitable.",
        "tools": ["notion", "obsidian"],
        "modules": [
            ("Foundations", ["Goals and priorities", "Beating procrastination", "Deep work"]),
            ("Systems", ["Task management", "Note-taking that lasts", "Weekly reviews"]),
            ("Your System", ["Design your workflow", "Build a habit loop", "Run it for a week"]),
        ],
    },
]

_STEP_TEMPLATES = [
    "Read the concept overview: what {t} is and why it matters.",
    "Follow a guided, worked example that applies {t} step by step.",
    "Try it yourself in a short drill, then check your understanding.",
]

_EXERCISE_FRAMES = [
    "Complete a real-world mini-task that puts {t} to use and share your result.",
    "Build a small deliverable that demonstrates {t} end to end.",
    "Apply {t} to your own project or a dataset/brief of your choice.",
]


def _lesson_key(mi: int, li: int) -> str:
    return f"m{mi + 1}-l{li + 1}"


def _build_lesson(skill: dict, module_title: str, mi: int, li: int, title: str) -> dict:
    t = title.lower()
    steps = [tpl.format(t=t) for tpl in _STEP_TEMPLATES]
    exercise = _EXERCISE_FRAMES[(mi + li) % len(_EXERCISE_FRAMES)].format(t=t)
    return {
        "key": _lesson_key(mi, li),
        "title": title,
        "summary": f"Learn {t} as part of “{module_title},” then practice it hands-on.",
        "steps": steps,
        "exercise": exercise,
        "tools": [T[k] for k in skill["tools"]],
    }


def _build_path(skill: dict) -> dict:
    modules = []
    lesson_count = 0
    for mi, (mtitle, lessons) in enumerate(skill["modules"]):
        built = [_build_lesson(skill, mtitle, mi, li, lt) for li, lt in enumerate(lessons)]
        lesson_count += len(built)
        modules.append({"title": mtitle, "lessons": built})
    return {
        "slug": skill["slug"],
        "title": skill["title"],
        "category": skill["category"],
        "difficulty": skill["difficulty"],
        "price_cents": skill["price_cents"],
        "hours": skill["hours"],
        "summary": skill["summary"],
        "tools": [T[k] for k in skill["tools"]],
        "modules": modules,
        "lesson_count": lesson_count,
    }


# The fully-built catalog, indexed for fast lookup.
CATALOG: list[dict] = [_build_path(s) for s in _SKILLS]
_BY_SLUG: dict[str, dict] = {p["slug"]: p for p in CATALOG}


def categories() -> list[str]:
    seen: list[str] = []
    for p in CATALOG:
        if p["category"] not in seen:
            seen.append(p["category"])
    return seen


def list_paths(category: str | None = None) -> list[dict]:
    if category and category != "All":
        return [p for p in CATALOG if p["category"] == category]
    return list(CATALOG)


def get_path(slug: str) -> dict | None:
    return _BY_SLUG.get(slug)


def get_lesson(slug: str, key: str) -> tuple[dict, dict] | None:
    """Return (path, lesson) for a slug+lesson key, or None."""
    path = _BY_SLUG.get(slug)
    if path is None:
        return None
    for module in path["modules"]:
        for lesson in module["lessons"]:
            if lesson["key"] == key:
                return path, lesson
    return None


def all_lesson_keys(slug: str) -> list[str]:
    path = _BY_SLUG.get(slug)
    if path is None:
        return []
    return [l["key"] for m in path["modules"] for l in m["lessons"]]
