"""Limpa histórico de chat com respostas alucinadas + reinicia fresh."""
import sys, os
# Adicionar o diretório backend ao path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, ChatMessage  # type: ignore

db = SessionLocal()
try:
    count = db.query(ChatMessage).count()
    if count > 0:
        db.query(ChatMessage).delete()
        db.commit()
        print(f"✅ {count} mensagens de chat antigas removidas (incluindo alucinações)")
    else:
        print("ℹ️ Histórico já está limpo")
finally:
    db.close()
