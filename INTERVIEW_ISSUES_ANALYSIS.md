# Interview System Issues - Analysis & Fixes

## Issues Reported

### 1. Agent Interrupting Before Answer Completion
**Problem**: Agent asks next question before student finishes answering
**Root Cause**: Manual VAD mode (`TURN_COMPLETE` signal) timing issues
- Frontend sends `TURN_COMPLETE` too early
- `MIN_TURN_INCREMENT_INTERVAL_SECONDS = 1.5` may be too short
- Agent receives turn_complete signal and immediately asks next question

**Symptoms**:
- "It didn't give me time and started asking the next question"
- Student unable to complete thoughts

### 2. Agent Not Responding to Questions
**Problem**: When student asks a question, agent doesn't answer
**Root Cause**: Turn completion logic treats student questions as turn endings
- System instruction says "answer questions naturally" but implementation doesn't support it
- `signal_activity_end()` forces immediate response generation
- No distinction between "student finished statement" vs "student asked question"

**Symptoms**:
- "When I ask the question to an agent, it was not able to answer"
- "It was not a conversational thing"

### 3. Empty/Minimal Transcript
**Problem**: Coach report generated with no actual conversation data
**Root Cause**: Transcript not being captured or persisted properly
- `_append_turn()` only called when `finished=True` on transcription
- Transcript may not be syncing to Redis before coach runs
- WebSocket disconnect might lose transcript data

**Symptoms**:
- Report says "The interview transcript is empty"
- "No verbal responses were provided"
- Overall score: 1.0/10

### 4. Generic Report Content
**Problem**: Report contains suggested scripts instead of actual interview analysis
**Root Cause**: Coach prompt generates fallback content when transcript is empty
- All feedback items show "◈ Suggested — fill in your number"
- No actual student quotes from interview
- Generic STAR scripts not based on conversation

**Symptoms**:
- "It should tell actual things that has been talked in the conversation"
- Report doesn't reflect what was actually discussed

## Recommended Fixes

### Fix 1: Improve Turn Completion Logic
**File**: `core/streaming_manager.py`

```python
# Increase minimum turn interval to prevent premature interruption
MIN_TURN_INCREMENT_INTERVAL_SECONDS = 3.0  # Was 1.5

# Add better turn completion detection
async def signal_activity_end(self) -> None:
    """Only call this when student has FULLY completed their thought"""
    if not self._is_connected or self._live_session is None:
        return
    
    # Don't force immediate response - let model decide if more input is coming
    await self._live_session.send_realtime_input(
        activity_end=genai_types.ActivityEnd()
    )
    # Remove the explicit nudge - let natural turn-taking happen
```

### Fix 2: Enable True Conversational Mode
**File**: `core/streaming_manager.py`

```python
# In build_system_instruction(), strengthen the conversational rules:
CRITICAL WAITING RULE:
- After asking a question, you MUST wait for the student to finish their complete answer.
- If the student asks YOU a question, ANSWER IT FULLY before continuing the interview.
- DO NOT move to the next question until the current exchange is complete.
- Listen for question markers: "Should I...?", "What about...?", "Is it better to...?"
- When you hear a question, treat it as a conversation, not an interruption.
```

### Fix 3: Fix Transcript Capture
**File**: `core/streaming_manager.py`

```python
# Capture partial transcriptions, not just finished ones
if content.input_transcription:
    student_text = content.input_transcription.text
    is_finished = bool(getattr(content.input_transcription, "finished", False))
    
    # Capture ALL text, not just finished chunks
    if student_text and student_text.strip():
        if is_finished:
            self._student_spoke_since_last_turn = True
            self._append_turn("student", student_text)
            # ... rest of logic
        else:
            # Accumulate partial transcription
            self._partial_student_text += student_text
```

### Fix 4: Ensure Transcript Persistence
**File**: `api/websocket.py`

```python
# In the finally block, ALWAYS persist transcript before cleanup
finally:
    # CRITICAL: Persist final state with complete transcript
    try:
        state = await session.sync_to_state(state)
        await redis.save_state(session_id, dict(state))
        logger.info("Final transcript persisted | turns=%d", len(state.get("transcript", [])))
    except Exception as exc:
        logger.error("CRITICAL: Transcript persist failed | session=%s", session_id)
```

### Fix 5: Coach Report Validation
**File**: `agents/coach.py`

```python
# Add validation before generating report
async def generate_coach_report(state: InterviewState, api_key: str) -> CoachReport:
    transcript = state.get("transcript", [])
    
    # Validate transcript exists and has content
    if not transcript or len(transcript) < 2:
        raise ValueError(
            f"Cannot generate report: transcript has only {len(transcript)} turns. "
            f"Minimum 2 turns required (1 interviewer + 1 student)."
        )
    
    student_turns = [t for t in transcript if t.get("speaker") == "student"]
    if not student_turns:
        raise ValueError("Cannot generate report: no student responses in transcript")
    
    logger.info("Generating report | transcript_turns=%d | student_turns=%d",
                len(transcript), len(student_turns))
```

## Testing Checklist

- [ ] Increase `MIN_TURN_INCREMENT_INTERVAL_SECONDS` to 3.0
- [ ] Test that agent waits for complete answers
- [ ] Test that agent responds when student asks questions
- [ ] Verify transcript is captured in Redis after each turn
- [ ] Verify transcript persists even on unexpected disconnect
- [ ] Verify coach report only generates when transcript has content
- [ ] Test full interview flow: warm_up → deep_dive → stress_test → report
- [ ] Verify report contains actual student quotes, not generic suggestions

## Priority Order

1. **HIGH**: Fix transcript persistence (Fix 3 + 4) - Without this, reports will always be empty
2. **HIGH**: Increase turn interval (Fix 1) - Prevents interruption
3. **MEDIUM**: Enable conversational mode (Fix 2) - Allows Q&A
4. **MEDIUM**: Add report validation (Fix 5) - Prevents bad reports
5. **LOW**: Improve system instructions - Fine-tuning

## Next Steps

1. Apply Fix 3 and Fix 4 immediately (transcript capture/persistence)
2. Test with a real interview session
3. Check Redis to verify transcript is being saved
4. Generate report and verify it contains actual conversation
5. If transcript is captured but report is still generic, debug coach prompt
