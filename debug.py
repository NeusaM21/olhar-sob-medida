import sys
import os

# Adiciona o diretório atual ao Python para ele achar o backend
sys.path.append(os.getcwd())

from backend.core.utils import extract_datetime_from_text

# A frase exata que você mandou no Postman
mensagem = "Quero marcar uma sobrancelha dia 23/11 às 14h"

print("\n" + "="*40)
print("🕵️‍♂️ INICIANDO INVESTIGAÇÃO DE DATAS")
print("="*40)
print(f"FRASE ANALISADA: '{mensagem}'")

try:
    data, hora = extract_datetime_from_text(mensagem)
    print("-" * 40)
    print(f"🔍 RESULTADO: Data='{data}' | Hora='{hora}'")
    print("-" * 40)
    
    if data and hora:
        print("✅ O código ENTENDEU a data!")
    else:
        print("❌ O código NÃO entendeu (retornou None).")
        
except Exception as e:
    print(f"💥 ERRO CRÍTICO NO CÓDIGO: {e}")

print("="*40 + "\n")