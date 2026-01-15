from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from backend.db.session import Base

# --------------------------------------------------
# CLIENTES
# --------------------------------------------------

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Client(name={self.name}, phone={self.phone})>"

# --------------------------------------------------
# AGENDAMENTOS
# --------------------------------------------------

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(100), nullable=False)
    service = Column(String(100), nullable=False)
    scheduled_time = Column(String(20), nullable=False)  # ex: "15:00"
    status = Column(String(30), default="pre-agendado")
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return (
            f"<Appointment(client={self.client_name}, "
            f"service={self.service}, time={self.scheduled_time})>"
        )

# --------------------------------------------------
# LOG DE MENSAGENS (WHATSAPP)
# --------------------------------------------------

class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Número do cliente (WhatsApp)
    phone = Column(String(20), nullable=False, index=True)

    # Texto da mensagem (entrada ou saída)
    message = Column(Text, nullable=False)

    # Direção da mensagem: "in" | "out"
    direction = Column(String(10), nullable=False)

    # Data/hora do evento
    timestamp = Column(DateTime, default=datetime.now, index=True)

    def __repr__(self):
        return (
            f"<MessageLog(phone={self.phone}, "
            f"direction={self.direction}, "
            f"timestamp={self.timestamp})>"
        )