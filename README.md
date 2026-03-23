# 🎤 AI Technical Interviewer & Mentor

> **Open-source AI-powered technical interview platform with real-time voice interaction and elite coaching feedback.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-orange.svg)](https://ai.google.dev/)

A next-generation interview practice platform that conducts **real-time voice interviews** using Google's Gemini Live API, analyzes your performance in real-time, and delivers **Mirror & Mentor coaching reports** with actionable feedback and elite answer scripts.

---

## ✨ Features

### 🎯 Real-Time Voice Interview
- **Sub-500ms latency** voice-to-voice conversation using Gemini 2.5 Flash Live
- **Natural interruptions** supported via Voice Activity Detection (VAD)
- **Resume-grounded questions** - every question references your actual projects and experience
- **Progressive difficulty** - warm-up → deep dive → stress test phases
- **Live video feed** - Google Meet-style interface with camera display (not recorded)

### 📊 Real-Time Performance Analysis
- **Communication heatmap** - live tracking of hesitation, filler words, and clarity
- **Technical depth scoring** - measures how well you explain your resume claims
- **Red flag detection** - identifies vague answers, missing metrics, and weak ownership
- **Live transcript** - see the conversation unfold in real-time

### 🎓 Elite Coaching Reports
- **Mirror & Mentor methodology** - compares what you said vs. what you claimed on your resume
- **6 Wellfound categories** - Technical Depth, Communication Clarity, Resume Consistency, Problem-Solving, Ownership & Impact, Cultural Fit
- **Elite answer scripts** - STAR-formatted rewrites with metrics and industry terminology
- **Actionable diagnosis** - specific, named weaknesses (not generic feedback)

---

## 🏗️ Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Live Layer (Speed)                                │
│  • Gemini 2.5 Flash Live - Real-time voice interview        │
│  • WebSocket bidirectional audio streaming                  │
│  • Voice Activity Detection (VAD) for natural conversation  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Logic Layer (Orchestration)                       │
│  • LangGraph state machine - Phase transitions             │
│  • Parallel Auditor - Real-time red flag detection         │
│  • Redis state persistence - Stateless workers             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Coaching Layer (Quality)                          │
│  • Gemini 2.5 Flash - Post-interview analysis              │
│  • Mirror & Mentor report generation                        │
│  • Elite Script rewrites with STAR structure               │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (async Python) |
| **Orchestration** | LangGraph (stateful workflows) |
| **Live Interview** | Gemini 2.5 Flash Live (Native Audio) |
| **Coaching** | Gemini 2.5 Flash |
| **State Store** | Upstash Redis (24hr TTL) |
| **Resume Parsing** | Gemini 2.5 Flash (entity extraction) |
| **Frontend** | Vanilla JS + WebSocket |
| **Audio** | WebRTC getUserMedia + AudioContext |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Google Gemini API Key** ([Get one here](https://ai.google.dev/))
- **Upstash Redis** ([Free tier available](https://upstash.com/))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-interviewer-mentor.git
   cd ai-interviewer-mentor
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your credentials:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
   UPSTASH_REDIS_REST_TOKEN=your_redis_token_here
   SESSION_TTL_SECONDS=86400
   ALLOWED_ORIGINS=*
   PORT=8000
   ```

4. **Run the server**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Open your browser**
   ```
   http://localhost:8000
   ```

---

## 📖 Usage

### 1. Upload Your Resume
- Drag & drop or browse for your resume (PDF, TXT, or MD)
- The system extracts projects, tech stack, and quantifiable achievements
- Parsing takes 3-5 seconds using Gemini's entity extraction

### 2. Start the Interview
- Click "Start Interview" to begin
- Grant camera and microphone permissions
- The AI interviewer will greet you and start with warm-up questions

### 3. Answer Naturally
- Speak naturally - the AI supports interruptions
- Your camera feed is displayed (not recorded)
- Live transcript and performance heatmap update in real-time

### 4. Review Your Report
- Click "End Interview" when finished
- Wait 10-15 seconds for the coaching report to generate
- Review your scores, diagnosis, and elite answer scripts

---

## 🎯 Interview Phases

### Phase 1: Warm-Up (2 questions)
- Conversational, non-technical questions
- Build rapport and understand career goals
- No resume grounding required yet

### Phase 2: Deep Dive (5 questions)
- Every question references a specific resume entity (project, company, tech)
- Progressive difficulty: easy → medium → challenging
- Focus on architecture decisions, trade-offs, and implementation details

### Phase 3: Stress Test (3 questions)
- Edge cases, scalability, and failure scenarios
- "What would break first if you had 10x the load?"
- Challenge assumptions and probe for robustness

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL | Required |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis token | Required |
| `SESSION_TTL_SECONDS` | Session expiry time | 86400 (24 hours) |
| `MAX_TURNS_WARM_UP` | Warm-up phase questions | 2 |
| `MAX_TURNS_DEEP_DIVE` | Deep dive phase questions (cumulative) | 7 |
| `MAX_TURNS_STRESS_TEST` | Stress test phase questions (cumulative) | 10 |
| `ALLOWED_ORIGINS` | CORS allowed origins | * |
| `PORT` | Server port | 8000 |

### Interview Customization

Edit `core/streaming_manager.py` to customize:
- System instruction prompts
- Phase transition thresholds
- Difficulty ramping logic
- Entity grounding rules

---

## 📁 Project Structure

```
.
├── agents/                 # Multi-agent system
│   ├── interviewer.py     # Agent 1: Real-time interviewer
│   ├── auditor.py         # Agent 2: Parallel performance analyzer
│   └── coach.py           # Agent 3: Post-interview coaching
├── api/                   # FastAPI routes
│   ├── routes/
│   │   ├── session.py     # Session management
│   │   ├── resume.py      # Resume upload & parsing
│   │   └── report.py      # Coaching report retrieval
│   ├── websocket.py       # WebSocket audio bridge
│   └── deps.py            # Dependency injection
├── core/                  # Core logic
│   ├── orchestrator.py    # LangGraph state machine
│   ├── streaming_manager.py  # Gemini Live wrapper
│   ├── state.py           # Pydantic state models
│   └── parser.py          # Resume parsing logic
├── services/              # External services
│   └── redis_client.py    # Upstash Redis client
├── templates/             # Frontend
│   └── index.html         # Single-page app
├── prompts/               # System prompts
│   ├── interviewer_system.txt
│   └── coach_system.txt
├── Docs/                  # Documentation
│   ├── architecture.md    # System design
│   ├── rules.md           # Development rules
│   └── resume_usage.md    # Resume injection analysis
├── main.py                # FastAPI app entry point
├── requirements.txt       # Python dependencies
└── .env.example           # Environment template
```

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Areas for Contribution

1. **Mobile Responsiveness** - Optimize UI for mobile devices
2. **Browser Compatibility** - Test and fix issues on Safari, Firefox, Edge
3. **WebSocket Reconnection** - Implement auto-reconnect on network hiccups
4. **Multi-Language Support** - Add i18n for non-English interviews
5. **Custom Interview Modes** - Quick interview, behavioral-only, etc.
6. **Real-Time Hints** - Live coaching during the interview
7. **Analytics Dashboard** - Track completion rates, scores, drop-offs

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit with clear messages (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use type hints for all function signatures
- Add docstrings for public functions
- Keep functions under 50 lines when possible
- Use async/await for I/O operations

---

## 📊 Performance

- **Interview latency:** < 500ms voice-to-voice
- **Resume parsing:** 3-5 seconds (one-time)
- **Coaching report:** 10-15 seconds (post-interview)
- **Concurrent sessions:** Unlimited (stateless workers)
- **Cost per interview:** ~$0.01 (Gemini API usage)

---

## 🔒 Privacy & Security

- **No audio/video recording** - Camera feed is displayed but never stored
- **Resume auto-deletion** - Original files deleted after parsing
- **24-hour TTL** - All session data expires automatically
- **No PII in logs** - Only session IDs and metadata logged
- **HTTPS required** - WebSocket Secure (WSS) in production

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024 [Your Name/Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

- **Google Gemini** - For the incredible Live API and Flash models
- **LangGraph** - For stateful orchestration primitives
- **Upstash** - For serverless Redis with generous free tier
- **FastAPI** - For the blazing-fast async Python framework
- **Wellfound** - For the feedback category framework inspiration

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/ai-interviewer-mentor/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/ai-interviewer-mentor/discussions)
- **Email:** your.email@example.com

---

## 🗺️ Roadmap

### Q2 2024
- [ ] Mobile app (React Native)
- [ ] Multi-language support (Spanish, French, Hindi, Chinese)
- [ ] Custom interview modes (Quick, Behavioral, System Design)
- [ ] Real-time hints during interview

### Q3 2024
- [ ] Team accounts with analytics dashboard
- [ ] Interview recording (opt-in)
- [ ] Shareable interview links for recruiters
- [ ] A/B testing framework for prompts

### Q4 2024
- [ ] Integration with ATS platforms (Greenhouse, Lever)
- [ ] White-label solution for enterprises
- [ ] Advanced analytics (ML-powered insights)
- [ ] Mobile-first redesign

---

## ⭐ Star History

If you find this project useful, please consider giving it a star! It helps others discover the project.

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/ai-interviewer-mentor&type=Date)](https://star-history.com/#yourusername/ai-interviewer-mentor&Date)

---

**Built with ❤️ by developers, for developers.**

*Practice like you're interviewing at Google. Get feedback like you hired a $500/hr coach.*
