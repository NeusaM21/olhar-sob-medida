from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.integrations.sheets import book_appointment # Importa a lógica que alteramos

router = APIRouter()

# Modelo de dados para receber o agendamento
class Appointment(BaseModel):
    date: str
    time: str
    client_name: str
    service_name: str
    phone: str

@router.post("/create")
def create_booking(appointment: Appointment):
    """
    Rota que recebe o pedido de agendamento e trata se foi possível ou não gravar.
    """
    # Tenta realizar o agendamento no Sheets
    success = book_appointment(
        appointment.date, 
        appointment.time, 
        appointment.client_name, 
        appointment.service_name, 
        appointment.phone
    )

    if success:
        return {"status": "success", "message": "Agendamento realizado com sucesso!"}
    else:
        # Se retornar False (horário ocupado ou erro), retornamos um erro 400
        # A IA verá esse erro e usará o Prompt para explicar à cliente
        raise HTTPException(status_code=400, detail="Horário indisponível ou erro na planilha")

@router.get("/test")
def test_booking():
    return {"message": "booking route OK"}