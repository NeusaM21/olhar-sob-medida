![Olhar Sob Medida – WhatsApp AI Automation](assets/cover.png)

# 🤖 Olhar Sob Medida  
### Intelligent WhatsApp Automation with Controlled LLM (Anti-Hallucination)

**Olhar Sob Medida** is a **production-ready automation system** built with **FastAPI** and **Google Gemini**, designed for **automated customer service, scheduling, and decision-making**, using a **controlled, deterministic, and auditable AI architecture**.

> ❌ Not a prompt-based chatbot  
> ✅ A **deterministic decision pipeline with orchestrated LLM**, safe for real-world environments

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🎯 Real Business Problem

Traditional AI chatbots often fail in production because they:

- hallucinate prices, services, or schedules  
- mix AI generation with business rules  
- lack human control  
- generate confident but incorrect responses  
- damage business credibility  

In production, **hallucination is not an acceptable error**.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## ✅ Technical Solution

This project solves the problem by applying:

- **LLM used only for language and intent detection**
- **100% deterministic decision logic**
- **External systems as source of truth**
- **Real-time human control**
- **Predictable and traceable pipeline**

Result:  
👉 **AI that does not hallucinate, does not invent, and does not break critical data**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧠 AI Pipeline (Recruiter View)

### LLM Role (Gemini)
- User intent interpretation  
- Natural language interaction  
- Flow direction (no business rule decisions)

### System Role
- Service and price validation  
- Schedule and availability checks  
- Conversation state management  
- Business rules and safe fallbacks  

### Source of Truth
- **Google Sheets** (services, prices, schedule, human control)

WhatsApp → Z-API → FastAPI → Gemini (intent)  
↓  
Deterministic Pipeline  
↓  
Google Sheets

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🛡️ Anti-Hallucination Architecture

- The LLM **cannot generate** prices, services, or schedules  
- All critical data comes from real external sources  
- Responses are always validated before sending  
- Predictable and auditable behavior  

✔️ Ready for **production environments**  
✔️ Safe for **customer-facing automation**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🤝 Human-in-the-Loop (Full Control)

- Automatic **mute / unmute** system  
- A human can take over the conversation at any time  
- AI pauses without conflicts  
- AI automatically resumes after manual interaction  

👉 Combines **automation with human oversight**, enterprise-grade pattern

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🗄️ Data Strategy

> ℹ️ The SQLite database (`olhar_sob_medida.db`) is used only for **local testing and auxiliary data**.  
> Critical data (schedule, services, conversation control) relies on **external trusted sources**.  
> The architecture is prepared for easy migration to PostgreSQL or managed databases.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧩 Tech Stack

- **Python**
- **FastAPI**
- **Google Gemini (LLM)**
- **WhatsApp (Z-API)**
- **Google Sheets (source of truth)**
- **Render (production deployment)**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 📁 Project Structure

```text
olhar-sob-medida/
│
├── backend/
│   ├── ai/
│   │   ├── engine.py              # 🤖 Decision pipeline + controlled LLM
│   │   └── training.py            # Conversation flow tuning
│   │
│   ├── core/
│   │   ├── config.py              # ⚙️ Global configuration
│   │   ├── prompts.py             # 🧠 Controlled LLM prompts
│   │   └── utils.py               # 🔧 Utility functions
│   │
│   ├── db/
│   │   ├── init_db.py             # 🗄️ Local DB initialization
│   │   ├── models.py              # SQLAlchemy models
│   │   └── session.py             # DB session handling
│   │
│   ├── integrations/
│   │   └── sheets.py              # 📊 Google Sheets integration
│   │
│   ├── routes/
│   │   ├── booking.py             # 📅 Scheduling routes
│   │   ├── chat.py                # 💬 Conversation flow
│   │   ├── services.py            # 💼 Services and pricing
│   │   └── webhook.py             # 🔗 WhatsApp webhook (Z-API)
│   │
│   └── app.py                     # 🚀 FastAPI application
│
├── data/
│   ├── price_list.json            # 💰 Services and prices
│   └── services_mapper.json       # Internal service mapping
│
├── docs/
│   ├── fluxo_mvp.md               # 📈 MVP flow
│   ├── fluxo_premium.md           # 🧠 Advanced flow (human control)
│   └── proposta.pdf               # 📄 Conceptual proposal
│
├── tests/
│   ├── test_engine.py             # 🧪 AI pipeline tests
│   └── test_sheets.py             # 🧪 Sheets integration tests
│
├── .env.example                   # 📋 Environment variables example
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```
<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧪 Logs, Errors, and Reliability

- Full exception handling  
- Clear logs for debugging  
- Failures do not break the flow  
- Safe fallbacks for invalid input  

👉 Focus on **stability**, not just nice responses

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🎬 Demo

![Demo](assets/demo.gif)

The demo above shows the system running in a real scenario, including:

- Real WhatsApp conversation  
- LLM-based intent detection  
- Service and schedule validation  
- Automatic booking  
- Handoff to human support  
- Automatic AI resume after manual interaction  

👉 Demonstrates a **controlled decision pipeline**, ready for real-world production use.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 💡 Why Recruiters Care About This Project

This repository demonstrates:
- Responsible and realistic LLM usage  
- AI architecture applied to real business problems  
- Clear separation between AI and business rules  
- Deterministic and auditable pipelines  
- WhatsApp + AI integration in production  
- Engineering mindset, not just prompt design  

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 👩‍💻 Author

Developed by **Neusa M. — AI Automation Engineer**

📧 contact.neusam21@gmail.com  
💻 https://github.com/NeusaM21  
🌐 https://www.linkedin.com/in/NeusaM21  

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 📜 License

This project is licensed under the [MIT License](LICENSE)  
— free for **commercial** and **academic** use.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

<p align="left">
  <a href="https://github.com/NeusaM21">
    <img src="https://img.shields.io/badge/⬅️-Back%20to%20main%20portfolio-blue?style=for-the-badge"/>
  </a>
</p>
