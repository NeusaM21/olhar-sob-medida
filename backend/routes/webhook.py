from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import MessageLog
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

        # Verifica mute do robô
        if is_robot_muted(phone):
            print("🔇 Robô mutado para:", phone)
            return {"status": "muted"}

        # Log de entrada
        db.add(
            MessageLog(
                phone=phone,
                message=message,
                direction="in"
            )
        )
        db.commit()

        # 🤖 Chamada correta do engine
        print("🤖 Chamando engine...")
        ai_response = generate_ai_response(phone, message)

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

        return {"status": "ok"}

    except Exception as e:
        print("❌ Erro no webhook:", str(e))
        return {"status": "error", "detail": str(e)}