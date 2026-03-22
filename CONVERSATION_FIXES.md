# Conversation & VAD Fixes

## Issues Fixed

### 1. VAD Triggering During AI Speech ✅
**Problem:** When AI was asking a question, the VAD would detect "silence" from the candidate and trigger TURN_COMPLETE prematurely, causing the AI to ask the next question before the candidate could answer.

**Solution:**
- Added explicit check to skip ALL VAD logic when `aiSpeaking` is true
- Reset VAD state (`hasSpokenThisTurn`, `totalSpeechDuration`) when AI starts speaking
- This ensures the candidate can listen to the full question without false triggers

**Code Change (templates/index.html):**
```javascript
// CRITICAL: Skip VAD logic entirely when AI is speaking
if (aiSpeaking) {
  // Reset VAD state when AI is speaking to prevent false triggers
  hasSpokenThisTurn = false;
  totalSpeechDuration = 0;
  return;  // Don't send audio or process VAD
}
```

### 2. Not Interactive - AI Just Asks Questions ✅
**Problem:** AI was acting like an interrogator, just asking pre-set questions and not responding to what the candidate said. If candidate asked a question, AI would ignore it.

**Solution:**
- Updated system instruction to explicitly allow AI to answer candidate questions
- Added "BE INTERACTIVE" rule emphasizing this is a conversation, not an exam
- AI now engages with candidate's responses, not just collects them

**Code Change (core/streaming_manager.py):**
```python
2. BE INTERACTIVE - This is a CONVERSATION, not an interrogation:
   - If the candidate asks you a question, ANSWER IT naturally before continuing
   - If they say something interesting, explore it deeper with follow-ups
   - If they mention a specific technology or approach, discuss it with them
   - Example: Candidate: "Should I have used Redis instead?" → You: "Great question! 
     Redis would definitely work well for caching. What made you consider it? 
     Let's talk through the trade-offs..."
   - Don't just collect answers - ENGAGE with what they're saying
```

### 3. Improved VAD Parameters ✅
**Problem:** VAD was too sensitive, triggering on short noise bursts.

**Solution:**
- Increased `MIN_SPEECH_DURATION` from 800ms to 1500ms
- Increased `SILENCE_DURATION` from 2000ms to 2500ms
- Increased `WAITING_FOR_AI_TIMEOUT` from 10s to 15s
- Added better logging to debug VAD behavior

**New Parameters:**
```javascript
const SILENCE_THRESHOLD = 0.005;      // RMS volume threshold
const SILENCE_DURATION = 2500;        // 2.5 seconds of silence required
const MIN_SPEECH_DURATION = 1500;     // Must speak for 1.5 seconds minimum
const WAITING_FOR_AI_TIMEOUT = 15000; // 15 second timeout
```

### 4. Better Logging ✅
**Problem:** Couldn't debug why VAD was triggering incorrectly.

**Solution:**
- Added "Speech started" log when candidate begins speaking
- Added detailed log showing speech duration vs minimum required
- Added ✅/❌ emojis to clearly show when TURN_COMPLETE is sent or ignored
- Fixed bug where duration was logged after being reset to 0

**New Logs:**
```
Silent VAD: Speech started
Silent VAD: Silence detected. Speech duration: 2500 ms, Min required: 1500 ms
✅ Silent VAD: TURN_COMPLETE sent after 2500 ms of speech
```

or

```
❌ Silent VAD: Ignoring short speech burst ( 800 ms < 1500 ms)
```

## How It Works Now

### Normal Flow:
1. **AI asks question** → `aiSpeaking = true` → VAD disabled
2. **AI finishes speaking** → `aiSpeaking = false` after 600ms → VAD enabled
3. **Candidate starts speaking** → VAD detects speech, starts accumulating duration
4. **Candidate speaks for 1.5+ seconds** → Duration counter increases
5. **Candidate stops speaking** → 2.5 seconds of silence detected
6. **VAD sends TURN_COMPLETE** → AI processes answer and responds
7. **AI responds** → Back to step 1

### Interactive Flow:
1. **Candidate asks a question** → VAD sends TURN_COMPLETE
2. **AI recognizes it's a question** → Answers it naturally
3. **AI continues conversation** → Asks follow-up or moves to next topic

### Edge Cases Handled:
- **Short noise bursts**: Ignored if < 1.5 seconds
- **AI speaking**: VAD completely disabled, no false triggers
- **Long pauses**: 2.5 seconds required before ending turn
- **Candidate interrupts AI**: AI stops immediately (native VAD)

## Testing Checklist

- [ ] AI asks first question
- [ ] Candidate can listen to full question without interruption
- [ ] Candidate speaks for 2+ seconds
- [ ] AI waits for 2.5 seconds of silence before responding
- [ ] AI acknowledges the answer ("I love that approach")
- [ ] AI asks contextual follow-up based on answer
- [ ] Candidate asks AI a question
- [ ] AI answers the question naturally
- [ ] AI continues conversation after answering
- [ ] Short noise bursts (< 1.5s) are ignored
- [ ] Console logs show correct speech durations

## Configuration

If you need to adjust sensitivity:

```javascript
// In templates/index.html

// Make it MORE sensitive (trigger faster):
const SILENCE_DURATION = 2000;        // Reduce to 2 seconds
const MIN_SPEECH_DURATION = 1000;     // Reduce to 1 second

// Make it LESS sensitive (more patient):
const SILENCE_DURATION = 3000;        // Increase to 3 seconds
const MIN_SPEECH_DURATION = 2000;     // Increase to 2 seconds
```

## Known Limitations

1. **Audio buffer size**: Speech duration is approximate based on 4096-sample buffers
2. **Network latency**: TURN_COMPLETE signal has ~100-200ms network delay
3. **Browser differences**: Chrome/Firefox may have slightly different audio processing
4. **Background noise**: Very loud environments may need higher `SILENCE_THRESHOLD`

## Future Improvements

1. **Adaptive VAD**: Adjust thresholds based on environment noise
2. **Visual feedback**: Show when AI is listening vs processing
3. **Manual override**: Let candidate press spacebar to force TURN_COMPLETE
4. **Barge-in detection**: Detect when candidate interrupts AI mid-sentence
5. **Emotion detection**: Adjust AI tone based on candidate's confidence level

## Related Files

- `templates/index.html` - Frontend VAD logic
- `core/streaming_manager.py` - System instruction and conversation rules
- `api/websocket.py` - WebSocket handler for audio streaming

## Support

If VAD is still triggering incorrectly:
1. Check browser console for RMS values and speech duration logs
2. Adjust `SILENCE_THRESHOLD` based on your environment
3. Increase `MIN_SPEECH_DURATION` if false triggers persist
4. Check that `aiSpeaking` flag is working correctly
