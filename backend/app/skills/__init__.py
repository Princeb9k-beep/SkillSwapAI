"""
Superpowers-style task "skills".

`obra/superpowers` organizes agent capabilities into small, self-contained skill
modules. We mirror that structure here: each module in this package is one focused
AI task (roadmap, projects, resume, interview, lessons). Routers stay thin and just
delegate to these — business logic and prompt design live in one place per skill.
"""
