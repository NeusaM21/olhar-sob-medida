🌎 English version available: [README_EN.md](README_EN.md)

![Olhar Sob Medida – WhatsApp AI Automation](assets/cover.png)

![Python](https://img.shields.io/badge/Python-3.x-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![LLM](https://img.shields.io/badge/LLM-Gemini-orange)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Z--API-brightgreen)
![Deploy](https://img.shields.io/badge/Deploy-Render-success)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

# 🤖 Olhar Sob Medida  
### Automação Inteligente via WhatsApp com LLM Controlado (Anti-Alucinação)

**Olhar Sob Medida** é um **sistema de automação profissional em produção**, desenvolvido com **FastAPI** e **Google Gemini**, projetado para **atendimento automatizado, agendamento e tomada de decisão**, utilizando uma **arquitetura de IA controlada, determinística e auditável**.

> ❌ Não é um chatbot baseado em prompt  
> ✅ É um **pipeline de decisão com LLM orquestrado**, seguro para uso em ambientes reais

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🎯 Problema Real de Negócio

Chatbots tradicionais com IA costumam falhar porque:

- inventam preços, serviços ou horários  
- misturam IA com regras de negócio  
- não permitem controle humano  
- geram respostas erradas com confiança  
- quebram a credibilidade da empresa  

Em produção, **alucinação ≠ erro aceitável**.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## ✅ Solução Técnica

Este projeto resolve o problema usando:

- **LLM apenas para linguagem e intenção**
- **Lógica de decisão 100% determinística**
- **Fontes externas como “source of truth”**
- **Controle humano em tempo real**
- **Pipeline previsível e rastreável**

Resultado:  
👉 **IA que não alucina, não inventa e não erra dados críticos**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧠 Pipeline de IA (Visão de Recrutador)

### Papel do LLM (Gemini)
- Interpretação de intenção do usuário  
- Linguagem natural e fluidez da conversa  
- Direcionamento do fluxo (sem decidir regras)

### Papel do Sistema
- Validação de serviços e preços  
- Verificação de agenda e disponibilidade  
- Gerenciamento de estado da conversa  
- Regras de negócio e fallback seguro  

### Fonte da Verdade
- **Google Sheets** (serviços, preços, agenda, controle humano)

WhatsApp → Z-API → FastAPI → Gemini (intenção)
↓
Pipeline Determinístico
↓
Google Sheets

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🛡️ Arquitetura Anti-Alucinação

- O LLM **não pode criar** preços, serviços ou horários  
- Todos os dados críticos vêm de fontes reais  
- Respostas são sempre validadas antes do envio  
- Comportamento previsível e auditável  

✔️ Pronto para **ambiente produtivo**  
✔️ Seguro para **atendimento ao cliente**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🤝 Human-in-the-Loop (Controle Total)

- Sistema de **mute / unmute automático**
- Humano pode assumir a conversa a qualquer momento
- IA pausa sem gerar conflitos
- IA retoma automaticamente após atendimento manual

👉 Combina **automação + controle humano**, padrão enterprise

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🗄️ Estratégia de Dados

> ℹ️ O banco SQLite (`olhar_sob_medida.db`) é usado apenas para **testes locais e dados auxiliares**.  
> Dados críticos (agenda, serviços, controle de atendimento) utilizam **fontes externas confiáveis**.  
> Arquitetura preparada para migração simples para PostgreSQL ou bancos gerenciados.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧩 Stack Tecnológica

- **Python**
- **FastAPI**
- **Google Gemini (LLM)**
- **WhatsApp (Z-API)**
- **Google Sheets (source of truth)**
- **Render (deploy em produção)**

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 📁 Estrutura do Projeto

```text
olhar-sob-medida/
│
├── backend/
│   ├── ai/
│   │   ├── engine.py              # 🤖 Pipeline de decisão + LLM controlado
│   │   └── training.py            # Ajustes e fluxos de conversação
│   │
│   ├── core/
│   │   ├── config.py              # ⚙️ Configurações globais
│   │   ├── prompts.py             # 🧠 Prompts controlados do LLM
│   │   └── utils.py               # 🔧 Funções utilitárias
│   │
│   ├── db/
│   │   ├── init_db.py             # 🗄️ Inicialização do banco local
│   │   ├── models.py              # Modelos SQLAlchemy
│   │   └── session.py             # Sessão e conexão com DB
│   │
│   ├── integrations/
│   │   └── sheets.py              # 📊 Google Sheets (source of truth)
│   │
│   ├── routes/
│   │   ├── booking.py             # 📅 Rotas de agendamento
│   │   ├── chat.py                # 💬 Fluxo de conversa
│   │   ├── services.py            # 💼 Serviços e preços
│   │   └── webhook.py             # 🔗 Webhook WhatsApp (Z-API)
│   │
│   └── app.py                     # 🚀 Aplicação FastAPI
│
├── data/
│   ├── price_list.json            # 💰 Serviços e preços (produção)
│   └── services_mapper.json       # Mapeamento interno de serviços
│
├── docs/
│   ├── fluxo_mvp.md               # 📈 Fluxo funcional do MVP
│   ├── fluxo_premium.md           # 🧠 Fluxo avançado (controle humano)
│   └── proposta.pdf               # 📄 Proposta conceitual
│
├── tests/
│   ├── test_engine.py             # 🧪 Testes do pipeline de IA
│   └── test_sheets.py             # 🧪 Testes da integração Sheets
│
├── .env.example                   # 📋 Exemplo de variáveis de ambiente
├── .gitignore
├── requirements.txt
├── LICENSE
└── README.md
```

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🧪 Logs, Erros e Confiabilidade

- Tratamento completo de exceções
- Logs claros para depuração
- Falhas não quebram o fluxo
- Fallbacks seguros quando entrada é inválida

👉 Foco em **estabilidade**, não só em resposta bonita

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 🎬 Demo

![Demo](assets/demo.gif)

A demo acima mostra o sistema em funcionamento com:

- Conversa real via WhatsApp  
- Detecção de intenção pelo LLM  
- Validação de serviços e agenda  
- Agendamento automático  
- Transferência para atendimento humano  
- Retorno automático da IA após interação manual  

👉 Demonstra um **pipeline de decisão controlado**, pronto para uso em ambiente real.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 💡 Por Que Este Projeto Chama Atenção de Recrutadores

Este repositório demonstra:

- Uso **realista e seguro de LLM**
- Arquitetura de IA aplicada a negócios
- Separação clara entre IA e regras
- Pipeline confiável e auditável
- Integração WhatsApp + IA em produção
- Mentalidade de **engenharia**, não só prompt

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">

## 👩‍💻 Autora

Desenvolvido por **Neusa M. — Engenheira de Automação com IA**  

📧 [contact.neusam21@gmail.com](mailto:contact.neusam21@gmail.com)  
💻 [github.com/NeusaM21](https://github.com/NeusaM21)  
🌐 [linkedin.com/in/NeusaM21](https://www.linkedin.com/in/NeusaM21)

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">


<a id="license"></a>

## 📜 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE)  
— uso livre para fins **comerciais** e **acadêmicos**.

<hr style="border: 0.5px solid #e5e5e5; margin: 20px 0;">


<p align="left">
  <a href="https://github.com/NeusaM21">
    <img src="https://img.shields.io/badge/⬅️-Voltar%20para%20o%20portfólio%20principal-blue?style=for-the-badge"/>
  </a>
</p>
