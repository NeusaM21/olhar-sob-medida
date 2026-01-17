import os
import json
import re
from datetime import datetime, timedelta, timezone
import unicodedata

from backend.integrations.sheets import (
    get_available_dates,
    get_available_times_for_date,
    book_appointment,
    cancel_appointment,
    set_robot_mute
)

# --------------------------------------------------
# MEMÓRIA DE CONVERSA (RAM)
# --------------------------------------------------
conversation_state = {}

# --------------------------------------------------
# CONFIGURAÇÕES
# --------------------------------------------------
def get_brazil_time():
    offset = timezone(timedelta(hours=-3))
    return datetime.now(offset)

def load_services():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    file_path = os.path.join(project_root, "data", "price_list.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["services"]

SERVICES = load_services()

# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------
def normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text

def format_services_list():
    """
    Formata a lista de serviços agrupada por categorias
    Retorna: string formatada com todos os serviços organizados
    """
    # Mapeamento de categorias para emojis
    category_emojis = {
        "Depilação": "✨",
        "Estética Facial": "💆‍♀️",
        "Cílios & Sobrancelhas": "👁️",
        "Design na Linha": "✂️",
        "Tratamentos Corporais": "💎",
        "Nail Designer": "💅",
        "Manicure & Pedicure": "🌸"
    }
    
    # Agrupa serviços por categoria
    categories = {}
    for service in SERVICES:
        category = service.get("category", "Outros")
        if category not in categories:
            categories[category] = []
        categories[category].append(service)
    
    # Formata a lista
    result = []
    service_number = 1
    
    # Define ordem das categorias (personalizada)
    category_order = [
        "Depilação",
        "Estética Facial", 
        "Cílios & Sobrancelhas",
        "Design na Linha",
        "Tratamentos Corporais",
        "Nail Designer",
        "Manicure & Pedicure"
    ]
    
    for category in category_order:
        if category not in categories:
            continue
            
        # Adiciona cabeçalho da categoria
        emoji = category_emojis.get(category, "✨")
        result.append(f"\n{emoji} *{category.upper()}*")
        
        # Adiciona serviços da categoria
        for service in categories[category]:
            price = service['price']
            # Formata preço (pode ser número ou string)
            price_str = f"R$ {price:.2f}" if isinstance(price, (int, float)) else price
            result.append(f"{service_number}. {service['name']} — {price_str}")
            service_number += 1
    
    return "\n".join(result)

def detect_service_by_number_or_name(text: str):
    """
    Detecta serviço por número (1, 2, 3...) ou por nome (sobrancelha, buço...)
    Retorna: service dict ou None
    """
    # Tenta detectar por número
    if text.isdigit():
        service_index = int(text) - 1
        if 0 <= service_index < len(SERVICES):
            return SERVICES[service_index]
    
    # Tenta detectar por nome
    for service in SERVICES:
        if normalize(service["name"]) in text:
            return service
    
    return None

def is_working_day(date_obj):
    """
    Verifica se a data cai em dia de funcionamento (Terça a Sábado)
    Retorna: (bool, str) - (é_dia_util, nome_do_dia)
    """
    weekday = date_obj.weekday()  # 0=Segunda, 1=Terça, ..., 6=Domingo
    
    days_pt = {
        0: "Segunda-feira",
        1: "Terça-feira",
        2: "Quarta-feira",
        3: "Quinta-feira",
        4: "Sexta-feira",
        5: "Sábado",
        6: "Domingo"
    }
    
    day_name = days_pt[weekday]
    
    # Terça(1) a Sábado(5)
    is_open = weekday >= 1 and weekday <= 5
    
    return is_open, day_name

def get_next_working_day(date_obj):
    """
    Retorna a próxima data útil (Terça a Sábado)
    """
    next_date = date_obj
    for _ in range(7):  # Máximo 7 dias para encontrar próximo dia útil
        next_date = next_date + timedelta(days=1)
        is_open, _ = is_working_day(next_date)
        if is_open:
            return next_date
    return None

def extract_date_and_time(text: str):
    text = normalize(text)
    date_part = None
    time_part = None
    
    # --- horário (Aceita 16h, 16:00, 16h30, 16:30, 16hs) ---
    # Regex atualizado para capturar minutos opcionais
    time_match = re.search(r'(\d{1,2})\s*(?:h|:|hs|horas)\s*(\d{2})?', text)
    if time_match:
        hour = int(time_match.group(1))
        minutes = int(time_match.group(2)) if time_match.group(2) else 0
        if 0 <= hour <= 23 and 0 <= minutes <= 59:
            time_part = f"{hour:02d}:{minutes:02d}"
            
    # --- data ---
    now_br = get_brazil_time()
    
    if "hoje" in text:
        date_part = now_br.date()
    elif "amanha" in text:
        date_part = (now_br + timedelta(days=1)).date()
    else:
        date_match = re.search(r'(\d{1,2})/(\d{1,2})', text)
        if date_match:
            day, month = map(int, date_match.groups())
            year = now_br.year
            try:
                date_part = datetime(year, month, day).date()
            except ValueError:
                pass

    return date_part, time_part

def standardize_sheet_dates(date_list):
    """
    Transforma qualquer formato de data que venha da planilha (YYYY-MM-DD ou DD/MM/YYYY)
    sempre para DD/MM/YYYY para garantir a comparação.
    """
    cleaned_list = []
    for d in date_list:
        # Se vier 2025-12-31
        if "-" in d:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                cleaned_list.append(dt.strftime("%d/%m/%Y"))
                continue
            except:
                pass
        # Se vier 31/12/2025
        cleaned_list.append(d)
    return cleaned_list

# --------------------------------------------------
# ENGINE PRINCIPAL
# --------------------------------------------------
def generate_ai_response(phone: str, message: str, sender_name: str = None) -> str:
    """
    🆕 VERSÃO ATUALIZADA: Motor de IA com Identificação Enriquecida
    
    Gera resposta automatizada para mensagens do WhatsApp, gerenciando
    todo o fluxo de agendamento e handoff para atendimento humano.
    
    Args:
        phone: Telefone do cliente no formato completo (ex: 5511999666070)
        message: Texto da mensagem enviada pelo cliente
        sender_name: Nome do remetente capturado do WhatsApp (opcional)
                    Quando disponível, usado como fonte primária de identificação
    
    Returns:
        str: Resposta a ser enviada ao cliente
        None: Se robô está mutado (atendimento humano ativo)
    
    Fontes de Identificação (por prioridade):
        1. sender_name (do WhatsApp via Z-API) - PRIORIDADE MÁXIMA
        2. state["name"] (fornecido durante agendamento atual)
        3. state["last_booking"]["name"] (histórico da sessão)
        4. "Cliente não identificado" (fallback)
    """
    # 🔇 VERIFICA SE ROBÔ ESTÁ SILENCIADO (MUTE_ROBO = TRUE)
    from backend.integrations.sheets import is_robot_muted
    
    if is_robot_muted(phone):
        # Robô silenciado - humano está atendendo
        # Não processa nem responde a mensagem
        print(f"🔇 [MUTE] Robô silenciado para {phone} - humano no controle")
        return None
    
    text = normalize(message)
    
    # Recupera estado ou cria novo (DEVE vir ANTES de qualquer uso de 'state')
    state = conversation_state.get(phone, {
        "status": "start", 
        "service": None,
        "date": None,
        "time": None,
        "name": None
    })
    
    # ========================================================================
    # 🆕 ALTERAÇÃO 1: DETECÇÃO PRIORITÁRIA DE TAG E INTENÇÃO DE HUMANO
    # ========================================================================
    # Verifica PRIMEIRO se há tag #SOLICITAR_HUMANO# ou palavras-chave
    # Isso evita que o fluxo de agendamento atropele a intenção do usuário
    # ========================================================================
    
    human_request_keywords = [
        "#solicitar_humano#",
        "responsavel", 
        "responsável", 
        "dono", 
        "dona", 
        "atendente", 
        "humano", 
        "pessoa", 
        "alguem", 
        "alguém", 
        "proprietario", 
        "proprietária", 
        "gerente"
    ]
    
    # Detecção prioritária de solicitação de atendimento humano
    if any(palavra in text for palavra in human_request_keywords):
        # ====================================================================
        # 🆕 ALTERAÇÃO 2: RECUPERAÇÃO INTELIGENTE DE IDENTIDADE
        # ====================================================================
        # Tenta recuperar o nome da cliente de múltiplas fontes:
        # 1. sender_name do WhatsApp (NOVA PRIORIDADE MÁXIMA)
        # 2. Estado atual (se ela já forneceu durante este agendamento)
        # 3. Último agendamento (histórico da sessão)
        # 4. Fallback para "Cliente não identificado"
        # ====================================================================
        
        client_name = (
            sender_name or                                      # 🆕 FONTE #1: WhatsApp (PRIORIDADE)
            state.get("name") or                                # FONTE #2: Estado atual
            state.get("last_booking", {}).get("name") or        # FONTE #3: Histórico
            "Cliente não identificado"                          # FONTE #4: Fallback
        )
        
        # ====================================================================
        # 🆕 ALTERAÇÃO 3: ENRIQUECIMENTO DOS DADOS DA PLANILHA
        # ====================================================================
        # Agora enviamos 4 parâmetros em vez de 2:
        # - phone: identificador único
        # - True: status do mute (ativa silêncio do robô)
        # - client_name: nome recuperado inteligentemente
        # - status: descrição clara da ação
        # ====================================================================
        
        set_robot_mute(
            phone=phone,
            mute_status=True,
            name=client_name,
            status="Solicitou falar com a dona"
        )
        
        # Limpa estado para evitar confusão quando robô voltar
        conversation_state.pop(phone, None)
        
        print(f"👤 [HANDOFF] Cliente '{client_name}' ({phone}) solicitou atendimento humano")
        print(f"📊 [FONTE] Nome obtido de: {'WhatsApp' if sender_name else 'Estado/Histórico' if client_name != 'Cliente não identificado' else 'Fallback'}")
        
        return (
            "Entendi 😊\n"
            "Vou te direcionar para atendimento humano agora.\n"
            "⏳ Por favor, aguarde um momento que você será atendida.\n"
            "Obrigada pela paciência 💖"
        )
    
    # ========================================================================
    # FIM DAS ALTERAÇÕES - Código original continua abaixo
    # ========================================================================
    
    # 👋 DETECTA SAUDAÇÃO INICIAL (reseta conversa e se apresenta)
    # Palavras-chave de saudação que indicam início de nova conversa
    saudacoes = ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "ola!", "hey", "ei", "opa"]
    
    # Se cliente enviou saudação e NÃO está em meio a um fluxo crítico
    if any(saudacao in text for saudacao in saudacoes):
        # Verifica se está em fluxo crítico (agendamento em andamento)
        estados_criticos = ["awaiting_name", "awaiting_confirmation", "awaiting_time"]
        
        if state.get("status") not in estados_criticos:
            # Reseta estado e inicia apresentação
            conversation_state[phone] = {
                "status": "awaiting_welcome_response",
                "service": None,
                "date": None,
                "time": None,
                "name": None
            }
            
            return (
                "✨ Olá! É um prazer receber você no Studio Olhar Sob Medida ✨\n\n"
                "Sou a assistente virtual do estúdio 😊\n"
                "Posso te ajudar com informações ou agendamentos.\n\n"
                "👉 Você gostaria de conhecer nossos serviços?"
            )
    
    # 🔧 CORREÇÃO BUG #2: Detectar despedida após agendamento confirmado
    # MAS não limpar estado até cliente REALMENTE sair
    if state.get("status") == "completed":
        # Detectar respostas negativas educadas (cliente não quer mais nada)
        if any(x in text for x in ["nao", "não", "obrigado", "obrigada", "valeu", "vlw", "ta bom", "tá bom", "beleza", "so isso", "só isso", "ok"]):
            name = state.get("last_booking", {}).get("name", "")
            date = state.get("last_booking", {}).get("date", "")
            time = state.get("last_booking", {}).get("time", "")
            
            # 🆕 NÃO limpa estado aqui - marca como "despedido"
            state["status"] = "farewell_sent"
            conversation_state[phone] = state
            
            if name and date and time:
                return (
                    f"Perfeito, *{name}*! 💖\n\n"
                    "Foi um prazer te atender!\n"
                    f"Nos vemos em *{date}* às *{time}* ✨\n\n"
                    "Até lá! 👋"
                )
            else:
                return (
                    "Perfeito! 💖\n\n"
                    "Foi um prazer te atender!\n"
                    "Até breve! 👋"
                )
        
        # 🔧 CORREÇÃO: Cliente quer algo mais (pergunta sobre endereço, Instagram, etc)
        # NÃO reseta para "start" - deixa o código continuar processando
        # Estado PERMANECE "completed" para manter contexto do agendamento
    
    # 🔧 CORREÇÃO BUG #2: Se cliente já recebeu despedida e volta a falar
    # Reconhecer que já tem agendamento e NÃO se reapresentar
    if state.get("status") == "farewell_sent":
        # Cliente voltou a falar - verificar se tem agendamento ativo
        if state.get("last_booking"):
            # Tem agendamento - não se reapresentar, apenas continuar atendendo
            state["status"] = "completed"
            conversation_state[phone] = state
            # Deixa o código continuar para processar a mensagem
        else:
            # Não tem agendamento - pode voltar ao início
            state["status"] = "start"
            conversation_state[phone] = state
    
    # 🆕 CORREÇÃO 2: Detectar pergunta sobre serviços (ANTES de tudo)
    # Isso evita que a IA reinicie do zero quando o cliente pergunta sobre serviços
    if any(palavra in text for palavra in ["servico", "serviços", "servicos", "lista", "quais servico", "que servico", "tem quais", "oferece"]):
        # 🔧 CORREÇÃO BUG #1: Bloquear detecção de palavra-chave em awaiting_welcome_response
        # Se não está em um fluxo crítico (apresentação, nome, confirmação), mostra lista
        if state.get("status") not in ["awaiting_welcome_response", "awaiting_name", "awaiting_confirmation"]:
            state["status"] = "awaiting_service_selection"
            conversation_state[phone] = state
            
            services_list = format_services_list()
            return (
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*"
            )
    
    # Se o usuário mandar "cancelar", reseta tudo
    if "cancelar" in text or "desmarcar" in text:
        # 🔧 CORREÇÃO: Pega o estado ATUAL antes de verificar
        current_state = conversation_state.get(phone, {})
        
        # 🆕 Caso 1: Cancelamento APÓS agendamento confirmado
        if current_state.get("last_booking"):
            last_booking = current_state["last_booking"]
            
            # Tenta cancelar na planilha
            cancelado = cancel_appointment(phone)
            
            conversation_state.pop(phone, None)
            
            if cancelado:
                return (
                    f"✅ Agendamento cancelado com sucesso, *{last_booking['name']}*!\n\n"
                    f"📋 Detalhes do cancelamento:\n"
                    f"✨ Serviço: {last_booking['service']}\n"
                    f"📅 Data: {last_booking['date']}\n"
                    f"⏰ Horário: {last_booking['time']}\n\n"
                    "💡 *Gostaria de:*\n"
                    "📅 Reagendar para outro dia ou horário?\n"
                    "✨ Agendar outro serviço?\n"
                    "📍 Ver nossos serviços disponíveis?\n\n"
                    "É só me dizer! Estou aqui para ajudar 💖"
                )
            else:
                return (
                    f"Entendi, *{last_booking['name']}*! 😊\n\n"
                    "⚠️ *IMPORTANTE:* Entre em contato conosco para confirmar o cancelamento!\n\n"
                    "📞 WhatsApp: (11) 9 1234-5678\n\n"
                    "Se quiser reagendar depois, é só me chamar! 💖"
                )
        
        # 🆕 Caso 2: Cancelamento DURANTE o processo de agendamento (antes de confirmar)
        if current_state.get("service"):
            service_name = current_state.get("service", {}).get("name", "")
            date_str = current_state.get("date", "")
            time_str = current_state.get("time", "")
            
            conversation_state.pop(phone, None)
            
            msg = "Tudo bem! Agendamento cancelado. 😊\n\n"
            if service_name or date_str or time_str:
                msg += "📋 Você estava agendando:\n"
                if service_name:
                    msg += f"✨ Serviço: {service_name}\n"
                if date_str:
                    msg += f"📅 Data: {date_str.strftime('%d/%m') if hasattr(date_str, 'strftime') else date_str}\n"
                if time_str:
                    msg += f"⏰ Horário: {time_str}\n"
                msg += "\n"
            
            msg += "💡 *Gostaria de:*\n"
            msg += "📅 Reagendar para outro dia ou horário?\n"
            msg += "✨ Conhecer outros serviços?\n"
            msg += "📍 Saber mais sobre o studio?\n\n"
            msg += "É só me dizer! Estou aqui para ajudar 💖"
            return msg
        
        # Caso 3: Cancelamento sem nada em andamento
        conversation_state.pop(phone, None)
        return "Tudo bem! Se precisar de algo, é só chamar. 👋"
    
    # Despedida simples
    if "tchau" in text or "ate logo" in text or "até logo" in text:
        name = ""
        current_state = conversation_state.get(phone, {})
        if current_state.get("last_booking"):
            name = current_state["last_booking"]["name"]
        
        if name:
            return f"Até logo, *{name}*! 💖 Foi um prazer te atender! 👋"
        return "Até logo! 💖 Foi um prazer te atender! 👋"
    
    # 🆕 CORREÇÃO 4: RESPOSTAS CONTEXTUAIS baseadas em agendamento ativo
    # Verifica se há agendamento confirmado para personalizar respostas
    
    # ENDEREÇO
    if any(palavra in text for palavra in ["endereco", "endereço", "local", "onde", "localizacao", "localização"]):
        # 🔧 Verifica se há agendamento confirmado
        if state.get("last_booking"):
            booking = state["last_booking"]
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                f"✨ Nos vemos em *{booking['date']}* às *{booking['time']}*! 💖"
            )
        # 🔧 CORREÇÃO BUG #1: Se está em awaiting_welcome_response, não muda o estado
        elif state.get("status") == "awaiting_welcome_response":
            # Não muda estado - cliente pode ainda responder sim/não
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                "Se quiser, posso te mostrar nossos serviços 😊"
            )
        else:
            # Outros estados - pode oferecer agendamento
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "address"
            conversation_state[phone] = state
            
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                "Se quiser, posso te mostrar nossos serviços 😊"
            )
    
    # TELEFONE
    if any(palavra in text for palavra in ["telefone", "contato", "whatsapp", "ligar"]):
        # 🔧 Verifica se há agendamento confirmado
        if state.get("last_booking"):
            booking = state["last_booking"]
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                f"Qualquer dúvida, estou aqui! 😊\n"
                f"Nos vemos em *{booking['date']}* às *{booking['time']}* ✨"
            )
        # 🔧 CORREÇÃO BUG #1: Se está em awaiting_welcome_response, não muda o estado
        elif state.get("status") == "awaiting_welcome_response":
            # Não muda estado - cliente pode ainda responder sim/não
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                "Qualquer dúvida, estou aqui! 😊"
            )
        else:
            # Outros estados - pode oferecer agendamento
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "phone"
            conversation_state[phone] = state
            
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                "👉 Posso te ajudar com algum agendamento? 😊"
            )
    
    # INSTAGRAM
    if any(palavra in text for palavra in ["instagram", "insta", "rede social", "redes sociais", "facebook", "social", "fotos", "portfolio"]):
        # 🔧 Verifica se há agendamento confirmado
        if state.get("last_booking"):
            booking = state["last_booking"]
            return (
                "📱 *Siga a gente no Instagram!*\n\n"
                "🌟 @olharsobmedida\n"
                "https://www.instagram.com/olharsobmedida\n\n"
                "Lá você encontra:\n"
                "✨ Nossos trabalhos\n"
                "📸 Fotos antes e depois\n"
                "🎁 Promoções exclusivas\n"
                "💄 Dicas de beleza\n\n"
                f"Confira nossos trabalhos! Te esperamos em *{booking['date']}* às *{booking['time']}* 💖"
            )
        # 🔧 CORREÇÃO BUG #1: Se está em awaiting_welcome_response, não muda o estado
        elif state.get("status") == "awaiting_welcome_response":
            # Não muda estado - cliente pode ainda responder sim/não
            return (
                "📱 *Siga a gente no Instagram!*\n\n"
                "🌟 @olharsobmedida\n"
                "https://www.instagram.com/olharsobmedida\n\n"
                "Lá você encontra:\n"
                "✨ Nossos trabalhos\n"
                "📸 Fotos antes e depois\n"
                "🎁 Promoções exclusivas\n"
                "💄 Dicas de beleza\n\n"
                "Vem conferir! 😊💖"
            )
        else:
            # Outros estados - pode oferecer agendamento
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "instagram"
            conversation_state[phone] = state
            
            return (
                "📱 *Siga a gente no Instagram!*\n\n"
                "🌟 @olharsobmedida\n"
                "https://www.instagram.com/olharsobmedida\n\n"
                "Lá você encontra:\n"
                "✨ Nossos trabalhos\n"
                "📸 Fotos antes e depois\n"
                "🎁 Promoções exclusivas\n"
                "💄 Dicas de beleza\n\n"
                "👉 Viu algum serviço que te interessou? Posso agendar para você! 💖"
            )

    # 🆕 NOVO FLUXO: RESPOSTA AO ENGAJAMENTO (SIM/NÃO)
    if state.get("status") == "awaiting_engagement_response":
        # Cliente respondeu SIM
        if any(x in text for x in ["sim", "claro", "quero", "pode", "gostaria", "ok"]):
            state["status"] = "awaiting_service_selection"
            conversation_state[phone] = state
            
            services_list = format_services_list()
            return (
                "Perfeito! ✨ Vou te ajudar com o agendamento 💖\n\n"
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*"
            )
        
        # Cliente respondeu NÃO
        elif any(x in text for x in ["nao", "não", "agora nao", "agora não", "depois"]):
            conversation_state.pop(phone, None)
            return (
                "Tudo bem 😊 Quando quiser conhecer ou agendar um serviço, é só me chamar. Estarei por aqui ✨"
            )
        
        # Cliente mandou outra coisa - tenta entender como serviço
        else:
            detected_service = detect_service_by_number_or_name(text)
            
            if detected_service:
                state["service"] = detected_service
                state["status"] = "awaiting_date"
                conversation_state[phone] = state
                
                # 🆕 Mensagem contextual sobre dias de funcionamento
                now_br = get_brazil_time()
                is_open_today, today_name = is_working_day(now_br.date())
                
                if is_open_today:
                    date_msg = (
                        f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                        "👉 Para qual data você gostaria de agendar?\n\n"
                        "Pode responder: *hoje*, *amanhã* ou uma data da sua preferência.\n\n"
                        "💡 Lembrando que o studio funciona de *Terça a Sábado* das *9h às 19h*"
                    )
                else:
                    next_day = get_next_working_day(now_br.date())
                    next_day_str = next_day.strftime('%d/%m') if next_day else "próximo dia útil"
                    date_msg = (
                        f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                        f"⚠️ Hoje é *{today_name}* e o studio está fechado.\n\n"
                        "👉 Para qual data você gostaria de agendar?\n\n"
                        f"Pode responder: *amanhã ({next_day_str})* ou uma data da sua preferência.\n\n"
                        "💡 Funcionamos de *Terça a Sábado* das *9h às 19h*"
                    )
                
                return date_msg
            else:
                return "Desculpe, não entendi 😕 Você gostaria de agendar um serviço? (responda *sim* ou *não*)"

    # =========================================================================
    # DETECÇÃO RÁPIDA DE INTENÇÃO (Atalho)
    # Se o usuário já falar o nome de um serviço, pulamos a apresentação
    # 🔧 CORREÇÃO BUG #1: MAS não se estiver em awaiting_welcome_response
    # =========================================================================
    detected_service = None
    
    # 🔧 Só detecta serviço se NÃO estiver esperando resposta da apresentação
    if state.get("status") not in ["awaiting_welcome_response", "awaiting_name", "awaiting_confirmation"]:
        detected_service = detect_service_by_number_or_name(text)
            
    if detected_service:
        state["service"] = detected_service
        state["status"] = "awaiting_date"
        conversation_state[phone] = state
        
        # 🆕 Mensagem contextual sobre dias de funcionamento
        now_br = get_brazil_time()
        is_open_today, today_name = is_working_day(now_br.date())
        
        if is_open_today:
            date_msg = (
                f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                "👉 Para qual data você gostaria de agendar?\n\n"
                "Pode responder: *hoje*, *amanhã* ou uma data da sua preferência.\n\n"
                "💡 Lembrando que o studio funciona de *Terça a Sábado* das *9h às 19h*"
            )
        else:
            next_day = get_next_working_day(now_br.date())
            next_day_str = next_day.strftime('%d/%m') if next_day else "próximo dia útil"
            date_msg = (
                f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                f"⚠️ Hoje é *{today_name}* e o studio está fechado.\n\n"
                "👉 Para qual data você gostaria de agendar?\n\n"
                f"Pode responder: *amanhã ({next_day_str})* ou uma data da sua preferência.\n\n"
                "💡 Funcionamos de *Terça a Sábado* das *9h às 19h*"
            )
        
        return date_msg

    # =========================================================================
    # FLUXO 1: BOAS VINDAS
    # =========================================================================
    if state["status"] == "start":
        state["status"] = "awaiting_welcome_response"
        conversation_state[phone] = state
        
        return (
            "✨ Olá! É um prazer receber você no Studio Olhar Sob Medida ✨\n\n"
            "Sou a assistente virtual do estúdio 😊\n"
            "Posso te ajudar com informações ou agendamentos.\n\n"
            "👉 Você gostaria de conhecer nossos serviços?"
        )

    # =========================================================================
    # FLUXO 2: RESPOSTA DA APRESENTAÇÃO
    # =========================================================================
    if state["status"] == "awaiting_welcome_response":
        # 🔧 CORREÇÃO BUG #1: Validação ESTRITA de sim/não
        if any(x in text for x in ["sim", "claro", "quero", "pode", "gostaria", "lista", "sim por favor", "com certeza", "aceito"]):
            state["status"] = "awaiting_service_selection"
            conversation_state[phone] = state
            
            services_list = format_services_list()
            return (
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*"
            )
        elif any(x in text for x in ["nao", "não", "agora nao", "agora não", "depois", "talvez depois"]):
            # Cliente claramente disse NÃO
            conversation_state.pop(phone, None)
            return "Entendi! Se quiser agendar algo depois, é só me chamar! 😊"
        else:
            # 🔧 CORREÇÃO BUG #1: Cliente mandou algo que não é sim/não
            # Não avança estado - pede resposta clara
            return (
                "Desculpe, não entendi 😊\n\n"
                "Você gostaria de conhecer nossos serviços?\n"
                "👉 Responda *sim* ou *não*, por favor!"
            )

    # =========================================================================
    # FLUXO 3: ESCOLHA DO SERVIÇO (Caso venha do menu)
    # =========================================================================
    if state["status"] == "awaiting_service_selection":
        # Tenta detectar serviço por número ou nome
        detected_service = detect_service_by_number_or_name(text)
        
        if detected_service:
            state["service"] = detected_service
            state["status"] = "awaiting_date"
            conversation_state[phone] = state
            
            # 🆕 Mensagem contextual sobre dias de funcionamento
            now_br = get_brazil_time()
            is_open_today, today_name = is_working_day(now_br.date())
            
            if is_open_today:
                date_msg = (
                    f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                    "👉 Para qual data você gostaria de agendar?\n\n"
                    "Pode responder: *hoje*, *amanhã* ou uma data da sua preferência.\n\n"
                    "💡 Lembrando que o studio funciona de *Terça a Sábado* das *9h às 19h*"
                )
            else:
                next_day = get_next_working_day(now_br.date())
                next_day_str = next_day.strftime('%d/%m') if next_day else "próximo dia útil"
                date_msg = (
                    f"Perfeito! ✨ *{detected_service['name']}* é uma ótima escolha 💖\n\n"
                    f"⚠️ Hoje é *{today_name}* e o studio está fechado.\n\n"
                    "👉 Para qual data você gostaria de agendar?\n\n"
                    f"Pode responder: *amanhã ({next_day_str})* ou uma data da sua preferência.\n\n"
                    "💡 Funcionamos de *Terça a Sábado* das *9h às 19h*"
                )
            
            return date_msg
        else:
            return "Não entendi qual serviço você quer 😕 Tente digitar o *número* ou o *nome*, como *1* ou *Sobrancelha*."

    # =========================================================================
    # FLUXO 4: DATA
    # =========================================================================
    if state["status"] == "awaiting_date":
        date, time = extract_date_and_time(text)
        
        if not date:
            return "Não consegui entender a data 😕 Pode me dizer novamente? (Ex: hoje, amanhã, 02/01)"
        
        # 🆕 VALIDA SE É DIA DE FUNCIONAMENTO
        is_open, day_name = is_working_day(date)
        
        if not is_open:
            next_day = get_next_working_day(date)
            next_day_str = next_day.strftime('%d/%m') if next_day else "próximo dia útil"
            return (
                f"⚠️ {day_name} ({date.strftime('%d/%m')}) o studio está fechado.\n\n"
                "🕒 Funcionamos de *Terça a Sábado* das *9h às 19h*\n\n"
                f"👉 Que tal agendar para *{next_day_str}* ou outra data da sua preferência?"
            )

        raw_available_dates = get_available_dates() 
        clean_available_dates = standardize_sheet_dates(raw_available_dates)
        
        user_date_str = date.strftime("%d/%m/%Y")
        
        print(f"DEBUG: Data Usuário: {user_date_str} | Datas Planilha Limpas: {clean_available_dates}")

        if user_date_str not in clean_available_dates:
            return (
                f"Essa data ({date.strftime('%d/%m')}) não está disponível ou não temos agenda aberta 😕\n"
                "👉 Pode escolher outra data, por favor?"
            )
            
        state["date"] = date
        conversation_state[phone] = state
        
        # Se o usuário já mandou horário (ex: "hoje as 16hs")
        if time:
            try:
                available_times = get_available_times_for_date(date.strftime("%d/%m/%Y"))
            except Exception as e:
                print(f"❌ [ERROR] Falha ao buscar horários: {e}")
                return (
                    f"Desculpe, tive um problema ao verificar os horários disponíveis para {date.strftime('%d/%m')} 😕\n\n"
                    "Por favor, tente novamente ou escolha apenas a data primeiro."
                )
            
            if time not in available_times:
                 return (
                    f"Consegui a data {date.strftime('%d/%m')}, mas o horário *{time}* já está ocupado 😕\n"
                    f"Horários livres: {', '.join(available_times)}"
                )

            state["time"] = time
            state["status"] = "awaiting_name"
            conversation_state[phone] = state
            
            return (
                f"Perfeito! ✨\n"
                f"📅 Data: *{date.strftime('%d/%m')}*\n"
                f"⏰ Horário: *{time}*\n\n"
                "👉 Para finalizar, qual é o seu *nome completo*?\n"
                "(Nome e sobrenome, por favor)"
            )
            
        state["status"] = "awaiting_time"
        conversation_state[phone] = state
        
        return (
            f"Perfeito! ✨ Data escolhida: *{date.strftime('%d/%m')}*\n\n"
            "👉 Qual horário você prefere?"
        )

    # =========================================================================
    # FLUXO 5: HORÁRIO
    # =========================================================================
    if state["status"] == "awaiting_time":
        _, time = extract_date_and_time(text)
        
        if not time:
            return "Não consegui entender o horário 😕 Pode me dizer novamente? (Ex: 16h)"
        
        try:
            available_times = get_available_times_for_date(state["date"].strftime("%d/%m/%Y"))
        except Exception as e:
            print(f"❌ [ERROR] Falha ao buscar horários: {e}")
            return (
                f"Desculpe, tive um problema ao verificar os horários disponíveis 😕\n\n"
                "Por favor, tente novamente."
            )
        
        if time not in available_times:
             return (
                f"Esse horário não está disponível 😕\n"
                f"Horários disponíveis: {', '.join(available_times)}"
            )

        state["time"] = time
        state["status"] = "awaiting_name"
        conversation_state[phone] = state
        
        return (
            f"Perfeito! ✨\n"
            f"📅 Data: *{state['date'].strftime('%d/%m')}*\n"
            f"⏰ Horário: *{time}*\n\n"
            "👉 Para finalizar, qual é o seu *nome completo*?\n"
            "(Nome e sobrenome, por favor)"
        )

    # =========================================================================
    # FLUXO 6: NOME DO CLIENTE
    # =========================================================================
    if state["status"] == "awaiting_name":
        # Captura o nome (remove palavras como "meu nome é", "sou", etc)
        name = message.strip()
        for phrase in ["meu nome e", "meu nome é", "me chamo", "sou", "eu sou"]:
            name = name.replace(phrase, "").strip()
        
        # Valida se tem pelo menos nome e sobrenome
        name_parts = name.split()
        if len(name_parts) < 2:
            return (
                "Por favor, me informe seu *nome completo* (nome e sobrenome) 😊\n"
                "Exemplo: Maria Silva"
            )
        
        state["name"] = name.title()
        state["status"] = "awaiting_confirmation"
        conversation_state[phone] = state
        
        return (
            f"Prazer, *{state['name']}*! 😊\n\n"
            f"📝 Resumo do agendamento:\n"
            f"👤 Nome: *{state['name']}*\n"
            f"✨ Serviço: *{state['service']['name']}*\n"
            f"📅 Data: *{state['date'].strftime('%d/%m')}*\n"
            f"⏰ Horário: *{state['time']}*\n\n"
            "👉 Posso confirmar o agendamento?"
        )

    # =========================================================================
    # FLUXO 7: CONFIRMAÇÃO
    # =========================================================================
    if state["status"] == "awaiting_confirmation":
        if any(x in text for x in ["sim", "confirmar", "ok", "pode"]):
            book_appointment(
                phone=phone,
                name=state["name"],
                service=state["service"]["name"],
                date=state["date"].strftime("%d/%m/%Y"),
                time=state["time"]
            )
            
            # 🆕 Salva informações do último agendamento para possível cancelamento
            conversation_state[phone] = {
                "status": "completed",
                "last_booking": {
                    "name": state["name"],
                    "service": state["service"]["name"],
                    "date": state["date"].strftime("%d/%m"),
                    "time": state["time"]
                }
            }
            
            # 🆕 CORREÇÃO 1: Removida menção a cancelamento - foco no positivo
            return (
                f"Agendamento confirmado com sucesso, *{state['name']}*! 🎉✨\n\n"
                "Estamos te esperando no *Studio Olhar Sob Medida* 💖\n\n"
                f"📍 Rua Horácio de Castilho, 21 - Vila Maria Alta\n"
                f"📅 {state['date'].strftime('%d/%m')} às {state['time']}\n\n"
                "Vai ficar lindo! Será um prazer te receber ✨\n\n"
                "👉 Posso te ajudar com mais alguma coisa? 😊"
            )
            
        if any(x in text for x in ["nao", "não", "cancelar"]):
            conversation_state.pop(phone, None)
            return (
                "Tudo bem! 😊\n\n"
                "Quando quiser agendar, é só me chamar!\n"
                "Estamos ansiosos pelo seu retorno! ✨"
            )
            
        return "👉 Posso confirmar o agendamento? (responda *sim* ou *não*)"

    # 🔧 FALLBACK: Mensagem não reconhecida
    # Se cliente tem agendamento confirmado, mantém contexto
    if state.get("last_booking"):
        return (
            "Desculpe, não entendi sua mensagem 😊\n\n"
            "💡 Posso te ajudar com:\n"
            "📍 Informações sobre o studio\n"
            "📞 Nossos contatos\n"
            "📱 Redes sociais\n"
            "🔄 Cancelar ou reagendar\n\n"
            "Como posso te ajudar?"
        )
    
    # Se não tem agendamento, pode resetar
    conversation_state.pop(phone, None)
    return "Desculpa, não entendi 😊 Em que posso te ajudar?"