# Troubleshooting: Report Not Generating

## Problem
The frontend keeps polling `/report/{session_id}` every 3 seconds and always gets `202 Accepted` (report not ready). The coach agent is triggered but the report never appears.

## Root Causes (Possible)

### 1. Empty Transcript
**Most Likely Issue**

The coach requires at least 2 turns (1 interviewer + 1 student) to generate a report. If the interview ended before any real conversation happened, the transcript will be empty or too short.

**How to Check:**
```bash
# Call the debug endpoint
curl http://your-domain/debug/session/bb04b3bb-889e-4f7b-8ae9-7fa32090f841
```

Look for:
- `transcript_total`: Should be >= 2
- `transcript_student`: Should be >= 1
- `transcript_interviewer`: Should be >= 1

**Why This Happens:**
- User clicked "End Interview" immediately after starting
- WebSocket disconnected before any audio was exchanged
- Flash Live connection failed but WebSocket stayed open
- Transcript not persisted to Redis before coach ran

**Fix:**
The coach now validates transcript length and logs detailed errors. Check logs for:
```
CRITICAL: Empty transcript in coach background task
```

### 2. Coach Agent Crashing Silently
**Second Most Likely**

The coach agent might be throwing an exception that's being caught and logged but not visible in your current log view.

**How to Check:**
Look for these log patterns:
```
Coach background task starting | session=... | transcript_turns=...
Coach report generated successfully | session=... | score=...
Coach report saved to Redis | key=...
```

If you see "starting" but NOT "generated successfully", the coach crashed.

**Common Crash Reasons:**
- Gemini API rate limit hit
- Invalid API key
- Malformed transcript data
- JSON parsing error from Gemini response
- Network timeout

**Fix:**
I've added detailed error logging with full tracebacks. Check logs for:
```
Coach background task failed | session=... | error=... | traceback=...
```

### 3. Redis Save Failing
**Less Likely**

The report might be generated but failing to save to Redis.

**How to Check:**
Look for this log line:
```
Coach report saved to Redis | key=session:...:report
```

If you see "generated successfully" but NOT "saved to Redis", Redis write failed.

**Common Reasons:**
- Redis connection lost
- Redis out of memory
- Redis key TTL expired before save
- Network issue with Upstash

**Fix:**
Check Redis connection health and Upstash dashboard for errors.

### 4. Race Condition: State Not Persisted
**Timing Issue**

The WebSocket might close and trigger the coach before the final transcript is persisted to Redis.

**How to Check:**
Look for this log sequence:
```
Session ended cleanly | session=... | turns=... | transcript_turns=...
Reloaded fresh state from Redis | transcript_turns=...
Coach report triggered with fresh state | session=...
```

If "transcript_turns" is 0 in the reloaded state, the transcript wasn't saved yet.

**Fix:**
The websocket handler now reloads state from Redis before triggering coach to ensure fresh data.

## Diagnostic Steps

### Step 1: Check Session State
```bash
curl http://your-domain/debug/session/bb04b3bb-889e-4f7b-8ae9-7fa32090f841
```

Expected response:
```json
{
  "session_id": "bb04b3bb-889e-4f7b-8ae9-7fa32090f841",
  "status": "finished",
  "turn_count": 8,
  "transcript_total": 16,
  "transcript_student": 8,
  "transcript_interviewer": 8,
  "has_report": false,
  "transcript_preview": [...],
  "auditor_notes_count": 8,
  "resume_exists": true
}
```

**Red Flags:**
- `transcript_total` < 2 → Interview ended too early
- `transcript_student` = 0 → No student responses recorded
- `status` != "finished" → Interview not properly closed
- `resume_exists` = false → Resume not loaded

### Step 2: Check Logs for Coach Execution
Search logs for the session ID and look for:

**Good Path:**
```
Session ended cleanly | session=bb04... | turns=8 | transcript_turns=16
Reloaded fresh state from Redis | transcript_turns=16
Coach report triggered with fresh state | session=bb04...
Coach background task starting | session=bb04... | transcript_turns=16
Transcript preview | session=bb04... | first_3_turns=[...]
Calling generate_coach_report | session=bb04...
Coach report generated successfully | session=bb04... | score=7.5
Coach report saved to Redis | key=session:bb04...:report
```

**Bad Path (Empty Transcript):**
```
Session ended cleanly | session=bb04... | turns=0 | transcript_turns=0
Reloaded fresh state from Redis | transcript_turns=0
CRITICAL: Empty transcript in coach background task | session=bb04...
```

**Bad Path (Coach Crash):**
```
Coach background task starting | session=bb04... | transcript_turns=16
Calling generate_coach_report | session=bb04...
Coach background task failed | session=bb04... | error=... | traceback=...
```

### Step 3: Check Redis Directly
If you have access to Upstash console:

1. Go to Upstash Redis dashboard
2. Search for key: `session:bb04b3bb-889e-4f7b-8ae9-7fa32090f841:state`
3. Check if transcript field exists and has data
4. Search for key: `session:bb04b3bb-889e-4f7b-8ae9-7fa32090f841:report`
5. Check if report exists

### Step 4: Manual Coach Trigger (Advanced)
If you have shell access to the server:

```python
import asyncio
from services.redis_client import RedisClient
from agents.coach import run_coach_background
import os

async def manual_trigger():
    redis = RedisClient(
        url=os.getenv("UPSTASH_REDIS_REST_URL"),
        token=os.getenv("UPSTASH_REDIS_REST_TOKEN"),
        ttl=86400
    )
    await redis.connect()
    
    session_id = "bb04b3bb-889e-4f7b-8ae9-7fa32090f841"
    state = await redis.load_state(session_id)
    
    print(f"Transcript turns: {len(state.get('transcript', []))}")
    print(f"Status: {state.get('status')}")
    
    api_key = os.getenv("GEMINI_API_KEY")
    await run_coach_background(state, api_key, redis)
    
    report = await redis.load_report(session_id)
    print(f"Report generated: {report is not None}")

asyncio.run(manual_trigger())
```

## Solutions

### Solution 1: Prevent Empty Transcript
**Frontend Change:**

Disable "End Interview" button until at least 1 student turn is recorded:

```javascript
// In templates/index.html
let studentTurnCount = 0;

function appendTranscript(speaker, text) {
  // ... existing code ...
  if (speaker === 'student') {
    studentTurnCount++;
    if (studentTurnCount >= 1) {
      document.getElementById('btn-end').disabled = false;
    }
  }
}

// Initially disable the button
document.getElementById('btn-end').disabled = true;
```

### Solution 2: Better Error Messages
**Frontend Change:**

Show specific error when report fails:

```javascript
async function pollReport(attempts = 0) {
  if (attempts > 40) {
    toast('Report generation failed. Please contact support with session ID: ' + sessionId, 10000);
    return;
  }
  try {
    const res = await fetch(`/report/${sessionId}`);
    if (res.status === 202) {
      setTimeout(() => pollReport(attempts + 1), 3000);
      return;
    }
    if (res.status === 400) {
      const error = await res.json();
      toast('Report error: ' + error.detail, 10000);
      return;
    }
    // ... rest of code
  }
}
```

### Solution 3: Retry Logic
**Backend Change:**

Add retry logic for transient Gemini API failures:

```python
# In agents/coach.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def generate_coach_report_with_retry(state, api_key):
    return await generate_coach_report(state, api_key)
```

### Solution 4: Fallback Report
**Backend Change:**

Generate a minimal report if coach fails:

```python
async def run_coach_background(state, api_key, redis_client):
    session_id = state.get("session_id", "unknown")
    try:
        # ... existing code ...
        report = await generate_coach_report(state, api_key)
        await redis_client.save_report(session_id, report.model_dump(mode="json"))
    except Exception as exc:
        logger.error("Coach failed, generating fallback report | session=%s", session_id)
        # Generate minimal fallback report
        fallback = {
            "session_id": session_id,
            "overall_score": 5.0,
            "summary": "We encountered an issue generating your detailed report. Please try again or contact support.",
            "feedback": []
        }
        await redis_client.save_report(session_id, fallback)
```

## Quick Fix for Current Session

For the stuck session `bb04b3bb-889e-4f7b-8ae9-7fa32090f841`:

1. Check debug endpoint: `GET /debug/session/bb04b3bb-889e-4f7b-8ae9-7fa32090f841`
2. If transcript is empty, the interview ended too early - no report can be generated
3. If transcript exists but report failed, check logs for the exact error
4. If needed, manually trigger coach using the Python script above

## Prevention

1. **Minimum Turn Requirement:** Don't allow ending interview until at least 2 turns
2. **Better Logging:** All changes above add detailed logging
3. **Health Checks:** Add `/health/coach` endpoint to test report generation
4. **Monitoring:** Set up alerts for "Coach background task failed" log lines
5. **User Feedback:** Show "Generating report..." with progress indicator instead of silent polling
