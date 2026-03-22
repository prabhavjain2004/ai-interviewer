# Mirror & Mentor Report Format

## Overview
The coaching report is generated after each interview using Gemini 1.5 Pro. It provides structured feedback across 6 categories based on the Wellfound interview framework.

## Report Structure

```json
{
  "session_id": "uuid-string",
  "generated_at": "2026-03-22T21:10:09.769Z",
  "overall_score": 7.5,
  "summary": "2-3 sentence overall coaching summary",
  "feedback": [
    {
      "category": "Technical Depth",
      "score": 8,
      "student_quote": "Exact words from the interview transcript",
      "resume_claim": "What the resume says they did",
      "diagnosis": "Specific named weakness (not generic)",
      "elite_script": "15-30 second rewrite with STAR structure and metrics",
      "is_derived_metric": true,
      "mirror": {
        "resume_claim": "Resume claim being compared",
        "student_said": "What student actually said",
        "gap": "Specific gap between claim and verbal answer",
        "consistency": "strong | moderate | weak"
      }
    }
  ]
}
```

## The 6 Categories (Wellfound Framework)

### 1. Technical Depth
- Accuracy and specificity of technical answers
- Use of correct terminology
- Depth of understanding vs surface-level knowledge

### 2. Communication Clarity
- Structure and conciseness
- Absence of filler words ("um", "like", "you know")
- Logical flow of explanation

### 3. Resume Consistency
- Alignment between resume claims and verbal answers
- Ability to back up resume statements with details
- Consistency in ownership claims ("I" vs "we")

### 4. Problem-Solving Approach
- STAR structure (Situation → Task → Action → Result)
- Logical reasoning
- Trade-off analysis

### 5. Ownership & Impact
- Use of "I" vs "we" (personal ownership)
- Quantifiable outcomes and metrics
- Clear articulation of personal contribution

### 6. Cultural & Role Fit
- Alignment with stated career goals
- Enthusiasm and engagement
- Growth mindset indicators

## Scoring System

- **1-3**: Significant gaps, needs substantial work
- **4-6**: Foundational understanding present, articulation needs improvement
- **7-8**: Strong answer with minor gaps
- **9-10**: Elite — clear, specific, metric-driven, STAR-structured

**Overall Score**: Weighted average (Technical Depth and Ownership & Impact weighted 1.5x)

## Elite Script Requirements

Every feedback item includes an "Elite Script" — the professional version of what the student should have said.

**Non-negotiable requirements:**
1. **STAR structure**: Situation → Task → Action → Result
2. **At least one metric**: Uses resume power_facts if available, otherwise suggests placeholder like "[X]%"
3. **Industry-standard terminology**: Matches the student's tech stack
4. **Natural speech**: Not robotic, not over-formal
5. **50-100 words**: 15-30 seconds when spoken aloud

### Example Transformation

**Student said:**
> "I worked on making the API faster, used some Redis stuff."

**Elite Script:**
> "In my [PROJECT] work, our API response times were averaging [X]ms under load, which was causing drop-offs in the user flow. I diagnosed the bottleneck as repeated database hits on [ENTITY] queries. I implemented a Redis caching layer with a [Y]-minute TTL on those endpoints, which brought average response time down to [Z]ms — a [N]% improvement that directly improved our [METRIC] in testing."

## Mirror Engine

Each feedback item includes a "mirror" comparison:

- **resume_claim**: What the resume says
- **student_said**: What they actually said in the interview
- **gap**: The specific articulation gap
- **consistency**: strong | moderate | weak

This helps students see the disconnect between what they wrote and what they can verbally articulate.

## Report Generation Process

1. **Input**: Resume JSON + Full transcript + Auditor notes
2. **Model**: Gemini 1.5 Pro (NOT Flash)
3. **Output**: Structured JSON with schema validation
4. **Storage**: Redis under key `session:{session_id}:report`
5. **Timing**: Generated as FastAPI BackgroundTask after interview ends
6. **Deduplication**: Skips if report already exists

## Frontend Display

The report is displayed in a modal with:
- Overall score with color coding (green ≥7, yellow 4-6, red <4)
- Summary box at the top
- 6 feedback cards, each showing:
  - Category name and score
  - Student quote (what they said)
  - Diagnosis (what's wrong)
  - Elite Script (how to say it better)
  - Metric badge (verified vs suggested)

## API Endpoints

### GET /report/{session_id}
- **202 Accepted**: Report still generating
- **200 OK**: Report ready (returns full JSON)
- **400 Bad Request**: Session not found or no transcript
- **404 Not Found**: Session doesn't exist

### Polling Strategy
Frontend polls every 3 seconds for up to 40 attempts (2 minutes max).
