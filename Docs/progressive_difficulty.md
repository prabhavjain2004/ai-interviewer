# Progressive Difficulty Ramping

## Overview
The interview now gradually increases question difficulty to prevent candidates from getting discouraged early while still testing their technical depth.

## How It Works

### Difficulty Levels

**EASY (Turns 1-2 of deep-dive)**
- High-level architecture questions
- "What did you build and why?"
- Focus on understanding the project scope
- Accessible, confidence-building questions
- Example: "Walk me through the architecture of [PROJECT] — what were the main components?"

**MEDIUM (Turns 3-4 of deep-dive)**
- Implementation details and trade-offs
- "Why did you choose X over Y?"
- Deeper technical exploration
- Evaluate decision-making process
- Example: "Why did you choose [TECH_X] over [TECH_Y] for that use case? What trade-offs did you evaluate?"

**CHALLENGING (Turns 5+ of deep-dive)**
- Edge cases, scalability, failure scenarios
- "What would break under stress?"
- Advanced problem-solving
- Test depth of understanding
- Example: "If [PROJECT] had to handle 10x the load overnight, what would break first and how would you address it?"

## Implementation Details

### Automatic Difficulty Updates
The system automatically updates the difficulty level every 2 turns during the deep-dive phase:

```python
# In core/streaming_manager.py
if self.phase == "deep_dive" and self.turn_count - self._last_system_instruction_turn >= 2:
    await self._update_difficulty_level()
```

### System Instruction Injection
When difficulty changes, a new system instruction is injected into the Gemini Live session:

```python
await self._live_session.send_client_content(
    turns=genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=(
            f"[SYSTEM: Difficulty level now {difficulty_label}. "
            f"Adjust question complexity accordingly while maintaining conversational flow.]"
        ))],
    ),
    turn_complete=False,
)
```

### Logging
Difficulty changes are logged for debugging and analytics:

```
2026-03-22 21:15:30 | INFO | core.streaming_manager | Difficulty updated | session_id=abc123 | turn=3 | level=MEDIUM
```

## Benefits

1. **Reduces Early Dropout**: Candidates don't get overwhelmed in the first few questions
2. **Builds Confidence**: Easy questions help candidates get into flow state
3. **Better Assessment**: Gradually reveals depth of knowledge
4. **Natural Progression**: Mimics real interview flow
5. **Maintains Engagement**: Keeps candidates interested throughout

## Example Question Progression

**Turn 1 (EASY):**
> "I see you built a recommendation system for [PROJECT]. Walk me through the high-level architecture — what were the main components?"

**Turn 2 (EASY):**
> "That makes sense. What was the primary goal you were trying to achieve with this system?"

**Turn 3 (MEDIUM):**
> "Interesting approach. Why did you choose collaborative filtering over content-based filtering? What trade-offs did you consider?"

**Turn 4 (MEDIUM):**
> "I like how you thought through that. How did you handle the cold start problem for new users?"

**Turn 5 (CHALLENGING):**
> "Smart solution. If your user base suddenly grew 10x overnight, what would break first in your recommendation pipeline and how would you fix it?"

**Turn 6 (CHALLENGING):**
> "That shows good architectural thinking. What about data consistency — how would you handle a scenario where user preferences are being updated while recommendations are being generated?"

## Configuration

The difficulty thresholds are defined in `build_system_instruction()`:

```python
if phase == "deep_dive":
    if turn_count <= 3:
        difficulty_guidance = "EASY"
    elif turn_count <= 5:
        difficulty_guidance = "MEDIUM"
    else:
        difficulty_guidance = "CHALLENGING"
```

These can be adjusted based on:
- Candidate experience level
- Interview track (startup vs FAANG)
- Time constraints
- Company requirements

## Future Enhancements

1. **Adaptive Difficulty**: Adjust based on answer quality
   - If candidate struggles with EASY questions, stay at EASY longer
   - If candidate excels at EASY questions, skip to MEDIUM faster

2. **Difficulty Visualization**: Show candidate their current difficulty level
   - Progress bar: EASY → MEDIUM → CHALLENGING
   - Gamification element

3. **Custom Difficulty Curves**: Different curves for different roles
   - Intern: Mostly EASY, some MEDIUM
   - Mid-level: Balanced across all three
   - Senior: Mostly CHALLENGING

4. **Difficulty Feedback in Report**: Show how candidate performed at each level
   - "Strong at EASY questions (100%)"
   - "Struggled with CHALLENGING questions (40%)"

## Testing

To test the progressive difficulty:

1. Start an interview
2. Watch the console logs for difficulty updates
3. Observe question complexity increasing
4. Check that turn 1-2 are high-level
5. Verify turn 3-4 dig into details
6. Confirm turn 5+ push on edge cases

## Metrics to Track

- **Dropout rate by turn**: Are candidates leaving early?
- **Answer quality by difficulty**: Do answers get worse at CHALLENGING?
- **Time per answer by difficulty**: Do CHALLENGING questions take longer?
- **Candidate satisfaction**: Do they feel the progression was natural?

## Related Files

- `core/streaming_manager.py`: Main implementation
- `agents/interviewer.py`: Phase thresholds
- `Docs/interview_improvements.md`: Overall improvements
- `Docs/future_improvements.md`: Future enhancement ideas
