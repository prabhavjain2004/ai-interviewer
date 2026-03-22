# Cost Analysis - AI Interview System

## Per-Interview Cost Breakdown (15-minute interview, 7 questions)

### 1. Gemini API Costs

#### A. Interview Phase (Gemini 1.5 Flash Live)
**Model:** `gemini-1.5-flash-latest`

**Audio Input (Student speaking):**
- Duration: ~7 minutes of student speech (assuming 1 min per answer)
- Audio format: 16kHz PCM mono
- Data size: 7 min × 60 sec × 16,000 samples × 2 bytes = ~13.44 MB
- Pricing: $0.0375 per million tokens (audio input) - SAME as 2.5
- Audio tokens: ~13.44 MB ≈ 6,720,000 audio samples ≈ 6.72M tokens
- **Cost: $0.0375 × 6.72 = $0.252**

**Audio Output (AI speaking):**
- Duration: ~8 minutes of AI speech (7 questions + acknowledgments)
- Audio format: 24kHz PCM mono
- Data size: 8 min × 60 sec × 24,000 samples × 2 bytes = ~23.04 MB
- Pricing: $0.075 per million tokens (audio output) - 50% CHEAPER than 2.5!
- Audio tokens: ~23.04 MB ≈ 11.52M tokens
- **Cost: $0.075 × 11.52 = $0.864**

**Text Input (System instructions, context updates):**
- Resume text: ~4,000 characters ≈ 1,000 tokens
- System instruction: ~2,000 tokens
- Context updates (RAG, difficulty changes): ~1,000 tokens
- Total: ~4,000 tokens
- Pricing: $0.0375 per million tokens - SAME as 2.5
- **Cost: $0.0375 × 0.004 = $0.00015**

**Subtotal (Interview Phase): $0.252 + $0.864 + $0.00015 = $1.116**
**SAVINGS vs 2.5 Flash: $0.864 (43% cheaper!)**

#### B. Resume Parsing Phase (Gemini 2.5 Flash)
**Model:** `gemini-2.5-flash-latest`

**Input:**
- Resume text: ~4,000 characters ≈ 1,000 tokens
- Parsing prompt: ~500 tokens
- Total: 1,500 tokens
- Pricing: $0.0375 per million tokens
- **Cost: $0.0375 × 0.0015 = $0.000056**

**Output:**
- Structured JSON: ~2,000 tokens
- Pricing: $0.15 per million tokens
- **Cost: $0.15 × 0.002 = $0.0003**

**Subtotal (Resume Parsing): $0.000056 + $0.0003 = $0.000356**

#### C. Coach Report Generation (Gemini 2.5 Pro)
**Model:** `gemini-2.5-pro`

**Input:**
- Resume JSON: ~2,000 tokens
- Full transcript: ~3,000 tokens (7 Q&A pairs)
- Auditor notes: ~1,000 tokens
- Coach prompt: ~1,500 tokens
- Total: 7,500 tokens
- Pricing: $1.25 per million tokens
- **Cost: $1.25 × 0.0075 = $0.009375**

**Output:**
- Structured report JSON: ~3,000 tokens (6 categories with Elite Scripts)
- Pricing: $5.00 per million tokens
- **Cost: $5.00 × 0.003 = $0.015**

**Subtotal (Coach Report): $0.009375 + $0.015 = $0.024375**

#### D. Auditor Analysis (Gemini 2.5 Flash)
**Model:** `gemini-2.5-flash-latest`

**Per student answer (7 answers total):**
- Input: ~300 tokens (student text + resume context)
- Output: ~200 tokens (auditor metadata)
- Input cost: $0.0375 × 0.0003 = $0.00001125
- Output cost: $0.15 × 0.0002 = $0.00003
- Per answer: $0.00004125
- **Total for 7 answers: $0.00004125 × 7 = $0.000289**

**Subtotal (Auditor): $0.000289**

### 2. Infrastructure Costs (per interview)

#### A. Redis (State Storage)
- Session data: ~50 KB
- Report data: ~20 KB
- Total: ~70 KB per interview
- Redis Cloud pricing: ~$0.00001 per KB
- **Cost: $0.00001 × 70 = $0.0007**

#### B. ChromaDB (Vector Storage for RAG)
- Resume embeddings: ~13 chunks
- Embedding API calls: 13 × $0.0001 = $0.0013
- Storage: ~5 KB
- **Cost: $0.0013 + negligible storage = $0.0013**

#### C. Bandwidth
- Audio upload (student): ~13.44 MB
- Audio download (AI): ~23.04 MB
- Total: ~36.5 MB
- CDN/bandwidth: ~$0.01 per GB
- **Cost: $0.01 × 0.0365 = $0.000365**

#### D. Compute (Server)
- CPU time: ~15 minutes
- AWS t3.medium: $0.0416/hour
- **Cost: $0.0416 × (15/60) = $0.0104**

**Subtotal (Infrastructure): $0.0007 + $0.0013 + $0.000365 + $0.0104 = $0.012765**

---

## Total Cost Per Interview

| Component | Cost (USD) |
|-----------|------------|
| Interview (1.5 Flash Live) | $1.116 |
| Resume Parsing (Flash) | $0.000356 |
| Coach Report (Pro) | $0.024375 |
| Auditor (Flash) | $0.000289 |
| Infrastructure | $0.012765 |
| **TOTAL** | **$1.154** |

### Rounded: **$1.15 per interview**
### **43% CHEAPER than 2.5 Flash!**

---

## Cost in Indian Rupees (INR)

**Exchange Rate:** 1 USD = ₹83 (as of March 2026)

**Total Cost: $1.15 × 83 = ₹95.45**

### Rounded: **₹95 per interview**
### **43% CHEAPER than 2.5 Flash (was ₹168)!**

---

## Cost Optimization Strategies

### 1. Reduce Audio Output Cost (Biggest expense)
**Current:** $0.864 (75% of total cost) - Already 50% cheaper with 1.5 Flash!

**Additional Optimizations:**
- Shorter AI responses (target 20 sec instead of 30 sec)
- Fewer acknowledgments (validate every 2 answers instead of every answer)
- **Potential savings:** 30% → $0.26 saved → **New cost: $0.85/interview**

### 2. Use Flash for Auditor (Already doing ✅)
**Current:** $0.000289
- Already optimized by using Flash instead of Pro

### 3. Batch Resume Parsing
**Current:** $0.000356 per interview
- Cache parsed resumes for 24 hours
- If user does multiple interviews, reuse parsed resume
- **Potential savings:** 50% on repeat users

### 4. Optimize Coach Report
**Current:** $0.024375
- Use Flash instead of Pro for initial draft, Pro only for refinement
- **Potential savings:** 60% → $0.015 saved → **New cost: $0.009/interview**

### 5. Self-hosted Infrastructure
**Current:** $0.012765
- Use self-hosted Redis instead of Redis Cloud
- Use in-memory ChromaDB for small scale
- **Potential savings:** 80% → $0.010 saved → **New cost: $0.002/interview**

---

## Optimized Cost Breakdown

| Component | Original (1.5 Flash) | Optimized | Savings |
|-----------|---------------------|-----------|---------|
| Interview (1.5 Flash Live) | $1.116 | $0.598 | $0.518 |
| Resume Parsing | $0.000356 | $0.000178 | $0.000178 |
| Coach Report | $0.024375 | $0.009 | $0.015375 |
| Auditor | $0.000289 | $0.000289 | $0 |
| Infrastructure | $0.012765 | $0.002 | $0.010765 |
| **TOTAL** | **$1.154** | **$0.610** | **$0.544** |

### Optimized Cost: **$0.61 per interview** (USD)
### Optimized Cost: **₹51 per interview** (INR)
### **70% CHEAPER than original 2.5 Flash estimate!**

---

## Pricing Strategy Recommendations

### Option 1: Freemium Model

**Free Tier:**
- 3 interviews per month
- Basic report (no Elite Scripts)
- Cost to you: $1.47 × 3 = $4.41/month per user
- Target: 70% of users stay on free tier

**Pro Tier: $19/month**
- Unlimited interviews
- Full reports with Elite Scripts
- Interview recordings
- Progress tracking
- Break-even: 13 interviews/month ($1.47 × 13 = $19.11)
- Target: 30% conversion rate

**Expected Revenue:**
- 1,000 users: 700 free + 300 paid
- Revenue: 300 × $19 = $5,700/month
- Costs: (700 × $4.41) + (300 × 13 × $1.47) = $3,087 + $5,733 = $8,820/month
- **Net: -$3,120/month** (need more paid users or higher price)

### Option 2: Pay-Per-Interview

**Pricing: $9.99 per interview**
- Cost: $0.61 (optimized with 1.5 Flash)
- Profit: $9.38 per interview
- Margin: 94%

**Volume Discounts:**
- 1 interview: $9.99
- 5 interviews: $39.99 ($8/each) - 20% discount
- 10 interviews: $69.99 ($7/each) - 30% discount

### Option 3: Subscription Tiers

**Basic: $29/month**
- 10 interviews/month
- Basic reports
- Cost: $0.61 × 10 = $6.10
- Profit: $22.90/month
- Margin: 79%

**Pro: $49/month**
- 25 interviews/month
- Full reports + recordings
- Cost: $0.61 × 25 = $15.25
- Profit: $33.75/month
- Margin: 69%

**Enterprise: $199/month**
- Unlimited interviews
- Custom tracks
- Team accounts
- Assume 100 interviews/month
- Cost: $0.61 × 100 = $61
- Profit: $138/month
- Margin: 69%

### Option 4: University/Corporate Licensing

**University License: $999/year**
- 500 students
- 2 interviews per student = 1,000 interviews/year
- Cost: $0.61 × 1,000 = $610/year
- **Profit: $389/year**
- **Margin: 39%** ✅ Now profitable!

**Adjusted: $1,999/year** (more competitive)
- Cost: $610
- Profit: $1,389/year
- Margin: 69%

**Corporate License: $2,999/year** (reduced from $4,999)
- 100 employees
- 5 interviews per employee = 500 interviews/year
- Cost: $0.61 × 500 = $305/year
- Profit: $2,694/year
- Margin: 90%

---

## Recommended Pricing (My Suggestion)

### For Individual Users:

**Pay-Per-Interview:**
- Single interview: **$9.99** (₹829)
- 5-pack: **$39.99** ($8 each) (₹3,319)
- 10-pack: **$69.99** ($7 each) (₹5,809)

**Why this works:**
- High margin (85%)
- No commitment required
- Users pay only when they need it
- Clear value proposition

### For Students (Discounted):

**Student Plan: $4.99 per interview**
- Requires .edu email verification
- Cost: $1.47
- Profit: $3.52
- Margin: 70%
- Makes it accessible to students

### For Universities:

**University License: $2,999/year**
- Up to 500 students
- 2 interviews per student
- Cost: $1,470
- Profit: $1,529
- Margin: 51%

### For Companies:

**Corporate License: $4,999/year**
- Up to 100 employees
- 5 interviews per employee
- Cost: $735
- Profit: $4,264
- Margin: 85%

---

## Break-Even Analysis

### To break even at different price points:

| Price per Interview | Interviews Needed | Monthly Revenue |
|---------------------|-------------------|-----------------|
| $4.99 (Student) | 1,000 | $4,990 |
| $9.99 (Regular) | 500 | $4,995 |
| $19.99 (Premium) | 250 | $4,998 |

**Fixed Costs (Monthly):**
- Server: $50
- Domain: $2
- Monitoring: $10
- Total: $62

**Break-even (at $9.99/interview):**
- Need: 62 / 8.52 = 8 interviews/month
- Very achievable!

---

## Scaling Considerations

### At 1,000 interviews/month:
- Revenue (at $9.99): $9,990
- Costs: ($0.61 × 1,000) + $62 = $672
- Profit: $9,318
- Margin: 93%

### At 10,000 interviews/month:
- Revenue: $99,900
- Costs: ($0.61 × 10,000) + $62 = $6,162
- Profit: $93,738
- Margin: 94%

### At 100,000 interviews/month:
- Revenue: $999,000
- Costs: ($0.61 × 100,000) + $62 = $61,062
- Profit: $937,938
- Margin: 94%

**Note:** At scale, negotiate volume discounts with Google for Gemini API (can reduce costs by 30-50%)

---

## Competitor Pricing (for reference)

- **Pramp:** Free (peer-to-peer, not AI)
- **Interviewing.io:** $99/month (unlimited, human interviewers)
- **Exponent:** $39/month (courses + practice)
- **LeetCode Premium:** $35/month (coding only)
- **Ribbon.ai:** Unknown (enterprise only)

**Your competitive advantage:**
- Lower price than human interviewers
- Higher quality than free peer practice
- Instant availability (no scheduling)
- Personalized feedback (Mirror & Mentor)

---

## Final Recommendation

**Start with Pay-Per-Interview model:**

**Pricing:**
- Regular: $9.99 per interview (₹829)
- Student (with .edu): $4.99 per interview (₹414)
- 5-pack: $39.99 (₹3,319)
- 10-pack: $69.99 (₹5,809)

**Why:**
1. **High margin** (85%) gives you room to experiment
2. **Low barrier to entry** (no subscription commitment)
3. **Scales well** (more users = more revenue)
4. **Simple pricing** (easy to understand)
5. **Competitive** (cheaper than alternatives)

**Later, add subscription tiers** once you have:
- 1,000+ users
- Usage data showing average interviews per user
- Feature differentiation (Pro features)

---

## Cost Monitoring

Track these metrics:
1. **Average cost per interview** (should stay ~$1.47)
2. **Gemini API usage** (biggest cost driver)
3. **Infrastructure costs** (should be <5% of total)
4. **Margin per interview** (target 80%+)
5. **Break-even point** (interviews needed to cover fixed costs)

Set up alerts:
- If cost per interview > $2.00 → investigate
- If margin < 70% → raise prices or optimize
- If infrastructure > 10% of costs → optimize or scale

---

## Questions?

Let me know if you want me to:
1. Create a pricing page design
2. Set up Stripe integration for payments
3. Build a usage tracking dashboard
4. Implement volume discounts
5. Add student verification (.edu emails)
