"""A curated catalog of skills for the Discover feed (the TikTok-style stream).

Each entry is a short "clip" about a skill: a caption, a one-line hook, an emoji
accent, a category, and a difficulty. The Discover endpoint personalizes this by
marking which skills the user already has/wants and how many learners on the
platform know each one (a real count, computed from the DB — no fake numbers).
"""

from __future__ import annotations

# Kept as plain data so it's trivial to extend. `category` matches the tags used
# elsewhere (Coding, Design, Languages, Music, Career, Business, Wellness).
SKILL_CATALOG: list[dict[str, str]] = [
    {"name": "Python", "category": "Coding", "emoji": "🐍",
     "blurb": "Automate boring tasks and build anything from scripts to AI.",
     "hook": "The most in-demand first language.", "difficulty": "beginner"},
    {"name": "JavaScript", "category": "Coding", "emoji": "🌐",
     "blurb": "The language of the web — make sites interactive and alive.",
     "hook": "Runs in every browser on earth.", "difficulty": "beginner"},
    {"name": "React", "category": "Coding", "emoji": "⚛️",
     "blurb": "Build slick, app-like interfaces the way the pros do.",
     "hook": "Powers most modern web apps.", "difficulty": "intermediate"},
    {"name": "SQL", "category": "Coding", "emoji": "🗄️",
     "blurb": "Ask any question of any database and get an answer.",
     "hook": "Every data job needs it.", "difficulty": "beginner"},
    {"name": "UI/UX Design", "category": "Design", "emoji": "🎨",
     "blurb": "Design screens people love to use — not just look at.",
     "hook": "Turn ideas into products.", "difficulty": "beginner"},
    {"name": "Figma", "category": "Design", "emoji": "🖌️",
     "blurb": "Prototype and design interfaces in the industry-standard tool.",
     "hook": "From sketch to clickable in minutes.", "difficulty": "beginner"},
    {"name": "Photography", "category": "Design", "emoji": "📷",
     "blurb": "Frame, light, and edit shots that stop the scroll.",
     "hook": "Your phone is enough to start.", "difficulty": "beginner"},
    {"name": "Spanish", "category": "Languages", "emoji": "🇪🇸",
     "blurb": "Unlock conversations with half a billion people.",
     "hook": "Learn by swapping with a native.", "difficulty": "beginner"},
    {"name": "French", "category": "Languages", "emoji": "🇫🇷",
     "blurb": "From café small talk to reading Camus in the original.",
     "hook": "Practice out loud, daily.", "difficulty": "beginner"},
    {"name": "Guitar", "category": "Music", "emoji": "🎸",
     "blurb": "Four chords and you can play a hundred songs.",
     "hook": "Play your first song this week.", "difficulty": "beginner"},
    {"name": "Music Production", "category": "Music", "emoji": "🎧",
     "blurb": "Turn a melody in your head into a finished track.",
     "hook": "Make beats from your bedroom.", "difficulty": "intermediate"},
    {"name": "Public Speaking", "category": "Career", "emoji": "🎤",
     "blurb": "Command a room and pitch ideas without the shakes.",
     "hook": "The skill that gets you promoted.", "difficulty": "beginner"},
    {"name": "Resume Writing", "category": "Career", "emoji": "📄",
     "blurb": "Write a resume that actually gets callbacks.",
     "hook": "Beat the bots and the recruiters.", "difficulty": "beginner"},
    {"name": "Data Analysis", "category": "Career", "emoji": "📊",
     "blurb": "Find the story hiding in a spreadsheet full of numbers.",
     "hook": "Every team wants this now.", "difficulty": "intermediate"},
    {"name": "Digital Marketing", "category": "Business", "emoji": "📣",
     "blurb": "Get the right people to notice what you build.",
     "hook": "Grow an audience from zero.", "difficulty": "beginner"},
    {"name": "Entrepreneurship", "category": "Business", "emoji": "🚀",
     "blurb": "Turn a side idea into something people pay for.",
     "hook": "Ship your first tiny product.", "difficulty": "intermediate"},
    {"name": "Cooking", "category": "Wellness", "emoji": "🍳",
     "blurb": "Cook three meals well and you'll never eat sad lunches again.",
     "hook": "Start with one signature dish.", "difficulty": "beginner"},
    {"name": "Meditation", "category": "Wellness", "emoji": "🧘",
     "blurb": "Train your focus like a muscle, ten minutes a day.",
     "hook": "Calm is a skill you can learn.", "difficulty": "beginner"},
]
