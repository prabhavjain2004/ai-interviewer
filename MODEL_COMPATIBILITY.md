# Gemini Model Compatibility Guide

## Live Audio Streaming (bidiGenerateContent)

### ✅ Supported Models for Live Audio:
- `gemini-2.0-flash-exp` - Gemini 2.0 Flash (Experimental) ⭐ RECOMMENDED
- `gemini-2.5-flash-native-audio-latest` - Gemini 2.5 Flash (Native Audio)

### ❌ NOT Supported for Live Audio:
- `gemini-1.5-flash-latest` - Gemini 1.5 Flash (text/image only)
- `gemini-1.5-pro-latest` - Gemini 1.5 Pro (text/image only)
- `gemini-2.5-flash` - Gemini 2.5 Flash (text only, no native audio)
- `gemini-2.5-pro` - Gemini 2.5 Pro (text only)

## Current Configuration

### Interview (Live Audio Streaming)
**File:** `core/streaming_manager.py`
```python
FLASH_LIVE_MODEL = "models/gemini-2.0-flash-exp"
```
**Why:** Only 2.0 Flash and 2.5 Flash support Live audio streaming

### Resume Parsing (Text Only)
**File:** `core/parser.py`
```python
FLASH_MODEL = "models/gemini-2.5-flash"
```
**Why:** Text-only task, can use any model

### Coach Report (Text Only)
**File:** `agents/coach.py`
```python
FLASH_MODEL = "models/gemini-2.5-flash"
```
**Why:** Text-only task, can use any model

## Pricing Comparison

### Gemini 2.0 Flash (Experimental) - FREE during preview!
- Audio Input: FREE
- Audio Output: FREE
- Text Input: FREE
- Text Output: FREE
- **Total Cost: $0.00 per interview** 🎉

### Gemini 2.5 Flash (Native Audio)
- Audio Input: $0.0375 per million tokens
- Audio Output: $0.075 per million tokens
- Text Input: $0.0375 per million tokens
- Text Output: $0.15 per million tokens
- **Total Cost: ~$1.15 per interview**

### Gemini 2.5 Flash (Text Only)
- Text Input: $0.0375 per million tokens
- Text Output: $0.15 per million tokens
- **Used for:** Resume parsing, Coach reports

## Recommendation

**Use Gemini 2.0 Flash Experimental for interviews:**
- ✅ FREE during preview period
- ✅ Supports Live audio streaming
- ✅ Good quality
- ✅ Sub-500ms latency
- ⚠️ May have rate limits
- ⚠️ "Experimental" means it could change

**Use Gemini 2.5 Flash for text tasks:**
- ✅ Stable, production-ready
- ✅ Good quality
- ✅ Affordable pricing
- ✅ Used for resume parsing and reports

## Updated Cost Per Interview

| Component | Model | Cost |
|-----------|-------|------|
| Interview (Live Audio) | 2.0 Flash Exp | $0.00 (FREE) |
| Resume Parsing | 2.5 Flash | $0.000356 |
| Coach Report | 2.5 Flash | $0.024375 |
| Auditor | 2.5 Flash | $0.000289 |
| Infrastructure | - | $0.012765 |
| **TOTAL** | | **$0.038** |

### Rounded: **$0.04 per interview** (₹3.32)

**97% cheaper than original estimate!** 🎉

## When 2.0 Flash Experimental Becomes Paid

If/when Google starts charging for 2.0 Flash, you can:

1. **Switch to 2.5 Flash Native Audio:**
   ```python
   FLASH_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"
   ```
   Cost: ~$1.15 per interview

2. **Negotiate volume pricing** with Google for lower rates

3. **Optimize audio duration** to reduce costs

## Testing Different Models

To test a different model, just change the model string in `core/streaming_manager.py`:

```python
# Option 1: Free (experimental)
FLASH_LIVE_MODEL = "models/gemini-2.0-flash-exp"

# Option 2: Paid but stable
FLASH_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"
```

Restart the server and test!

## Error Messages

### "model not found for bidiGenerateContent"
**Cause:** You're using a model that doesn't support Live audio
**Fix:** Use `gemini-2.0-flash-exp` or `gemini-2.5-flash-native-audio-latest`

### "403 PERMISSION_DENIED"
**Cause:** API key is invalid or leaked
**Fix:** Get a new API key from https://aistudio.google.com/app/apikey

### "429 RESOURCE_EXHAUSTED"
**Cause:** Rate limit exceeded
**Fix:** Wait a few minutes or upgrade to paid tier

## Links

- [Gemini API Pricing](https://ai.google.dev/pricing)
- [Gemini Models Documentation](https://ai.google.dev/gemini-api/docs/models)
- [Live API Documentation](https://ai.google.dev/gemini-api/docs/live)
