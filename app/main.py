from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.routers import auth, watches, resell, admin, notifications, payments, evaluations, stellar_contracts, stellar, stellar_mvp
from app.database import engine, get_db
from app.models import Base, User, Store, Watch
from app.auth import require_role
import os

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)
   
app = FastAPI(
    title="Marketplace de Relógios com NFT + Escrow na Stellar",
    description="API para marketplace de relógios de luxo com tokenização NFT e sistema de escrow",
    version="2.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inclui rotas principais
app.include_router(auth.router)
app.include_router(watches.router)
app.include_router(resell.router)
app.include_router(admin.router)
app.include_router(notifications.router)
app.include_router(payments.router)
app.include_router(evaluations.router)
app.include_router(stellar_mvp.router)  # Endpoints Stellar MVP (sempre funcionam) - PRIMEIRO
app.include_router(stellar_contracts.router)  # Contratos Stellar
app.include_router(stellar.router)  # Endpoints Stellar básicos
app.include_router(stellar_mvp.router)  # Endpoints Stellar MVP (sempre funcionam)

@app.get("/")
def root():
    return {
        "message": "Marketplace de Relógios com NFT + Escrow na Stellar",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "Autenticação JWT",
            "Pagamentos PIX e Cartão",
            "Conversão BRL/USDC",
            "Gestão de Relógios",
            "Sistema de Revenda",
            "Avaliações",
            "Notificações",
            "Contratos Stellar",
            "NFT Tokenização",
            "Escrow Automático",
            "Blockchain Verification"
        ],
        "stellar_contracts": {
            "watch_registration": "/stellar/watches/register",
            "escrow_management": "/stellar/escrow/create",
            "nft_transfer": "/stellar/nft/transfer",
            "verification": "/stellar/nft/{watch_id}/verify"
        }
    }

@app.get("/health")
def health():
    from datetime import datetime
    return {
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected"
    }

# Endpoints de DEBUG temporários
@app.get("/debug/profile")
def debug_profile(current_user = Depends(require_role(["admin", "store", "evaluator", "user"])), db: Session = Depends(get_db)):
    """Debug do perfil do usuário"""
    try:
        user = db.query(User).filter(User.id == int(current_user["sub"])).first()
        if not user:
            return {"error": "Usuário não encontrado"}
        
        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "balance_brl": getattr(user, 'balance_brl', 0.0),
            "balance_xlm": getattr(user, 'balance_xlm', 0.0),
            "has_balance_fields": hasattr(user, 'balance_brl')
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

@app.get("/debug/dashboard")
def debug_dashboard(current_user = Depends(require_role(["admin"])), db: Session = Depends(get_db)):
    """Debug do dashboard admin"""
    try:
        total_users = db.query(User).count()
        total_stores = db.query(Store).count()
        total_watches = db.query(Watch).count()
        
        return {
            "total_users": total_users,
            "total_stores": total_stores, 
            "total_watches": total_watches,
            "current_user": current_user,
            "status": "working"
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}
