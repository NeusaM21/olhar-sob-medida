import os
import json
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from functools import lru_cache

# --------------------------------------------------
# PATHS
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRICE_LIST_PATH = os.path.join(BASE_DIR, "data", "price_list.json")

# --------------------------------------------------
# GOOGLE SHEETS CONFIG
# --------------------------------------------------

SPREADSHEET_NAME = os.getenv("PLANILHA_NOME", "Agenda Olhar Sob Medida")

WORKSHEET_AGENDA_NAME = "Agenda"
WORKSHEET_CONTROLE_NAME = "Controle_Robo"

# Colunas da aba Agenda
COL_DATA = 1
COL_HORA = 2
COL_CLIENTE = 3
COL_SERVICO = 4
COL_TELEFONE = 5
COL_STATUS = 6

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --------------------------------------------------
# AUTH
# --------------------------------------------------

def _get_client():
    raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
    if not raw:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS não configurada")

    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def _open_sheet(sheet_name: str):
    client = _get_client()
    return client.open(SPREADSHEET_NAME).worksheet(sheet_name)

# --------------------------------------------------
# SERVICES (DURAÇÃO)
# --------------------------------------------------

def load_services_duration():
    """
    Retorna dict: { "Nome do Serviço": duração_em_minutos }
    """
    if not os.path.exists(PRICE_LIST_PATH):
        return {}

    with open(PRICE_LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        s["name"]: s.get("duration_minutes", 30)
        for s in data.get("services", [])
    }

def calcular_proximo_horario(hora_str: str, minutos: int) -> str:
    base = datetime.strptime(hora_str, "%H:%M")
    return (base + timedelta(minutes=minutos)).strftime("%H:%M")

# --------------------------------------------------
# AGENDA — FONTE DA VERDADE
# --------------------------------------------------

@lru_cache(maxsize=32)
def get_available_dates_cached(cache_key: str = None):
    """
    Versão com cache de get_available_dates.
    cache_key é usado apenas para invalidar cache quando necessário.
    """
    sheet = _open_sheet(WORKSHEET_AGENDA_NAME)
    rows = sheet.get_all_values()[1:]  # ignora cabeçalho

    dates = set()

    for row in rows:
        if len(row) < 2:
            continue

        date_str = row[0].strip()
        if not date_str:
            continue

        try:
            datetime.strptime(date_str, "%d/%m/%Y")
            dates.add(date_str)
        except ValueError:
            continue

    return list(dates)

def get_available_dates():
    """
    Lê a aba Agenda e retorna uma lista de datas em formato DD/MM/YYYY (strings)
    que possuem pelo menos um horário disponível.
    """
    # Cache por 5 minutos (use timestamp arredondado)
    cache_key = str(int(datetime.now().timestamp() // 300))
    return get_available_dates_cached(cache_key)

def get_available_times_for_date(date_str: str):
    """
    Retorna lista de horários disponíveis (HH:MM) para uma data.
    date_str deve estar no formato DD/MM/YYYY
    
    OTIMIZADO: Busca apenas linhas da data específica
    """
    try:
        sheet = _open_sheet(WORKSHEET_AGENDA_NAME)
        
        # 🚀 OTIMIZAÇÃO: Usa batch_get ao invés de get_all_values
        # Isso é mais rápido para planilhas grandes
        all_data = sheet.get_all_values()[1:]  # Skip header
        
        times = []
        
        # 🚀 OTIMIZAÇÃO: Para assim que encontrar todos os horários da data
        for row in all_data:
            if len(row) < 3:
                continue
            
            # Se achou a data e célula de cliente está vazia
            if row[0] == date_str and not row[2].strip():
                times.append(row[1])
        
        print(f"📅 [HORÁRIOS] {date_str}: {len(times)} slots disponíveis")
        return times
        
    except Exception as e:
        print(f"❌ [ERROR get_available_times_for_date] {date_str}: {e}")
        # Retorna lista vazia em caso de erro ao invés de travar
        return []

# --------------------------------------------------
# AGENDA CORE (CHAMADA APENAS APÓS CONFIRMAÇÃO)
# --------------------------------------------------

def book_appointment(phone, name, service, date, time):
    """
    Marca o agendamento preenchendo as linhas correspondentes
    ao tempo total do serviço.
    
    Args:
        phone: telefone do cliente
        name: nome do cliente
        service: nome do serviço
        date: data no formato DD/MM/YYYY (string)
        time: horário no formato HH:MM (string)
    """
    try:
        sheet = _open_sheet(WORKSHEET_AGENDA_NAME)

        durations = load_services_duration()
        total_minutes = durations.get(service, 30)
        slots = total_minutes // 30

        rows = sheet.get_all_values()

        rows_to_update = []

        for i in range(slots):
            hora = calcular_proximo_horario(time, i * 30)

            for idx, row in enumerate(rows):
                if len(row) >= 2 and row[0] == date and row[1] == hora:
                    if row[2].strip():
                        print(f"[AGENDA CONFLICT] {date} {hora}")
                        return False
                    rows_to_update.append(idx + 1)

        if not rows_to_update:
            print(f"❌ [AGENDA] Nenhuma linha encontrada para {date} {time}")
            return False

        updates = []
        for i, row_idx in enumerate(rows_to_update):
            cliente = name if i == 0 else f"RESERVADO ({name})"
            updates.append({
                "range": f"C{row_idx}:F{row_idx}",
                "values": [[cliente, service, phone, "Agendado"]]
            })

        sheet.batch_update(updates)
        print(f"✅ [AGENDA OK] {name} ({phone}) - {service} em {date} {time}")
        
        # Invalida cache de datas disponíveis
        get_available_dates_cached.cache_clear()
        
        return True
        
    except Exception as e:
        print(f"❌ [AGENDA ERROR] {phone} - {service} em {date} {time}: {e}")
        return False

# --------------------------------------------------
# CONTROLE DO ROBÔ
# --------------------------------------------------

def is_robot_muted(phone: str) -> bool:
    """
    Verifica se o robô está silenciado para um telefone.
    
    Args:
        phone: telefone do cliente
        
    Returns:
        True se MUTE_ROBO = TRUE, False caso contrário
    """
    try:
        sheet = _open_sheet(WORKSHEET_CONTROLE_NAME)
        rows = sheet.get_all_values()[1:]

        for row in rows:
            if len(row) >= 2 and row[0].strip() == phone:
                return row[1].strip().upper() == "TRUE"

        return False
        
    except Exception as e:
        print(f"❌ [MUTE CHECK ERROR] {phone}: {e}")
        # Em caso de erro, assume que NÃO está mutado (robô funciona)
        return False

def set_robot_mute(phone: str, mute: bool) -> bool:
    """
    Ativa ou desativa o MUTE do robô para um telefone específico.
    Quando MUTE = True, robô para de responder (atendimento humano).
    Quando MUTE = False, robô volta a funcionar.
    
    Args:
        phone: telefone do cliente
        mute: True para silenciar robô, False para reativar
        
    Returns:
        True se atualizou com sucesso, False se deu erro
    """
    try:
        sheet = _open_sheet(WORKSHEET_CONTROLE_NAME)
        rows = sheet.get_all_values()
        
        # Procura se o telefone já existe na planilha
        row_index = None
        for idx, row in enumerate(rows):
            if len(row) >= 1 and row[0].strip() == phone:
                row_index = idx + 1
                break
        
        mute_value = "TRUE" if mute else "FALSE"
        
        if row_index:
            # Atualiza linha existente (coluna B = MUTE_ROBO)
            sheet.update(f"B{row_index}", [[mute_value]])
            print(f"✅ [MUTE UPDATE] {phone} -> {mute_value}")
        else:
            # Adiciona nova linha
            sheet.append_row([phone, mute_value])
            print(f"✅ [MUTE NEW] {phone} -> {mute_value}")
        
        return True
        
    except Exception as e:
        print(f"❌ [MUTE ERROR] {phone}: {e}")
        return False

# --------------------------------------------------
# CANCELAMENTO DE AGENDAMENTO
# --------------------------------------------------

def cancel_appointment(phone: str) -> bool:
    """
    Cancela o agendamento mais recente de um telefone.
    
    Args:
        phone: telefone do cliente
        
    Returns:
        True se cancelou com sucesso, False se não encontrou
    """
    try:
        sheet = _open_sheet(WORKSHEET_AGENDA_NAME)
        rows = sheet.get_all_values()
        
        rows_to_clear = []
        
        # Procura todas as linhas com esse telefone
        for idx, row in enumerate(rows):
            if len(row) >= 5 and row[4] == phone and row[5] == "Agendado":
                rows_to_clear.append(idx + 1)
        
        if not rows_to_clear:
            print(f"[CANCELAMENTO] Nenhum agendamento encontrado para {phone}")
            return False
        
        # Limpa as células (Cliente, Serviço, Telefone, Status)
        updates = []
        for row_idx in rows_to_clear:
            updates.append({
                "range": f"C{row_idx}:F{row_idx}",
                "values": [["", "", "", ""]]
            })
        
        sheet.batch_update(updates)
        print(f"✅ [CANCELAMENTO OK] {phone} - {len(rows_to_clear)} slots liberados")
        
        # Invalida cache de datas disponíveis
        get_available_dates_cached.cache_clear()
        
        return True
        
    except Exception as e:
        print(f"❌ [CANCELAMENTO ERROR] {phone}: {e}")
        return False