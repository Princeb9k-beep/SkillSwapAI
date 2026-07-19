# SkillSwapAI — Product Specification & Build Roadmap

> **Status:** target vision / engineering spec. This document defines *what SkillSwapAI
> is meant to become*; it is deliberately broader than what ships today. Consult the
> codebase and PR history for current implementation status. Build order is fixed in
> §6 — do not deviate from the priority sequence.

## 0. Operating Mandate

Claude operates as the principal full‑stack engineer, architect, and AI systems designer
for SkillSwapAI — a platform that matches people who want to exchange skills and learn
together. Output for feature work must be:

- Technically precise, deterministic, modular, scalable, security‑aware.
- Fully implementable — complete modules and full code blocks, no pseudocode and no
  placeholders unless unavoidable.
- Written senior‑engineer‑to‑senior‑engineer: no filler, no conversational tone in
  delivered artifacts.

---

## 1. Core Mission

**Match people based on the skills they have and the skills they want — and support
their learning through AI‑powered tools.** All code and architecture must reinforce this
mission.

---

## 2. Primary Features (Highest Priority)

### 2.1 AI Skill Matching (Primary Feature)
A matching engine that accepts a user's known skills and desired skills, computes
complementary matches, ranks candidates, and surfaces the best partners — "a dating app
for learning."

Deliverables: matching algorithms · PostgreSQL schemas · FastAPI endpoints · Redis
caching layers · ranking logic · React UI flows · example request/response payloads.

### 2.2 AI Learning Roadmaps
On skill selection, generate personalized learning plans, daily lessons, weekly goals,
progress tracking, and 30/60/90‑day roadmaps.

Deliverables: roadmap generation logic · lesson structuring modules · progress tracking
schema · API routes · React components.

### 2.3 Messaging + Video Practice Rooms
Real‑time collaboration: WebRTC video, screen sharing, whiteboard, shared notes.

Deliverables: signaling server code · FastAPI WebSocket endpoints · React WebRTC
components · session persistence models.

### 2.4 AI Coach
24/7 learning support: Q&A, feedback, file critique, conversation practice.

Deliverables: Groq AI pipelines · file‑analysis endpoints · feedback scoring logic ·
conversation modules.

### 2.5 Skill Verification
Trust systems: project uploads, quizzes, peer reviews, AI assessments, badges.

Deliverables: verification workflows · badge logic · assessment rubrics · review models.

---

## 3. Secondary Features (Implement After Core)

### 3.1 Gamification
XP, levels, streaks, achievements, leaderboards. → XP formulas · achievement triggers ·
leaderboard queries.

### 3.2 Portfolio Builder
Auto‑create projects, certificates, skill timeline, shareable profile. → portfolio schema
· certificate generator logic · timeline rendering.

### 3.3 AI Translation
Live translated chat, video captions, voice translation. → translation pipelines ·
captioning modules · multilingual UX flows.

### 3.4 Communities
Topic‑based groups (coding, music, sports, languages, art). → community models · posting
APIs · moderation logic.

### 3.5 Local Meetups
Opt‑in: nearby learners, study groups, hackathons, photography walks. → geolocation
matching · meetup scheduling · safety logic.

### 3.6 AI Reputation Score
Replace simple ratings with reliability, teaching quality, response time, session
completion, reviews. → reputation algorithm · weighting formulas · display logic.

### 3.7 Marketplace
Paid tutoring, template/course sales, coaching bookings. → marketplace schema · payment
flows · commission logic.

### 3.8 Daily AI Challenges
E.g. learn one Spanish phrase, solve a coding problem, draw a logo in 15 minutes. →
challenge generator · streak logic · reward system.

### 3.9 AI Skill Scanner
Ingest résumé / portfolio / GitHub / LinkedIn; identify strengths, missing skills, next
steps. → file ingestion pipelines · skill extraction models · recommendation logic.

### 3.10 Company Partnerships
Skill challenges, scholarships, internships, hiring. → company dashboards · challenge
submission flows · recruiter tools.

---

## 4. Unique Differentiator: AI Twin

An AI Twin that learns how a partner teaches, mimics their teaching style, quizzes based
on past sessions, and summarizes shared learning history. → teaching‑style embeddings ·
partner‑mimic logic · session memory models.

---

## 5. Required Tech Stack

FastAPI (backend) · React (frontend) · PostgreSQL (primary DB) · Redis (caching, queues)
· Groq (AI inference) · SQLAlchemy + Alembic (migrations) · modular, production‑ready file
structure. Output complete modules and full code — no pseudocode, no placeholders unless
unavoidable.

---

## 6. Development Roadmap (Strict Priority Order)

1. AI skill matching
2. Messaging + video sessions
3. AI coach
4. Progress tracking + streaks
5. Skill verification
6. Community groups
7. Marketplace
8. Company partnerships

Do not deviate from this sequence.

---

## 7. Hard‑to‑Copy Advantage

Design for a compounding moat: a growing dataset of successful matches, AI models that
improve from user behavior, and network effects that strengthen over time. This must be
reflected in schemas, pipelines, and architecture (e.g. capture match outcomes and
session signals as first‑class, trainable data).

---

## 8. Output Requirements (for feature work)

Always produce: full code files · API routes · database schemas · migrations · React
components · ASCII architecture diagrams · explanations of design decisions. No
conversational tone or filler in delivered artifacts.
