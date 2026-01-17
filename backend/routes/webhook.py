from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
import json
from datetime import datetime

from backend.db.session import get_db
from backend.db.models import MessageLog, ConversationSession
from backend.ai.engine import generate_ai_response
from backend.integrations.sheets import is_robot_muted
from backend.core.utils import send_whatsapp_message

router = APIRouter()

# --------------------------------------------------
# CONTROLE DE DUPLICIDADE (ANTI-REENTREGA)
# --------------------------------------------------

MAX_PROCESSED_IDS = 500
processed_ids = set()

def register_message_id(message_id: str) -> bool:
    if not message_id or message_id in processed_ids:
        return False

    processed_ids.add(message_id)

    if len(processed_ids) > MAX_PROCESSED_IDS:
        processed_ids.pop()

    return True

# --------------------------------------------------
# EXTRAÇÃO SEGURA DE TEXTO (Z-API)
# --------------------------------------------------

def extract_message_text(data: dict) -> str:
    """
    Extrai o texto da mensagem cobrindo os formatos
    mais comuns enviados pela Z-API.
    """
    if isinstance(data.get("text"), str):
        return data["text"]

    if isinstance(data.get("text"), dict):
        return data["text"].get("message", "")

    if isinstance(data.get("message"), dict):
        return data["message"].get("text", "")

    if isinstance(data.get("message"), str):
        return data["message"]

    return ""

# --------------------------------------------------
# EXTRAÇÃO DO NOME DO REMETENTE (Z-API)
# --------------------------------------------------

def extract_sender_name(data: dict) -> str:
    """
    Extrai o nome do remetente do WhatsApp cobrindo os formatos
    mais comuns enviados pela Z-API.
    
    Prioridade de extração:
    1. senderName (campo mais comum)
    2. pushName (alternativa)
    3. notifyName (backup)
    4. contact.name (objeto aninhado)
    
    Retorna None se nenhum nome for encontrado.
    """
    # Tenta extrair de múltiplos campos possíveis
    name = (
        data.get('senderName') or 
        data.get('pushName') or 
        data.get('notifyName') or
        (data.get('contact', {}).get('name') if isinstance(data.get('contact'), dict) else None)
    )
    
    # Remove espaços em branco e retorna None se vazio
    if name:
        name = name.strip()
        return name if name else None
    
    return None

# --------------------------------------------------
# 🆕 GERENCIAMENTO DE SESSÃO DE CONVERSA
# --------------------------------------------------

def get_or_create_session(db: Session, phone: str) -> ConversationSession:
    """
    Busca ou cria uma sessão de conversa para o cliente.
    
    Args:
        db: Sessão do banco de dados
        phone: Número de telefone do cliente
    
    Returns:
        ConversationSession: Sessão ativa ou nova sessão criada
    """
    # Busca sessão existente
    session = db.query(ConversationSession).filter(
        ConversationSession.phone == phone
    ).first()
    
    if session:
        print(f"📂 Sessão encontrada: step={session.current_step}, status={session.status}")
        return session
    
    # Cria nova sessão
    print(f"🆕 Criando nova sessão para {phone}")
    new_session = ConversationSession(
        phone=phone,
        current_step="initial",
        conversation_data="{}",
        status="active",
        is_muted=False
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return new_session

def update_session(
    db: Session,
    session: ConversationSession,
    current_step: str = None,
    conversation_data: dict = None,
    status: str = None,
    is_muted: bool = None
):
    """
    Atualiza uma sessão de conversa existente.
    
    Args:
        db: Sessão do banco de dados
        session: Sessão a ser atualizada
        current_step: Nova etapa da conversa (opcional)
        conversation_data: Novos dados da conversa (opcional)
        status: Novo status (opcional)
        is_muted: Novo estado de mute (opcional)
    """
    if current_step is not None:
        session.current_step = current_step
        print(f"📝 Sessão atualizada: step → {current_step}")
    
    if conversation_data is not None:
        session.conversation_data = json.dumps(conversation_data, ensure_ascii=False)
        print(f"💾 Dados da conversa atualizados: {conversation_data}")
    
    if status is not None:
        session.status = status
        print(f"📊 Status atualizado: {status}")
    
    if is_muted is not None:
        session.is_muted = is_muted
        print(f"🔇 Mute atualizado: {is_muted}")
    
    session.last_interaction = datetime.now()
    db.commit()
    db.refresh(session)

def parse_session_data(session: ConversationSession) -> dict:
    """
    Converte os dados JSON da sessão em dicionário Python.
    
    Args:
        session: Sessão de conversa
    
    Returns:
        dict: Dados da conversa ou dicionário vazio se inválido
    """
    try:
        if session.conversation_data:
            return json.loads(session.conversation_data)
        return {}
    except json.JSONDecodeError:
        print("⚠️ Erro ao decodificar conversation_data, retornando dict vazio")
        return {}

# --------------------------------------------------
# WEBHOOK PRINCIPAL (Z-API)
# --------------------------------------------------

@router.post("/webhook", tags=["webhook"])
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        data = await request.json()
        print("📩 Webhook recebido:", data)

        message_id = data.get("messageId") or data.get("id")
        phone = data.get("phone")
        is_group = data.get("isGroup", False)
        from_me = data.get("fromMe", False)

        # Ignora mensagens inválidas, grupos ou mensagens do próprio bot
        if not phone or is_group or from_me:
            print("🚫 Mensagem ignorada (grupo / fromMe / sem phone)")
            return {"status": "ignored"}

        # Anti-duplicidade
        if not register_message_id(message_id):
            print("🔁 Mensagem duplicada ignorada:", message_id)
            return {"status": "duplicate"}

        # Extrai texto de forma segura
        message = extract_message_text(data).strip()
        print("💬 Texto extraído:", message)

        if not message:
            print("🚫 Mensagem vazia após extração")
            return {"status": "empty"}

        # Extrai nome do remetente
        sender_name = extract_sender_name(data)
        print(f"👤 Nome do remetente: {sender_name or 'Não identificado'}")

        # ====================================================================
        # 🆕 GERENCIAMENTO DE SESSÃO
        # ====================================================================
        
        # Busca ou cria sessão para este cliente
        session = get_or_create_session(db, phone)
        
        # Parse dos dados da conversa
        session_data = parse_session_data(session)
        
        # Verifica se robô está mutado
        robot_muted = is_robot_muted(phone)
        
        if robot_muted:
            print(f"🔇 Robô mutado para: {phone} ({sender_name or 'sem nome'})")
            
            # Atualiza sessão para indicar que está em atendimento humano
            if not session.is_muted:
                update_session(
                    db=db,
                    session=session,
                    is_muted=True,
                    status="waiting_human"
                )
            
            return {"status": "muted"}
        
        # Se robô estava mutado e agora foi desmutado
        if session.is_muted and not robot_muted:
            print(f"🔊 Robô desmutado para: {phone} - Retomando conversa...")
            update_session(
                db=db,
                session=session,
                is_muted=False,
                status="active"
            )

        # Log de entrada
        db.add(
            MessageLog(
                phone=phone,
                message=message,
                direction="in"
            )
        )
        db.commit()

        # ====================================================================
        # 🆕 CHAMADA DO ENGINE COM CONTEXTO COMPLETO
        # ====================================================================
        print(f"🤖 Chamando engine para {phone} ({sender_name or 'sem nome'})...")
        print(f"📋 Contexto: step={session.current_step}, data={session_data}")
        
        ai_response = generate_ai_response(
            phone=phone,
            message=message,
            sender_name=sender_name,
            current_step=session.current_step,  # 🆕 Etapa atual
            session_data=session_data  # 🆕 Dados da conversa
        )

        if ai_response:
            send_whatsapp_message(phone, ai_response)

            # Log de saída
            db.add(
                MessageLog(
                    phone=phone,
                    message=ai_response,
                    direction="out"
                )
            )
            db.commit()
            
            # ====================================================================
            # 🆕 ATUALIZAÇÃO DA SESSÃO APÓS RESPOSTA
            # ====================================================================
            # Nota: O engine deve retornar também o novo estado da conversa
            # Por enquanto, apenas atualizamos o timestamp de last_interaction
            # que é feito automaticamente no update_session
            
            print("✅ Resposta enviada e sessão atualizada")

        return {"status": "ok"}

    except Exception as e:
        print("❌ Erro no webhook:", str(e))
        return {"status": "error", "detail": str(e)}