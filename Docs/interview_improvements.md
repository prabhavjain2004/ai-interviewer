# Interview System Improvements

## Changes Made (March 22, 2026)

### 1. Simplified Phase System
**Before:** 3 phases (warm_up → deep_dive → stress_test) with 11 total questions
**After:** 2 phases (warm_up → deep_dive) with 7 total questions max

**Rationale:** 
- Target interview length: ~15 minutes
- Removed stress_test phase complexity
- Faster, more focused interviews

**New Thresholds:**
- Warm-up: 2 questions (quick intro, non-technical)
- Deep-dive: 5 questions (technical, resume-grounded)
- Total: 7 questions max

### 2. Better Answer Acknowledgment
**Problem:** AI was asking next question immediately without validating the answer
**Solution:** Added explicit acknowledgment requirement in system instruction

**Examples of acknowledgments:**
- "I love that approach"
- "That makes sense"
- "Really interesting"
- "Smart trade-off"
- "I really like how you approached that"
- "That shows good architectural thinking"

**Implementation:** System instruction now requires AI to validate/acknowledge before asking next question.

### 3. Contextual Follow-ups
**Problem:** AI was asking pre-planned questions in sequence, ignoring student answers
**Solution:** Emphasized conversation-driven questioning

**Key Rules:**
- LISTEN to what student says
- If they mention specific tech (e.g., "multi-agent orchestration"), next question MUST drill into that
- No checklist approach — adapt in real-time
- Questions must be based on previous answers

**Example:**
- Student: "I used multi-agent orchestration"
- AI: "I love that approach — walk me through how you handled coordination between agents. What communication pattern did you use?"

### 4. Less Technical Warm-up
**Before:** Warm-up phase allowed technical questions
**After:** Warm-up is strictly non-technical

**Warm-up Guidelines:**
- Ask about current work and career goals
- Keep it light and conversational
- Build rapport only
- NO technical questions yet
- 2 questions max

### 5. Fixed VAD False Triggers
**Problem:** System was sending TURN_COMPLETE before student even spoke
**Solution:** Added minimum speech duration requirement

**New VAD Parameters:**
- `SILENCE_THRESHOLD`: 0.005 (lowered from 0.015)
- `SILENCE_DURATION`: 2000ms (increased from 1800ms)
- `MIN_SPEECH_DURATION`: 800ms (NEW - prevents false triggers)
- Speech duration tracking to filter out noise bursts

**How it works:**
1. User must speak for at least 800ms before system considers it valid speech
2. After valid speech, system waits 2 full seconds of silence
3. Only then sends TURN_COMPLETE
4. Console logs show speech duration for debugging

### 6. Improved Backend Nudge
**Problem:** Gemini wasn't responding after TURN_COMPLETE signal
**Solution:** Hardened the manual turn completion signal

**Changes:**
- Send explicit text message: "[Candidate finished speaking. Please respond now.]"
- Use `turn_complete=True` flag
- More aggressive nudge to force response generation

## Configuration Changes

### agents/interviewer.py
```python
PHASE_THRESHOLDS = {
    "warm_up": 2,       # 2 questions
    "deep_dive": 7,     # 5 more questions (total 7)
    "stress_test": 999, # removed
}
```

### main.py
```python
max_turns_warm_up: int = 2
max_turns_deep_dive: int = 7
max_turns_stress_test: int = 999  # disabled
```

### templates/index.html
```javascript
const SILENCE_THRESHOLD = 0.005;
const SILENCE_DURATION = 2000;
const MIN_SPEECH_DURATION = 800;
```

## Testing Checklist

- [ ] Interview completes in ~15 minutes
- [ ] Only 7 questions asked total
- [ ] Warm-up is non-technical (2 questions)
- [ ] Deep-dive is technical and resume-grounded (5 questions)
- [ ] AI acknowledges answers before asking next question
- [ ] Follow-up questions are contextual (based on student's answer)
- [ ] No false TURN_COMPLETE triggers
- [ ] Student can speak for 800ms+ before turn ends
- [ ] 2 seconds of silence required before turn completion
- [ ] Console logs show speech duration
- [ ] Report generates successfully after interview

## Report Format

See `Docs/report_format.md` for complete report structure and examples.

**Key Features:**
- 6 categories (Wellfound framework)
- Overall score (1-10)
- Elite Scripts with STAR structure and metrics
- Mirror comparison (resume vs verbal)
- Specific, actionable feedback

## Next Steps

1. Test with real interview scenarios
2. Tune `SILENCE_THRESHOLD` if needed based on environment noise
3. Adjust `MIN_SPEECH_DURATION` if users speak very slowly
4. Monitor turn counts to ensure 7-question limit is respected
5. Collect feedback on acknowledgment quality
6. Verify contextual follow-ups are working as expected
