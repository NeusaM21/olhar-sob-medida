from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import MessageLog
from backend.ai.engine import generate_ai_response
from backend.integrations.sheets import is_robot_muted
from backend.core.utils import send_whatsapp_message

router = APIRouter()

# --------------------------------------------------
# SCHEMA (Swagger / Testes Manuais)
# --------------------------------------------------

class ChatTestMessage(BaseModel):
    phone: str
    message: str

# --------------------------------------------------
# ROTA DE TESTE / CHAT
# --------------------------------------------------

@router.post("/message", tags=["chat"])
async def chat_test_message(
    payload: ChatTestMessage,
    db: Session = Depends(get_db)
):
    """
    Endpoint de chat para o Studio Olhar Sob Medida.

    - Recebe mensagem do usuário
    - Verifica se o robô está silenciado
    - Encaminha a mensagem para o engine
    - Retorna e envia a resposta gerada
    """

    phone = payload.phone.strip()
    message = payload.message.strip()

    if not message:
        return {"status": "empty_message"}

    # 🔇 Verifica se o robô está silenciado
    if is_robot_muted(phone):
        return {
            "status": "muted",
            "reason": "Número silenciado na planilha Controle_Robo."
        }

    # 🤖 Chama o motor de conversação
    ai_response = generate_ai_response(
        phone=phone,
        message=message
    )

    print(f"🤖 IA respondeu: {ai_response}")

    # 📤 Envia resposta via WhatsApp
    try:
        send_whatsapp_message(phone, ai_response)
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem WhatsApp: {e}")

    # 🧾 Log no banco SQLite
    try:
        db.add(
            MessageLog(
                sender=phone,
                message=message,
                response=ai_response
            )
        )
        db.commit()
    except Exception as e:
        print(f"⚠️ Erro ao salvar log no banco SQLite: {e}")
        db.rollback()

    return {
        "status": "ok",
        "ai_response": ai_response
    }