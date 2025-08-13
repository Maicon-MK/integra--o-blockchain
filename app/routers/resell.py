from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas import ResellOfferCreate, ResellOfferOut, ProposePricePayload, EscrowOut
from app.auth import require_role
from app.database import get_db
from app.models import ResellOffer, Watch, Store, Evaluator, User, Escrow, OwnershipTransfer, Commission
from app.stellar import transfer_nft, simulate_payment_conversion
from app.routers.notifications import create_notification

router = APIRouter(prefix="/resell", tags=["resell"])

@router.post("/prepare", response_model=ResellOfferOut)
def prepare_resell(
    offer: ResellOfferCreate,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    # O seller_user_id é derivado do usuário logado
    offer.seller_user_id = int(current_user["sub"])
    
    # Verificar se o usuário é o dono do relógio
    watch = db.query(Watch).filter(
        Watch.id == offer.watch_id,
        Watch.current_owner_user_id == int(current_user["sub"])
    ).first()
    
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado ou você não é o proprietário")
    
    # Permitir revenda independente do status (comentado temporariamente)
    # if watch.status != "evaluated":
    #     raise HTTPException(status_code=400, detail="Relógio precisa ser avaliado antes da revenda")
    
    # NOVA REGRA: Verificar se o avaliador existe e está ativo
    evaluator = db.query(Evaluator).filter(Evaluator.id == offer.evaluator_id, Evaluator.active == True).first()
    if not evaluator:
        raise HTTPException(status_code=400, detail="Avaliador não encontrado ou inativo. Usuários só podem vender para avaliadores credenciados")
    
    # O relógio deve ir para a LOJA DO AVALIADOR (não loja especificada)
    evaluator_store = db.query(Store).filter(Store.id == evaluator.store_id).first()
    if not evaluator_store:
        raise HTTPException(status_code=400, detail="Avaliador deve estar associado a uma loja credenciada")
    
    # Forçar que a venda seja para a loja do avaliador
    offer.store_id = evaluator_store.id
    store = evaluator_store
    
    # Criar oferta de revenda
    db_offer = ResellOffer(**offer.dict())
    db.add(db_offer)
    db.commit()
    db.refresh(db_offer)
    
    # Notificar avaliador
    create_notification(
        db=db,
        user_id=evaluator.user_id,
        title="Nova Solicitação de Revenda",
        message=f"Solicitação de avaliação para revenda do relógio {watch.brand} {watch.model}",
        type="info"
    )
    
    return db_offer

@router.post("/{offer_id}/propose-price")
def propose_price(
    offer_id: int,
    payload: ProposePricePayload,
    current_user = Depends(require_role(["evaluator", "store"])),
    db: Session = Depends(get_db)
):
    # Buscar oferta e verificar se o usuário está autorizado
    offer = db.query(ResellOffer).filter(ResellOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")
    
    # Verificar se é avaliador ou loja da oferta
    if current_user["role"] == "evaluator":
        evaluator = db.query(Evaluator).filter(
            Evaluator.id == offer.evaluator_id,
            Evaluator.user_id == int(current_user["sub"])
        ).first()
        if not evaluator:
            raise HTTPException(status_code=403, detail="Não autorizado")
    elif current_user["role"] == "store":
        store = db.query(Store).filter(
            Store.id == offer.store_id,
            Store.user_id == int(current_user["sub"])
        ).first()
        if not store:
            raise HTTPException(status_code=403, detail="Não autorizado")
    else:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    if offer.status != "pending":
        raise HTTPException(status_code=400, detail="Oferta não está pendente")
    
    # Atualizar oferta com preço proposto
    offer.proposed_price_brl = payload.proposed_price_brl
    offer.status = "price_proposed"
    
    db.commit()
    
    # Notificar vendedor
    create_notification(
        db=db,
        user_id=offer.seller_user_id,
        title="Preço Proposto",
        message=f"Avaliador propôs R$ {payload.proposed_price_brl:,.2f} para revenda do seu relógio",
        type="info"
    )
    
    return {"offer_id": offer_id, "proposed_price_brl": payload.proposed_price_brl, "status": "price_proposed"}

@router.post("/{offer_id}/accept")
def accept_offer(
    offer_id: int,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    # Verificar se o usuário é o vendedor
    offer = db.query(ResellOffer).filter(
        ResellOffer.id == offer_id,
        ResellOffer.seller_user_id == int(current_user["sub"])
    ).first()
    
    if not offer:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")
    
    if offer.status != "price_proposed":
        raise HTTPException(status_code=400, detail="Oferta não tem preço proposto")
    
    # Aceitar oferta
    offer.status = "accepted"
    offer.final_price_brl = offer.proposed_price_brl
    
    db.commit()
    
    # Notificar loja
    store = db.query(Store).filter(Store.id == offer.store_id).first()
    create_notification(
        db=db,
        user_id=store.user_id,
        title="Oferta Aceita",
        message=f"Vendedor aceitou proposta de R$ {offer.final_price_brl:,.2f}",
        type="success"
    )
    
    return {"offer_id": offer_id, "status": "accepted", "final_price_brl": offer.final_price_brl}

@router.post("/{offer_id}/pay")
def pay_escrow(
    offer_id: int,
    current_user = Depends(require_role(["store"])),
    db: Session = Depends(get_db)
):
    """FUNÇÃO SIMPLIFICADA PARA DEBUG"""
    try:
        # Verificar se é a loja da oferta
        offer = db.query(ResellOffer).filter(ResellOffer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=404, detail="Oferta não encontrada")
        
        # Verificar loja
        store = db.query(Store).filter(
            Store.id == offer.store_id,
            Store.user_id == int(current_user["sub"])
        ).first()
        
        if not store:
            raise HTTPException(status_code=403, detail="Não autorizado")
            
        if offer.status != "accepted":
            raise HTTPException(status_code=400, detail=f"Status atual: {offer.status}, esperado: accepted")
        
        # Simular pagamento - apenas mudar status
        offer.status = "paid"
        db.commit()
        
        # Retornar resposta mock
        return {
            "id": 1,
            "offer_id": offer_id,
            "escrow_stellar_account": "TEMP_ACCOUNT",
            "escrow_secret_key": "TEMP_SECRET", 
            "amount_usdc": float(offer.final_price_brl),
            "depositor_stellar_key": "TEMP_KEY",
            "status": "holding"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.post("/{offer_id}/confirm-delivery")
def confirm_delivery(
    offer_id: int,
    current_user = Depends(require_role(["store"])),  # LOJA confirma recebimento
    db: Session = Depends(get_db)
):
    """LOJA confirma que recebeu o relógio físico e libera o pagamento"""
    try:
        # Verificar se é a LOJA da oferta
        offer = db.query(ResellOffer).filter(ResellOffer.id == offer_id).first()
        
        if not offer:
            raise HTTPException(status_code=404, detail="Oferta não encontrada")
        
        # Verificar se é a loja autorizada para esta oferta
        store = db.query(Store).filter(
            Store.id == offer.store_id,
            Store.user_id == int(current_user["sub"])
        ).first()
        
        if not store:
            raise HTTPException(status_code=403, detail="Apenas a loja compradora pode confirmar o recebimento")
        
        if offer.status != "paid":
            raise HTTPException(status_code=400, detail=f"Status atual: {offer.status}, esperado: paid")
        
        # SIMULAR: Loja confirma recebimento e libera pagamento
        offer.status = "completed"
        db.commit()
        
        # Notificar vendedor que o dinheiro foi liberado
        create_notification(
            db=db,
            user_id=offer.seller_user_id,
            title="💰 Pagamento Liberado!",
            message=f"A loja confirmou o recebimento do relógio. Você recebeu R$ {offer.final_price_brl:,.2f}",
            type="success"
        )
        
        return {
            "message": "✅ Loja confirmou recebimento! Dinheiro liberado para o vendedor",
            "offer_id": offer_id,
            "status": "completed",
            "amount_released": offer.final_price_brl,
            "seller_received": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.get("/", response_model=List[ResellOfferOut])
def list_resell_offers(
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    # Filtrar por papel do usuário
    if current_user["role"] == "admin":
        return db.query(ResellOffer).all()
    elif current_user["role"] == "store":
        store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
        if store:
            return db.query(ResellOffer).filter(ResellOffer.store_id == store.id).all()
    elif current_user["role"] == "evaluator":
        evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
        if evaluator:
            return db.query(ResellOffer).filter(ResellOffer.evaluator_id == evaluator.id).all()
    elif current_user["role"] == "user":
        return db.query(ResellOffer).filter(ResellOffer.seller_user_id == int(current_user["sub"])).all()
    
    return []

@router.get("/my-offers", response_model=List[ResellOfferOut])
def get_my_offers(
    current_user = Depends(require_role(["user", "store", "evaluator"])),
    db: Session = Depends(get_db)
):
    """Retorna as ofertas do usuário logado"""
    if current_user["role"] == "user":
        # Para usuários comuns, retorna ofertas onde ele é o vendedor
        offers = db.query(ResellOffer).filter(
            ResellOffer.seller_user_id == int(current_user["sub"])
        ).all()
    elif current_user["role"] == "store":
        # Para lojas, retorna ofertas destinadas à sua loja
        store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
        if not store:
            raise HTTPException(status_code=404, detail="Loja não encontrada")
        offers = db.query(ResellOffer).filter(
            ResellOffer.store_id == store.id
        ).all()
    elif current_user["role"] == "evaluator":
        # Para avaliadores, retorna ofertas destinadas ao seu perfil
        evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
        if not evaluator:
            raise HTTPException(status_code=404, detail="Avaliador não encontrado")
        offers = db.query(ResellOffer).filter(
            ResellOffer.evaluator_id == evaluator.id
        ).all()
    
    return offers

@router.get("/{offer_id}", response_model=ResellOfferOut)
def get_resell_offer(
    offer_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    offer = db.query(ResellOffer).filter(ResellOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Oferta não encontrada")
    
    # Verificar autorização
    if current_user["role"] != "admin":
        authorized = False
        if current_user["role"] == "user" and offer.seller_user_id == int(current_user["sub"]):
            authorized = True
        elif current_user["role"] == "store":
            store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
            if store and offer.store_id == store.id:
                authorized = True
        elif current_user["role"] == "evaluator":
            evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
            if evaluator and offer.evaluator_id == evaluator.id:
                authorized = True
        
        if not authorized:
            raise HTTPException(status_code=403, detail="Não autorizado")
    
    return offer
