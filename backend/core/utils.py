import requests
from backend.core.config import settings

# --------------------------------------------------
# WHATSAPP (Z-API)
# --------------------------------------------------

def send_whatsapp_message(phone: str, message: str):
    """
    Envia mensagem via Z-API usando credenciais centralizadas.
    Função utilitária pura (sem lógica de negócio).
    """

    if not phone or not message:
        print("⚠️ send_whatsapp_message chamado com parâmetros inválidos")
        return None

    url = (
        f"https://api.z-api.io/instances/"
        f"{settings.Z_API_INSTANCE_ID}/token/"
        f"{settings.Z_API_TOKEN}/send-text"
    )

    headers = {
        "Content-Type": "application/json",
        "Client-Token": settings.ZAPI_CLIENT_TOKEN
    }

    payload = {
        "phone": phone,
        "message": message
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print(
            f"📤 Z-API | phone={phone} "
            f"status={response.status_code} "
            f"response={response.text}"
        )

        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de rede ao enviar mensagem WhatsApp: {e}")
        return None

    except Exception as e:
        print(f"❌ Erro inesperado no envio WhatsApp: {e}")
        return None