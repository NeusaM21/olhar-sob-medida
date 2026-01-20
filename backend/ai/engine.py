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

def is_greeting(text: str) -> bool:
    """
    🆕 Verifica se texto é uma saudação
    Retorna: True se for saudação, False caso contrário
    """
    greetings = [
        "oi", "ola", "olá", "oi!", "ola!",
        "bom dia", "boa tarde", "boa noite",
        "hey", "ei", "opa", "e ai", "e aí",
        "alo", "alô", "hello", "hi"
    ]
    
    normalized = normalize(text)
    
    # Verifica se texto é EXATAMENTE uma saudação (não parte de frase maior)
    return normalized in greetings

def is_session_expired(session_data: dict, timeout_minutes: int = 30) -> bool:
    """
    🆕 Verifica se sessão expirou por inatividade
    
    Args:
        session_data: Dados da sessão
        timeout_minutes: Minutos de inatividade para considerar expirada
    
    Returns:
        True se sessão expirou, False caso contrário
    """
    if not session_data:
        return True
    
    # Se não tem timestamp, considerar não expirada (sessão nova)
    if 'last_activity' not in session_data:
        return False
    
    try:
        last_activity = datetime.fromisoformat(session_data['last_activity'])
        now = get_brazil_time()
        
        # Remove timezone info para comparação
        if last_activity.tzinfo:
            last_activity = last_activity.replace(tzinfo=None)
        if now.tzinfo:
            now = now.replace(tzinfo=None)
        
        elapsed = now - last_activity
        is_expired = elapsed > timedelta(minutes=timeout_minutes)
        
        if is_expired:
            print(f"⏰ [SESSION] Sessão expirada - Última atividade: {last_activity}, Agora: {now}, Diferença: {elapsed}")
        
        return is_expired
        
    except Exception as e:
        print(f"⚠️ [SESSION] Erro ao verificar expiração: {e}")
        return False

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
    """
    🆕 VERSÃO MELHORADA - Parsing flexível de data e horário
    
    Aceita formatos naturais combinados como:
    - "dia 20 as 15h"
    - "20/01 15h"
    - "amanhã às 15"
    - "dia 20" (só data)
    - "15h" (só horário)
    
    Retorna: (date_part, time_part)
    """
    text = normalize(text)
    date_part = None
    time_part = None
    
    print(f"🔍 [PARSING] Analisando texto: '{text}'")
    
    # --------------------------------------------------
    # 🆕 EXTRAÇÃO DE HORÁRIO - Mais flexível
    # --------------------------------------------------
    # Padrões aceitos:
    # - "15h", "15hs", "15h30", "15:00", "15:30"
    # - "às 15h", "as 15", "15 horas"
    # - "3 da tarde", "15 da tarde"
    
    # Regex principal para capturar horas e minutos
    time_patterns = [
        r'(?:as|às)?\s*(\d{1,2})\s*(?:h|:|hs|horas)\s*(\d{2})?',  # 15h, 15:30, às 15h
        r'(\d{1,2})\s+(?:da\s+)?(?:manha|manhã|tarde|noite)',      # 15 da tarde
    ]
    
    for pattern in time_patterns:
        time_match = re.search(pattern, text)
        if time_match:
            hour = int(time_match.group(1))
            minutes = int(time_match.group(2)) if len(time_match.groups()) > 1 and time_match.group(2) else 0
            
            # Validação de horário
            if 0 <= hour <= 23 and 0 <= minutes <= 59:
                time_part = f"{hour:02d}:{minutes:02d}"
                print(f"✅ [PARSING] Horário extraído: {time_part}")
                break
    
    # --------------------------------------------------
    # 🆕 EXTRAÇÃO DE DATA - Mais flexível
    # --------------------------------------------------
    now_br = get_brazil_time()
    
    # Padrão 1: "hoje"
    if "hoje" in text:
        date_part = now_br.date()
        print(f"✅ [PARSING] Data extraída (hoje): {date_part}")
    
    # Padrão 2: "amanhã" ou "amanha"
    elif "amanha" in text or "amanhã" in text:
        date_part = (now_br + timedelta(days=1)).date()
        print(f"✅ [PARSING] Data extraída (amanhã): {date_part}")
    
    # Padrão 3: "dia DD" ou "dia DD/MM"
    else:
        # Tenta extrair "dia 20" ou "dia 20/01"
        dia_pattern = r'dia\s+(\d{1,2})(?:/(\d{1,2}))?'
        dia_match = re.search(dia_pattern, text)
        
        if dia_match:
            day = int(dia_match.group(1))
            month = int(dia_match.group(2)) if dia_match.group(2) else now_br.month
            year = now_br.year
            
            try:
                date_part = datetime(year, month, day).date()
                print(f"✅ [PARSING] Data extraída (dia X): {date_part}")
            except ValueError:
                print(f"❌ [PARSING] Data inválida: dia={day}, month={month}")
        
        # Padrão 4: "DD/MM" sem "dia" antes
        else:
            date_match = re.search(r'(\d{1,2})/(\d{1,2})', text)
            if date_match:
                day, month = map(int, date_match.groups())
                year = now_br.year
                try:
                    date_part = datetime(year, month, day).date()
                    print(f"✅ [PARSING] Data extraída (DD/MM): {date_part}")
                except ValueError:
                    print(f"❌ [PARSING] Data inválida: {day}/{month}")

    print(f"📊 [PARSING] Resultado final - Data: {date_part}, Horário: {time_part}")
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
# 🆕 FUNÇÕES DE MANIPULAÇÃO DE ESTADO DA SESSÃO
# --------------------------------------------------

def get_state_from_session(current_step: str, session_data: dict) -> dict:
    """
    Converte dados da sessão do banco em formato de estado interno.
    
    Args:
        current_step: Etapa atual da conversa
        session_data: Dados da conversa em formato dict
    
    Returns:
        dict: Estado no formato usado internamente pelo engine
    """
    # Converte date string de volta para objeto date se existir
    date_obj = None
    if session_data.get("date"):
        try:
            date_obj = datetime.strptime(session_data["date"], "%Y-%m-%d").date()
        except:
            pass
    
    return {
        "status": current_step or "start",
        "service": session_data.get("service"),
        "date": date_obj,
        "time": session_data.get("time"),
        "name": session_data.get("name"),
        "last_booking": session_data.get("last_booking"),
        "engagement_context": session_data.get("engagement_context")
    }

def prepare_session_update(state: dict) -> dict:
    """
    Prepara os dados do estado para serem salvos na sessão do banco.
    
    Args:
        state: Estado interno do engine
    
    Returns:
        dict: Dados formatados para salvar no banco
    """
    # Converte date object para string se existir
    date_str = None
    if state.get("date"):
        try:
            date_str = state["date"].strftime("%Y-%m-%d")
        except:
            pass
    
    session_data = {
        "service": state.get("service"),
        "date": date_str,
        "time": state.get("time"),
        "name": state.get("name"),
        "last_booking": state.get("last_booking"),
        "engagement_context": state.get("engagement_context"),
        "last_activity": get_brazil_time().isoformat()  # 🆕 Timestamp de última atividade
    }
    
    # Remove campos None para não poluir o JSON
    session_data = {k: v for k, v in session_data.items() if v is not None}
    
    return {
        "current_step": state.get("status", "start"),
        "conversation_data": session_data,
        "status": "completed" if state.get("status") == "completed" else "active"
    }

# --------------------------------------------------
# ENGINE PRINCIPAL
# --------------------------------------------------
def generate_ai_response(
    phone: str,
    message: str,
    sender_name: str = None,
    current_step: str = None,
    session_data: dict = None
) -> tuple[str, dict]:
    """
    🆕 VERSÃO CORRIGIDA - TIMEOUT + SAUDAÇÃO FUNCIONANDO
    
    Gera resposta automatizada para mensagens do WhatsApp, gerenciando
    todo o fluxo de agendamento com PERSISTÊNCIA em banco de dados.
    
    Args:
        phone: Telefone do cliente no formato completo (ex: 5511999666070)
        message: Texto da mensagem enviada pelo cliente
        sender_name: Nome do remetente capturado do WhatsApp (opcional)
        current_step: Etapa atual da conversa vinda do banco
        session_data: Dados da conversa vindos do banco
    
    Returns:
        tuple: (mensagem_resposta, dados_para_atualizar_sessao)
    """
    
    text = normalize(message)
    
    # 🆕 Inicializa session_data se vier None
    if session_data is None:
        session_data = {}
    
    print(f"🔍 [ENGINE] Entrada - phone={phone}, step={current_step}, message='{message[:50]}'")
    print(f"📊 [SESSION] session_data recebido: {session_data}")
    
    # ========================================================================
    # 🔥 VERIFICAÇÃO CRÍTICA 1: SESSÃO EXPIRADA (PRIORIDADE MÁXIMA)
    # ========================================================================
    if is_session_expired(session_data, timeout_minutes=30):
        print(f"⏰ [SESSION] Sessão expirada detectada! Limpando dados antigos...")
        session_data = {}
        current_step = None
    
    # ========================================================================
    # 🔥 VERIFICAÇÃO CRÍTICA 2: SAUDAÇÃO INICIAL (ANTES DE CONVERTER STATE)
    # ========================================================================
    initial_greetings = ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite"]
    
    # Se detectou saudação E (não tem sessão OU sessão está vazia OU step é None)
    if any(greeting == text for greeting in initial_greetings):
        if not session_data or not current_step or current_step == "start":
            print(f"👋 [SAUDAÇÃO] Nova conversa detectada! Apresentando o bot...")
            
            state = {
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
                "👉 Você gostaria de conhecer nossos serviços?",
                prepare_session_update(state)
            )
    
    # ========================================================================
    # 🔥 AGORA SIM: Converte dados da sessão para formato interno
    # ========================================================================
    state = get_state_from_session(current_step, session_data)
    
    print(f"✅ [ENGINE] Estado convertido - status={state['status']}")
    
    # ========================================================================
    # 🆕 DETECÇÃO PRIORITÁRIA DE TAG E INTENÇÃO DE HUMANO
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
        # Recuperação inteligente de identidade
        is_in_booking_flow = state.get("service") is not None
        has_provided_name = state.get("name") is not None
        
        if is_in_booking_flow and not has_provided_name:
            client_name = "Cliente não identificado"
            print(f"📊 [CONTEXTO] Cliente em agendamento sem identificação - usando fallback")
        else:
            client_name = (
                state.get("name") or
                state.get("last_booking", {}).get("name") or
                sender_name or
                "Cliente não identificado"
            )
        
        # Registra na planilha
        set_robot_mute(
            phone=phone,
            mute_status=True,
            name=client_name,
            status="Solicitou falar com a dona"
        )
        
        print(f"👤 [HANDOFF] Cliente '{client_name}' ({phone}) solicitou atendimento humano")
        
        # 🆕 Retorna estado atualizado para indicar que está em atendimento humano
        return (
            "Entendi 😊\n"
            "Vou te direcionar para atendimento humano agora.\n"
            "⏳ Por favor, aguarde um momento que você será atendida.\n"
            "Obrigada pela paciência 💖",
            {
                "current_step": state["status"],  # Mantém step atual
                "conversation_data": session_data,
                "status": "waiting_human"  # Marca como aguardando humano
            }
        )
    
    # ========================================================================
    # CORREÇÃO: Detectar despedida após agendamento confirmado
    # ========================================================================
    
    if state.get("status") == "completed":
        if any(x in text for x in ["nao", "não", "obrigado", "obrigada", "valeu", "vlw", "ta bom", "tá bom", "beleza", "so isso", "só isso", "ok"]):
            name = state.get("last_booking", {}).get("name", "")
            date = state.get("last_booking", {}).get("date", "")
            time = state.get("last_booking", {}).get("time", "")
            
            state["status"] = "farewell_sent"
            
            if name and date and time:
                return (
                    f"Perfeito, *{name}*! 💖\n\n"
                    "Foi um prazer te atender!\n"
                    f"Nos vemos em *{date}* às *{time}* ✨\n\n"
                    "Até lá! 👋",
                    prepare_session_update(state)
                )
            else:
                return (
                    "Perfeito! 💖\n\n"
                    "Foi um prazer te atender!\n"
                    "Até breve! 👋",
                    prepare_session_update(state)
                )
    
    if state.get("status") == "farewell_sent":
        if state.get("last_booking"):
            state["status"] = "completed"
        else:
            state["status"] = "start"
    
    # ========================================================================
    # DETECÇÃO DE PERGUNTA SOBRE SERVIÇOS
    # ========================================================================
    
    if any(palavra in text for palavra in ["servico", "serviços", "servicos", "lista", "quais servico", "que servico", "tem quais", "oferece"]):
        if state.get("status") not in ["awaiting_welcome_response", "awaiting_name", "awaiting_confirmation"]:
            state["status"] = "awaiting_service_selection"
            
            services_list = format_services_list()
            return (
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*",
                prepare_session_update(state)
            )
    
    # ========================================================================
    # CANCELAMENTO
    # ========================================================================
    
    if "cancelar" in text or "desmarcar" in text:
        # Caso 1: Cancelamento após agendamento confirmado
        if state.get("last_booking"):
            last_booking = state["last_booking"]
            cancelado = cancel_appointment(phone)
            
            # Limpa estado
            state = {
                "status": "start",
                "service": None,
                "date": None,
                "time": None,
                "name": None
            }
            
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
                    "É só me dizer! Estou aqui para ajudar 💖",
                    prepare_session_update(state)
                )
            else:
                return (
                    f"Entendi, *{last_booking['name']}*! 😊\n\n"
                    "⚠️ *IMPORTANTE:* Entre em contato conosco para confirmar o cancelamento!\n\n"
                    "📞 WhatsApp: (11) 9 1234-5678\n\n"
                    "Se quiser reagendar depois, é só me chamar! 💖",
                    prepare_session_update(state)
                )
        
        # Caso 2: Cancelamento durante o processo
        if state.get("service"):
            service_name = state.get("service", {}).get("name", "")
            date_str = state.get("date", "")
            time_str = state.get("time", "")
            
            state = {
                "status": "start",
                "service": None,
                "date": None,
                "time": None,
                "name": None
            }
            
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
            
            return (msg, prepare_session_update(state))
        
        # Caso 3: Sem nada em andamento
        state = {"status": "start", "service": None, "date": None, "time": None, "name": None}
        return (
            "Tudo bem! Se precisar de algo, é só chamar. 👋",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # DESPEDIDA
    # ========================================================================
    
    if "tchau" in text or "ate logo" in text or "até logo" in text:
        name = ""
        if state.get("last_booking"):
            name = state["last_booking"]["name"]
        
        if name:
            return (
                f"Até logo, *{name}*! 💖 Foi um prazer te atender! 👋",
                prepare_session_update(state)
            )
        return (
            "Até logo! 💖 Foi um prazer te atender! 👋",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # RESPOSTAS CONTEXTUAIS (ENDEREÇO, TELEFONE, INSTAGRAM)
    # ========================================================================
    
    # ENDEREÇO
    if any(palavra in text for palavra in ["endereco", "endereço", "local", "onde", "localizacao", "localização"]):
        if state.get("last_booking"):
            booking = state["last_booking"]
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                f"✨ Nos vemos em *{booking['date']}* às *{booking['time']}*! 💖",
                prepare_session_update(state)
            )
        elif state.get("status") == "awaiting_welcome_response":
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                "Se quiser, posso te mostrar nossos serviços 😊",
                prepare_session_update(state)
            )
        else:
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "address"
            
            return (
                "📍 *Endereço do Studio Olhar Sob Medida:*\n\n"
                "Rua Horácio de Castilho, 21\n"
                "Vila Maria Alta – São Paulo/SP\n\n"
                "🕘 Funcionamos de terça a sábado, das 9h às 19h.\n\n"
                "Se quiser, posso te mostrar nossos serviços 😊",
                prepare_session_update(state)
            )
    
    # TELEFONE
    if any(palavra in text for palavra in ["telefone", "contato", "whatsapp", "ligar"]):
        if state.get("last_booking"):
            booking = state["last_booking"]
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                f"Qualquer dúvida, estou aqui! 😊\n"
                f"Nos vemos em *{booking['date']}* às *{booking['time']}* ✨",
                prepare_session_update(state)
            )
        elif state.get("status") == "awaiting_welcome_response":
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                "Qualquer dúvida, estou aqui! 😊",
                prepare_session_update(state)
            )
        else:
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "phone"
            
            return (
                "📞 *Nossos contatos:*\n\n"
                "WhatsApp: (11) 9 1234-5678\n"
                "Telefone fixo: (11) 1234-5678\n\n"
                "👉 Posso te ajudar com algum agendamento? 😊",
                prepare_session_update(state)
            )
    
    # INSTAGRAM
    if any(palavra in text for palavra in ["instagram", "insta", "rede social", "redes sociais", "facebook", "social", "fotos", "portfolio"]):
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
                f"Confira nossos trabalhos! Te esperamos em *{booking['date']}* às *{booking['time']}* 💖",
                prepare_session_update(state)
            )
        elif state.get("status") == "awaiting_welcome_response":
            return (
                "📱 *Siga a gente no Instagram!*\n\n"
                "🌟 @olharsobmedida\n"
                "https://www.instagram.com/olharsobmedida\n\n"
                "Lá você encontra:\n"
                "✨ Nossos trabalhos\n"
                "📸 Fotos antes e depois\n"
                "🎁 Promoções exclusivas\n"
                "💄 Dicas de beleza\n\n"
                "Vem conferir! 😊💖",
                prepare_session_update(state)
            )
        else:
            state["status"] = "awaiting_engagement_response"
            state["engagement_context"] = "instagram"
            
            return (
                "📱 *Siga a gente no Instagram!*\n\n"
                "🌟 @olharsobmedida\n"
                "https://www.instagram.com/olharsobmedida\n\n"
                "Lá você encontra:\n"
                "✨ Nossos trabalhos\n"
                "📸 Fotos antes e depois\n"
                "🎁 Promoções exclusivas\n"
                "💄 Dicas de beleza\n\n"
                "👉 Viu algum serviço que te interessou? Posso agendar para você! 💖",
                prepare_session_update(state)
            )
    
    # ========================================================================
    # RESPOSTA AO ENGAJAMENTO
    # ========================================================================
    
    if state.get("status") == "awaiting_engagement_response":
        if any(x in text for x in ["sim", "claro", "quero", "pode", "gostaria", "ok"]):
            state["status"] = "awaiting_service_selection"
            
            services_list = format_services_list()
            return (
                "Perfeito! ✨ Vou te ajudar com o agendamento 💖\n\n"
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*",
                prepare_session_update(state)
            )
        
        elif any(x in text for x in ["nao", "não", "agora nao", "agora não", "depois"]):
            state = {"status": "start", "service": None, "date": None, "time": None, "name": None}
            return (
                "Tudo bem 😊 Quando quiser conhecer ou agendar um serviço, é só me chamar. Estarei por aqui ✨",
                prepare_session_update(state)
            )
        
        else:
            detected_service = detect_service_by_number_or_name(text)
            
            if detected_service:
                state["service"] = detected_service
                state["status"] = "awaiting_date"
                
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
                
                return (date_msg, prepare_session_update(state))
            else:
                return (
                    "Desculpe, não entendi 😕 Você gostaria de agendar um serviço? (responda *sim* ou *não*)",
                    prepare_session_update(state)
                )
    
    # ========================================================================
    # DETECÇÃO RÁPIDA DE SERVIÇO (ATALHO)
    # ========================================================================
    
    detected_service = None
    
    if state.get("status") not in ["awaiting_welcome_response", "awaiting_name", "awaiting_confirmation"]:
        detected_service = detect_service_by_number_or_name(text)
            
    if detected_service:
        state["service"] = detected_service
        state["status"] = "awaiting_date"
        
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
        
        return (date_msg, prepare_session_update(state))
    
    # ========================================================================
    # FLUXO 1: BOAS VINDAS
    # ========================================================================
    
    if state["status"] == "start":
        state["status"] = "awaiting_welcome_response"
        
        return (
            "✨ Olá! É um prazer receber você no Studio Olhar Sob Medida ✨\n\n"
            "Sou a assistente virtual do estúdio 😊\n"
            "Posso te ajudar com informações ou agendamentos.\n\n"
            "👉 Você gostaria de conhecer nossos serviços?",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # FLUXO 2: RESPOSTA DA APRESENTAÇÃO
    # ========================================================================
    
    if state["status"] == "awaiting_welcome_response":
        if any(x in text for x in ["sim", "claro", "quero", "pode", "gostaria", "lista", "sim por favor", "com certeza", "aceito"]):
            state["status"] = "awaiting_service_selection"
            
            services_list = format_services_list()
            return (
                "Confira nossos serviços:\n\n"
                f"{services_list}\n\n"
                "👉 Digite o número ou nome do serviço que deseja agendar!\n\n"
                "💡 Exemplo: *1* ou *sobrancelha*",
                prepare_session_update(state)
            )
        elif any(x in text for x in ["nao", "não", "agora nao", "agora não", "depois", "talvez depois"]):
            state = {"status": "start", "service": None, "date": None, "time": None, "name": None}
            return (
                "Entendi! Se quiser agendar algo depois, é só me chamar! 😊",
                prepare_session_update(state)
            )
        else:
            return (
                "Desculpe, não entendi 😊\n\n"
                "Você gostaria de conhecer nossos serviços?\n"
                "👉 Responda *sim* ou *não*, por favor!",
                prepare_session_update(state)
            )
    
    # ========================================================================
    # FLUXO 3: ESCOLHA DO SERVIÇO
    # ========================================================================
    
    if state["status"] == "awaiting_service_selection":
        detected_service = detect_service_by_number_or_name(text)
        
        if detected_service:
            state["service"] = detected_service
            state["status"] = "awaiting_date"
            
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
            
            return (date_msg, prepare_session_update(state))
        else:
            return (
                "Não entendi qual serviço você quer 😕 Tente digitar o *número* ou o *nome*, como *1* ou *Sobrancelha*.",
                prepare_session_update(state)
            )
    
    # ========================================================================
    # 🆕 FLUXO 4: DATA (COM PARSING FLEXÍVEL E VALIDAÇÃO DE SAUDAÇÃO)
    # ========================================================================
    
    if state["status"] == "awaiting_date":
        # 🆕 Parsing flexível - extrai data e horário (podem vir juntos)
        date, time = extract_date_and_time(text)
        
        if not date:
            return (
                "Não consegui entender a data 😕\n\n"
                "Por favor, me diga a data que você prefere.\n"
                "💡 Exemplos: *hoje*, *amanhã*, *20/01*, *dia 20*",
                prepare_session_update(state)
            )
        
        # Valida se é dia de funcionamento
        is_open, day_name = is_working_day(date)
        
        if not is_open:
            next_day = get_next_working_day(date)
            next_day_str = next_day.strftime('%d/%m') if next_day else "próximo dia útil"
            return (
                f"⚠️ {day_name} ({date.strftime('%d/%m')}) o studio está fechado.\n\n"
                "🕒 Funcionamos de *Terça a Sábado* das *9h às 19h*\n\n"
                f"👉 Que tal agendar para *{next_day_str}* ou outra data da sua preferência?",
                prepare_session_update(state)
            )

        # Valida se data está disponível na planilha
        raw_available_dates = get_available_dates() 
        clean_available_dates = standardize_sheet_dates(raw_available_dates)
        
        user_date_str = date.strftime("%d/%m/%Y")
        
        print(f"📊 [VALIDAÇÃO] Data usuário: {user_date_str} | Datas disponíveis: {clean_available_dates}")

        if user_date_str not in clean_available_dates:
            return (
                f"Essa data (*{date.strftime('%d/%m')}*) não está disponível ou não temos agenda aberta 😕\n\n"
                "👉 Pode escolher outra data, por favor?",
                prepare_session_update(state)
            )
        
        # Salva a data
        state["date"] = date
        
        # 🆕 SE HORÁRIO VEIO JUNTO, VALIDA E PULA PARA O NOME
        if time:
            print(f"✅ [FLUXO] Cliente informou data E horário juntos!")
            
            try:
                available_times = get_available_times_for_date(date.strftime("%d/%m/%Y"))
            except Exception as e:
                print(f"❌ [ERROR] Falha ao buscar horários: {e}")
                return (
                    f"Desculpe, tive um problema ao verificar os horários disponíveis para *{date.strftime('%d/%m')}* 😕\n\n"
                    "Por favor, tente novamente ou escolha apenas a data primeiro.",
                    prepare_session_update(state)
                )
            
            if time not in available_times:
                 return (
                    f"Consegui a data *{date.strftime('%d/%m')}*, mas o horário *{time}* já está ocupado 😕\n\n"
                    f"📋 Horários disponíveis: {', '.join(available_times)}\n\n"
                    "👉 Qual horário você prefere?",
                    prepare_session_update(state)
                )

            # Horário válido! Pula direto para nome
            state["time"] = time
            state["status"] = "awaiting_name"
            
            return (
                f"Perfeito! ✨\n"
                f"📅 Data: *{date.strftime('%d/%m')}*\n"
                f"⏰ Horário: *{time}*\n\n"
                "👉 Para finalizar, qual é o seu *nome completo*?\n"
                "(Nome e sobrenome, por favor)",
                prepare_session_update(state)
            )
        
        # SE NÃO VEIO HORÁRIO, PERGUNTA
        state["status"] = "awaiting_time"
        
        return (
            f"Perfeito! ✨ Data escolhida: *{date.strftime('%d/%m')}*\n\n"
            "👉 Qual horário você prefere?\n"
            "💡 Funcionamos das *9h às 19h*",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # FLUXO 5: HORÁRIO
    # ========================================================================
    
    if state["status"] == "awaiting_time":
        _, time = extract_date_and_time(text)
        
        if not time:
            return (
                "Não consegui entender o horário 😕\n\n"
                "Por favor, me diga o horário que você prefere.\n"
                "💡 Exemplos: *15h*, *15:00*, *3 da tarde*",
                prepare_session_update(state)
            )
        
        try:
            available_times = get_available_times_for_date(state["date"].strftime("%d/%m/%Y"))
        except Exception as e:
            print(f"❌ [ERROR] Falha ao buscar horários: {e}")
            return (
                f"Desculpe, tive um problema ao verificar os horários disponíveis 😕\n\n"
                "Por favor, tente novamente.",
                prepare_session_update(state)
            )
        
        if time not in available_times:
             return (
                f"Esse horário (*{time}*) não está disponível 😕\n\n"
                f"📋 Horários disponíveis: {', '.join(available_times)}\n\n"
                "👉 Qual horário você prefere?",
                prepare_session_update(state)
            )

        state["time"] = time
        state["status"] = "awaiting_name"
        
        return (
            f"Perfeito! ✨\n"
            f"📅 Data: *{state['date'].strftime('%d/%m')}*\n"
            f"⏰ Horário: *{time}*\n\n"
            "👉 Para finalizar, qual é o seu *nome completo*?\n"
            "(Nome e sobrenome, por favor)",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # 🆕 FLUXO 6: NOME DO CLIENTE (COM VALIDAÇÃO DE SAUDAÇÃO)
    # ========================================================================
    
    if state["status"] == "awaiting_name":
        # 🆕 VALIDAÇÃO: Rejeitar saudações
        if is_greeting(message):
            return (
                "Opa! Isso é uma saudação 😊\n\n"
                "Preciso do seu *nome completo* para finalizar o agendamento.\n\n"
                "💡 Exemplo: *Maria Silva* ou *João Santos*\n\n"
                "👉 Qual é o seu nome?",
                prepare_session_update(state)
            )
        
        name = message.strip()
        for phrase in ["meu nome e", "meu nome é", "me chamo", "sou", "eu sou"]:
            name = name.replace(phrase, "").strip()
        
        name_parts = name.split()
        if len(name_parts) < 2:
            return (
                "Por favor, me informe seu *nome completo* (nome e sobrenome) 😊\n"
                "💡 Exemplo: Maria Silva",
                prepare_session_update(state)
            )
        
        state["name"] = name.title()
        state["status"] = "awaiting_confirmation"
        
        return (
            f"Prazer, *{state['name']}*! 😊\n\n"
            f"📝 Resumo do agendamento:\n"
            f"👤 Nome: *{state['name']}*\n"
            f"✨ Serviço: *{state['service']['name']}*\n"
            f"📅 Data: *{state['date'].strftime('%d/%m')}*\n"
            f"⏰ Horário: *{state['time']}*\n\n"
            "👉 Posso confirmar o agendamento?",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # 🆕 FLUXO 7: CONFIRMAÇÃO (COM VALIDAÇÃO DE SAUDAÇÃO)
    # ========================================================================
    
    if state["status"] == "awaiting_confirmation":
        # 🆕 VALIDAÇÃO: Rejeitar saudações
        if is_greeting(message):
            return (
                f"Entendi a saudação! 😊\n\n"
                f"Mas preciso saber: você quer confirmar este agendamento?\n\n"
                f"📝 Resumo:\n"
                f"👤 Nome: *{state['name']}*\n"
                f"✨ Serviço: *{state['service']['name']}*\n"
                f"📅 Data: *{state['date'].strftime('%d/%m')}*\n"
                f"⏰ Horário: *{state['time']}*\n\n"
                f"👉 Responda *sim* para confirmar ou *não* para cancelar",
                prepare_session_update(state)
            )
        
        if any(x in text for x in ["sim", "confirmar", "ok", "pode"]):
            book_appointment(
                phone=phone,
                name=state["name"],
                service=state["service"]["name"],
                date=state["date"].strftime("%d/%m/%Y"),
                time=state["time"]
            )
            
            # Salva informações do último agendamento
            state["status"] = "completed"
            state["last_booking"] = {
                "name": state["name"],
                "service": state["service"]["name"],
                "date": state["date"].strftime("%d/%m"),
                "time": state["time"]
            }
            
            return (
                f"Agendamento confirmado com sucesso, *{state['name']}*! 🎉✨\n\n"
                "Estamos te esperando no *Studio Olhar Sob Medida* 💖\n\n"
                f"📍 Rua Horácio de Castilho, 21 - Vila Maria Alta\n"
                f"📅 {state['date'].strftime('%d/%m')} às {state['time']}\n\n"
                "Vai ficar lindo! Será um prazer te receber ✨\n\n"
                "👉 Posso te ajudar com mais alguma coisa? 😊",
                prepare_session_update(state)
            )
            
        if any(x in text for x in ["nao", "não", "cancelar"]):
            state = {"status": "start", "service": None, "date": None, "time": None, "name": None}
            return (
                "Tudo bem! 😊\n\n"
                "Quando quiser agendar, é só me chamar!\n"
                "Estamos ansiosos pelo seu retorno! ✨",
                prepare_session_update(state)
            )
            
        return (
            "👉 Posso confirmar o agendamento? (responda *sim* ou *não*)",
            prepare_session_update(state)
        )
    
    # ========================================================================
    # FALLBACK
    # ========================================================================
    
    if state.get("last_booking"):
        return (
            "Desculpe, não entendi sua mensagem 😊\n\n"
            "💡 Posso te ajudar com:\n"
            "📍 Informações sobre o studio\n"
            "📞 Nossos contatos\n"
            "📱 Redes sociais\n"
            "🔄 Cancelar ou reagendar\n\n"
            "Como posso te ajudar?",
            prepare_session_update(state)
        )
    
    state = {"status": "start", "service": None, "date": None, "time": None, "name": None}
    return (
        "Desculpa, não entendi 😊 Em que posso te ajudar?",
        prepare_session_update(state)
    )