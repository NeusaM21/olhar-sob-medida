from backend.integrations.sheets import book_appointment
from datetime import datetime

def executar_teste():
    print("🚀 A iniciar teste de agendamento...")
    
    # Dados do teste
    data_teste = "20/12/2025"
    hora_teste = "10:00"
    cliente = "Teste Neusa Magalhães"
    servico = "Limpeza de Pele" # Este serviço deve ocupar 90min (3 linhas)
    telefone = "11999999999"

    print(f"📅 A tentar agendar {servico} para {data_teste} às {hora_teste}...")
    
    sucesso = book_appointment(data_teste, hora_teste, cliente, servico, telefone)

    if sucesso:
        print("✅ SUCESSO! Verifica a tua folha 'Agenda'.")
        print("Deverás ver:")
        print(f"1. {hora_teste} - {cliente}")
        print(f"2. 10:30 - RESERVADO ({cliente})")
        print(f"3. 11:00 - RESERVADO ({cliente})")
    else:
        print("❌ FALHA: O horário pode estar ocupado ou não foi encontrado na grade.")

if __name__ == "__main__":
    executar_teste()