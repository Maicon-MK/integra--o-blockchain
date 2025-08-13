# ENDPOINTS PARA CONTRATOS STELLAR
# Rotas para Registro de Relógios, Escrow e NFT

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from ..database import get_db
from ..routers.auth import get_current_user
from ..models import User, Watch, ResellOffer
from ..stellar_contracts import stellar_contracts

router = APIRouter(prefix="/stellar", tags=["Contratos Stellar"])

# ========================= SCHEMAS =========================

class EvaluationReportCreate(BaseModel):
    """Schema para criação de laudo de avaliação"""
    serial: str = Field(..., description="Número de série do relógio")
    brand: str = Field(..., description="Marca do relógio")
    model: str = Field(..., description="Modelo do relógio")
    condition: str = Field(..., description="Condição: excellent, good, fair, poor")
    authenticity: str = Field(..., description="Autenticidade: authentic, replica, unknown")
    evaluator_id: int = Field(..., description="ID do avaliador")
    estimated_value_brl: float = Field(..., description="Valor estimado em BRL")
    notes: str = Field("", description="Observações do avaliador")
    photos_hashes: List[str] = Field(..., description="Hashes das fotos")
    pdf_hash: str = Field(..., description="Hash do PDF do laudo")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class WatchRegistrationResponse(BaseModel):
    """Resposta do registro de relógio"""
    watch_id: int
    serial: str
    nft_code: str
    nft_issuer: str
    laudo_hash: str
    status: str
    message: str

class EscrowCreateRequest(BaseModel):
    """Requisição para criar escrow"""
    offer_id: int = Field(..., description="ID da oferta de revenda")
    amount_usdc: float = Field(..., description="Valor em USDC para escrow")

class EscrowResponse(BaseModel):
    """Resposta da criação de escrow"""
    escrow_id: int
    escrow_account: str
    amount_usdc: str
    status: str
    message: str

class NFTTransferRequest(BaseModel):
    """Requisição para transferir NFT"""
    watch_id: int = Field(..., description="ID do relógio")
    to_user_id: int = Field(..., description="ID do usuário destinatário")

class NFTTransferResponse(BaseModel):
    """Resposta da transferência de NFT"""
    watch_id: int
    nft_token_id: str
    from_user: str
    to_user: str
    transaction_hash: str
    message: str

# ========================= 1. ENDPOINTS DE REGISTRO DE RELÓGIOS =========================

@router.post("/watches/register", response_model=WatchRegistrationResponse)
async def register_watch_with_nft(
    evaluation_data: EvaluationReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra um relógio com laudo e cria NFT correspondente
    """
    try:
        # Verificar se usuário tem permissão (admin ou store)
        if current_user.role not in ["admin", "store"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas admins e lojas podem registrar relógios"
            )
        
        # Verificar se usuário tem chave Stellar
        if not current_user.stellar_public_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário deve ter chave Stellar configurada"
            )
        
        # Converter para dict
        evaluation_dict = evaluation_data.dict()
        
        # Registrar relógio com NFT
        registration_contract = stellar_contracts.get_watch_registration()
        result = registration_contract.register_watch(evaluation_dict, current_user.id)
        
        return WatchRegistrationResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.get("/watches/{watch_id}/nft-status")
async def get_watch_nft_status(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica status do NFT de um relógio
    """
    try:
        watch = db.query(Watch).filter(Watch.id == watch_id).first()
        if not watch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Relógio não encontrado"
            )
        
        # Verificar autenticidade na blockchain
        nft_contract = stellar_contracts.get_nft()
        verification = nft_contract.verify_nft_authenticity(watch_id)
        
        return verification
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na verificação: {str(e)}"
        )

# ========================= 2. ENDPOINTS DE ESCROW =========================

@router.post("/escrow/create", response_model=EscrowResponse)
async def create_escrow(
    escrow_request: EscrowCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cria contrato de escrow para uma oferta de revenda
    """
    try:
        # Verificar se usuário tem permissão (store)
        if current_user.role != "store":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas lojas podem criar escrow"
            )
        
        # Verificar se oferta existe
        offer = db.query(ResellOffer).filter(ResellOffer.id == escrow_request.offer_id).first()
        if not offer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Oferta de revenda não encontrada"
            )
        
        # Verificar se usuário tem chave Stellar
        if not current_user.stellar_public_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuário deve ter chave Stellar configurada"
            )
        
        # Criar escrow
        escrow_contract = stellar_contracts.get_escrow()
        result = escrow_contract.deposit_to_escrow(
            escrow_request.offer_id,
            escrow_request.amount_usdc,
            current_user.stellar_public_key
        )
        
        return EscrowResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar escrow: {str(e)}"
        )

@router.post("/escrow/{escrow_id}/confirm-delivery")
async def confirm_delivery(
    escrow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirma entrega/recebimento para liberação do escrow
    """
    try:
        # Determinar tipo de confirmador baseado no role
        if current_user.role == "user":
            confirmer_type = "seller"
        elif current_user.role == "evaluator":
            confirmer_type = "evaluator"
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas vendedores e avaliadores podem confirmar entrega"
            )
        
        # Confirmar entrega
        escrow_contract = stellar_contracts.get_escrow()
        result = escrow_contract.confirm_delivery(escrow_id, confirmer_type)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na confirmação: {str(e)}"
        )

@router.get("/escrow/{escrow_id}/status")
async def get_escrow_status(
    escrow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Consulta status de um escrow
    """
    try:
        from ..models import Escrow
        
        escrow = db.query(Escrow).filter(Escrow.id == escrow_id).first()
        if not escrow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escrow não encontrado"
            )
        
        return {
            "escrow_id": escrow.id,
            "offer_id": escrow.offer_id,
            "amount_usdc": str(escrow.amount_usdc),
            "status": escrow.status,
            "seller_confirmed": escrow.seller_confirmed,
            "evaluator_confirmed": escrow.evaluator_confirmed,
            "created_at": escrow.created_at.isoformat(),
            "released_at": escrow.released_at.isoformat() if escrow.released_at else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar escrow: {str(e)}"
        )

# ========================= 3. ENDPOINTS DE NFT =========================

@router.post("/nft/transfer", response_model=NFTTransferResponse)
async def transfer_nft(
    transfer_request: NFTTransferRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transfere NFT de relógio entre usuários
    """
    try:
        # Verificar se usuário é dono do relógio
        watch = db.query(Watch).filter(Watch.id == transfer_request.watch_id).first()
        if not watch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Relógio não encontrado"
            )
        
        if watch.current_owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas o dono pode transferir o NFT"
            )
        
        # Verificar usuário destinatário
        to_user = db.query(User).filter(User.id == transfer_request.to_user_id).first()
        if not to_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário destinatário não encontrado"
            )
        
        # Executar transferência
        nft_contract = stellar_contracts.get_nft()
        result = nft_contract.transfer_nft(
            transfer_request.watch_id,
            current_user.id,
            transfer_request.to_user_id
        )
        
        return NFTTransferResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na transferência: {str(e)}"
        )

@router.get("/nft/{watch_id}/history")
async def get_nft_ownership_history(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna histórico de propriedade do NFT
    """
    try:
        # Verificar se relógio existe
        watch = db.query(Watch).filter(Watch.id == watch_id).first()
        if not watch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Relógio não encontrado"
            )
        
        # Obter histórico
        nft_contract = stellar_contracts.get_nft()
        history = nft_contract.get_nft_ownership_history(watch_id)
        
        return {
            "watch_id": watch_id,
            "serial": watch.serial or watch.serial_number,
            "brand": watch.brand,
            "model": watch.model,
            "ownership_history": history
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter histórico: {str(e)}"
        )

@router.get("/nft/{watch_id}/verify")
async def verify_nft_authenticity(
    watch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica autenticidade do NFT na blockchain
    """
    try:
        nft_contract = stellar_contracts.get_nft()
        verification = nft_contract.verify_nft_authenticity(watch_id)
        
        return verification
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na verificação: {str(e)}"
        )

# ========================= 4. ENDPOINTS ADMINISTRATIVOS =========================

@router.get("/admin/stellar-transactions")
async def get_stellar_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    """
    Lista transações Stellar (apenas admin)
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas admins podem ver transações Stellar"
            )
        
        from ..models import StellarTransaction
        
        transactions = (
            db.query(StellarTransaction)
            .order_by(StellarTransaction.created_at.desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "id": tx.id,
                "transaction_hash": tx.transaction_hash,
                "transaction_type": tx.transaction_type,
                "from_account": tx.from_account,
                "to_account": tx.to_account,
                "asset_code": tx.asset_code,
                "amount": tx.amount,
                "status": tx.status,
                "created_at": tx.created_at.isoformat()
            }
            for tx in transactions
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar transações: {str(e)}"
        )

@router.get("/admin/escrows")
async def get_all_escrows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista todos os escrows (apenas admin)
    """
    try:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas admins podem ver escrows"
            )
        
        from ..models import Escrow
        
        escrows = db.query(Escrow).all()
        
        return [
            {
                "id": escrow.id,
                "offer_id": escrow.offer_id,
                "amount_usdc": str(escrow.amount_usdc),
                "status": escrow.status,
                "seller_confirmed": escrow.seller_confirmed,
                "evaluator_confirmed": escrow.evaluator_confirmed,
                "created_at": escrow.created_at.isoformat(),
                "released_at": escrow.released_at.isoformat() if escrow.released_at else None
            }
            for escrow in escrows
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar escrows: {str(e)}"
        )
