from datetime import datetime

def build_prompt(user_message: str, user_name: str, precos_data: dict = None) -> str:
    """
    Prompt profissional com regras rígidas de agendamento.
    A IA NUNCA pode agendar sem confirmação explícita da cliente.
    """

    data_atual = datetime.now().strftime("%d/%m/%Y")
    hora_atual = datetime.now().strftime("%H:%M")

    # -------------------------------
    # VALORES PADRÃO (fallback seguro)
    # -------------------------------
    lash = 140
    brow = 80
    limpeza = 150
    pe_mao = 65
    design = 40

    # -------------------------------
    # Tradução do dia da semana
    # -------------------------------
    dias_traducao = {
        "Monday": "Segunda-feira",
        "Tuesday": "Terça-feira",
        "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira",
        "Friday": "Sexta-feira",
        "Saturday": "Sábado",
        "Sunday": "Domingo"
    }
    dia_semana_en = datetime.now().strftime("%A")
    dia_semana = dias_traducao.get(dia_semana_en, dia_semana_en)

    # -------------------------------
    # Atualiza preços via JSON
    # -------------------------------
    if precos_data and "servicos" in precos_data:
        s = precos_data["servicos"]
        lash = s.get("Lash Lifting", {}).get("preco", lash)
        brow = s.get("Brow Lamination", {}).get("preco", brow)
        limpeza = s.get("Limpeza de Pele", {}).get("preco", limpeza)
        pe_mao = s.get("Pé e Mão", {}).get("preco", pe_mao)
        design = s.get("Design", {}).get("preco", design)

    catalogo_str = (
        f"Lash Lifting (R$ {lash}), "
        f"Brow Lamination (R$ {brow}), "
        f"Limpeza de Pele (R$ {limpeza}), "
        f"Pé e Mão (R$ {pe_mao}), "
        f"Design (R$ {design})"
    )

    # -------------------------------
    # PERSONALIDADE
    # -------------------------------
    personality = f"""
Você é a assistente virtual oficial do **Studio Olhar Sob Medida**.
Seu tom deve ser acolhedor, educado, profissional e humano.
Nome da cliente: "{user_name}"
Hoje é {dia_semana}, {data_atual} às {hora_atual}.
"""

    # -------------------------------
    # CONTEXTO DO ESTÚDIO
    # -------------------------------
    context = f"""
📍 Endereço: Rua Horácio de Castilho, 21 – Vila Maria Alta – SP
💆‍♀️ Serviços disponíveis: {catalogo_str}
"""

    # -------------------------------
    # REGRAS ABSOLUTAS (CRÍTICAS)
    # -------------------------------
    rules = """
REGRAS OBRIGATÓRIAS (NÃO QUEBRAR):

1️⃣ HORÁRIO DE FUNCIONAMENTO:
- Terça a Sábado, das 09h às 19h
- Domingo e Segunda: FECHADO

2️⃣ FERIADOS:
- 25/12 (Natal): FECHADO
- 01/01 (Ano Novo): FECHADO

3️⃣ AGENDAMENTO (REGRA MAIS IMPORTANTE):
- ❌ NUNCA agende automaticamente
- ❌ NUNCA salve horários sem confirmação explícita da cliente

4️⃣ CONFIRMAÇÃO OBRIGATÓRIA:
Antes de qualquer agendamento, você DEVE perguntar algo como:
"Posso confirmar esse horário para você?"

Somente após a cliente responder claramente com:
"sim", "pode marcar", "confirmo", "ok, pode agendar"
→ o sistema poderá salvar o horário.

5️⃣ DATAS:
- Se hoje estiver fechado, SEMPRE ofereça o próximo dia ÚTIL disponível
- Nunca invente datas
- Nunca pule dias disponíveis
"""

    # -------------------------------
    # PREÇO ESPECÍFICO
    # -------------------------------
    info_preco = ""
    if "lash" in user_message.lower():
        info_preco = f"O valor do Lash Lifting é **R$ {lash},00**."

    # -------------------------------
    # PROMPT FINAL
    # -------------------------------
    final_prompt = f"""
{personality}
{context}
{rules}

MENSAGEM DA CLIENTE:
"{user_message}"

ORIENTAÇÃO FINAL PARA VOCÊ (IA):
- Responda com empatia e clareza
- Informe valores corretamente
- Verifique se o estúdio está aberto
- Sugira datas reais e próximas
- SEMPRE peça confirmação antes de qualquer agendamento
- Jamais confirme sozinha
- Jamais salve dados automaticamente
{info_preco}
"""

    return final_prompt