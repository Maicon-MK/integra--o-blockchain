
import os
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from app.schemas import WatchCreate, WatchOut, MarketplaceListing, PurchasePayload, OwnershipTransferOut, StoreOut
from app.auth import require_role
from app.database import get_db
from app.models import Watch, User, OwnershipTransfer, Notification, Commission, Store
from app.stellar import create_nft_asset, transfer_nft, get_nft_history, simulate_payment_conversion
from app.routers.notifications import create_notification
from uuid import uuid4

router = APIRouter(prefix="/watches", tags=["watches"])

@router.post("/", response_model=WatchOut)
async def create_watch(
    watch: WatchCreate,
    current_user = Depends(require_role(["admin", "evaluator"])),
    db: Session = Depends(get_db)
):
    # Verificar se número de série já existe
    existing_watch = db.query(Watch).filter(Watch.serial_number == watch.serial_number).first()
    if existing_watch:
        raise HTTPException(status_code=400, detail="Número de série já cadastrado")
    
    # Determinar status inicial baseado no tipo de usuário
    user_role = current_user.get("role", "user")
    if user_role == "admin":
        initial_status = "registered"
    elif user_role == "evaluator":
        # Avaliadores criam relógios já avaliados e prontos para venda
        initial_status = "for_sale"
    else:
        initial_status = "registered"
    
    # Para avaliadores, verificar se estão vinculados a uma loja
    evaluator_store_id = None
    owner_user_id = int(current_user["sub"])
    
    if user_role == "evaluator":
        from app.models import Evaluator, Store
        evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
        if evaluator and evaluator.store_id:
            evaluator_store_id = evaluator.store_id
            # Para relógios criados por avaliadores, o dono deve ser a loja
            store = db.query(Store).filter(Store.id == evaluator.store_id).first()
            if store:
                owner_user_id = store.user_id
    
    # Para lojas, buscar o store_id
    store_id = None
    if user_role == "store":
        store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
        if store:
            store_id = store.id
    
    # Criar relógio no banco
    db_watch = Watch(
        serial_number=watch.serial_number,
        brand=watch.brand,
        model=watch.model,
        year=watch.year,
        condition=watch.condition,
        description=watch.description,
        purchase_price_brl=watch.purchase_price_brl,
        current_value_brl=watch.current_value_brl,
        current_owner_user_id=owner_user_id,
        status=initial_status,
        store_id=evaluator_store_id  # Associar à loja se avaliador vinculado
    )
    
    db.add(db_watch)
    db.commit()
    db.refresh(db_watch)
    
    # APENAS REGISTRAR - não tokenizar automaticamente
    # Notificar usuário sobre registro
    notification_message = f"Relógio {watch.brand} {watch.model} registrado com sucesso"
    if user_role == "evaluator":
        notification_message = f"Relógio {watch.brand} {watch.model} avaliado. Use /watches/{db_watch.id}/tokenize para tokenizar"
    
    create_notification(
        db=db,
        user_id=int(current_user["sub"]),
        title="Relógio Registrado",
        message=notification_message,
        type="info"
    )
    
    return db_watch

@router.post("/{watch_id}/tokenize", response_model=WatchOut)
async def tokenize_watch(
    watch_id: int,
    current_user = Depends(require_role(["evaluator"])),
    db: Session = Depends(get_db)
):
    """Avaliador tokeniza relógio após avaliação"""
    
    # Verificar se relógio existe
    watch = db.query(Watch).filter(Watch.id == watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado")
    
    # Verificar se o avaliador tem permissão
    evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
    if not evaluator:
        raise HTTPException(status_code=403, detail="Usuário não é um avaliador credenciado")
    
    # Verificar se relógio já foi tokenizado
    if watch.status == "tokenized":
        raise HTTPException(status_code=400, detail="Relógio já foi tokenizado")
    
    # Verificar se relógio foi avaliado
    if watch.status not in ["evaluated", "registered"]:
        raise HTTPException(status_code=400, detail="Relógio deve estar avaliado para ser tokenizado")
    
    # Buscar usuário para obter chave pública Stellar
    user = db.query(User).filter(User.id == int(current_user["sub"])).first()
    
    # Criar chave Stellar se não existir
    if user and not user.stellar_public_key:
        from app.stellar import MARKETPLACE_KEYPAIR_PUBLIC
        user.stellar_public_key = MARKETPLACE_KEYPAIR_PUBLIC
        db.commit()
    
    # Tokenizar na Stellar
    try:
        nft_result = create_nft_asset(
            watch_id=watch.id,
            brand=watch.brand,
            model=watch.model,
            serial_number=watch.serial_number,
            receiver_public=user.stellar_public_key
        )
        
        if nft_result["status"] == "success":
            # Atualizar relógio com dados NFT
            watch.nft_code = nft_result["asset_code"]
            watch.nft_issuer = nft_result["issuer"]
            watch.blockchain_address = nft_result.get("blockchain_address", nft_result["issuer"])
            watch.status = "tokenized"
            
            # Calcular comissões e fees simulados
            tokenization_fee = watch.current_value_brl * 0.001  # 0.1% fee
            stellar_network_fee = 0.00001  # Fee da rede Stellar
            
            db.commit()
            db.refresh(watch)
            
            # Notificar sobre tokenização
            create_notification(
                db=db,
                user_id=int(current_user["sub"]),
                title="Relógio Tokenizado",
                message=f"NFT criado: {watch.brand} {watch.model} tokenizado na Stellar blockchain. Fee: R$ {tokenization_fee:.2f}",
                type="success"
            )
            
            return watch
        else:
            # Falha na tokenização
            watch.status = "nft_error"
            db.commit()
            raise HTTPException(status_code=500, detail="Falha na tokenização NFT")
            
    except Exception as e:
        # Erro na tokenização
        watch.status = "nft_failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erro na tokenização: {str(e)}")

@router.post("/upload", response_model=WatchOut)
async def create_watch_with_image(
    serial_number: str = Form(...),
    brand: str = Form(...),
    model: str = Form(...),
    description: str = Form(...),
    current_owner_user_id: int = Form(...),
    image: UploadFile = File(...),
    current_user = Depends(require_role(["admin", "user"])),
    db: Session = Depends(get_db)
):
    # Verificar se o usuário é o dono ou admin
    if current_user["role"] != "admin" and int(current_user["sub"]) != current_owner_user_id:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    # Verificar se número de série já existe
    existing_watch = db.query(Watch).filter(Watch.serial_number == serial_number).first()
    if existing_watch:
        raise HTTPException(status_code=400, detail="Número de série já cadastrado")
    
    # Salvar imagem
    uploads_dir = os.path.join(os.getcwd(), "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    ext = os.path.splitext(image.filename)[1] if image.filename else ".jpg"
    filename = f"watch_{uuid4().hex}{ext}"
    file_path = os.path.join(uploads_dir, filename)
    
    with open(file_path, "wb") as f:
        f.write(await image.read())
    
    image_url = f"/static/uploads/{filename}"
    
    # Criar relógio no banco
    db_watch = Watch(
        serial_number=serial_number,
        brand=brand,
        model=model,
        description=description,
        current_owner_user_id=current_owner_user_id,
        image_url=image_url,
        status="registered"
    )
    
    db.add(db_watch)
    db.commit()
    db.refresh(db_watch)
    
    # Buscar usuário para obter chave pública Stellar
    user = db.query(User).filter(User.id == current_owner_user_id).first()
    
    # Criar NFT na Stellar
    nft_result = create_nft_asset(
        watch_id=db_watch.id,
        brand=brand,
        model=model,
        serial_number=serial_number,
        receiver_public=user.stellar_public_key
    )
    
    if nft_result["status"] == "success":
        db_watch.nft_code = nft_result["asset_code"]
        db_watch.nft_issuer = nft_result["issuer"]
        db.commit()
        
        # Notificar usuário
        create_notification(
            db=db,
            user_id=current_owner_user_id,
            title="Relógio Cadastrado",
            message=f"Seu relógio {brand} {model} foi cadastrado e tokenizado como NFT",
            type="success"
        )
    
    return db_watch

@router.get("/", response_model=List[WatchOut])
def list_watches(
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    return db.query(Watch).all()

@router.get("/available-for-sale", response_model=List[WatchOut])
def list_watches_for_sale(
    current_user = Depends(require_role(["store", "admin"])),
    db: Session = Depends(get_db)
):
    """Lista relógios avaliados e tokenizados, prontos para venda por lojas"""
    user_role = current_user.get("role", "user")
    
    if user_role == "store":
        # Para lojas, mostrar apenas relógios da própria loja
        from app.models import Store
        store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
        if not store:
            raise HTTPException(status_code=404, detail="Loja não encontrada")
        
        return db.query(Watch).filter(
            Watch.store_id == store.id,
            Watch.status.in_(["tokenized", "evaluated"])
        ).all()
    else:
        # Para admin, mostrar todos os relógios prontos para venda
        return db.query(Watch).filter(
            Watch.status.in_(["tokenized", "evaluated"])
        ).all()

@router.get("/my", response_model=List[WatchOut])
def my_watches(
    current_user = Depends(require_role(["user", "store"])),
    db: Session = Depends(get_db)
):
    return db.query(Watch).filter(Watch.current_owner_user_id == int(current_user["sub"])).all()

@router.get("/marketplace", response_model=List[WatchOut])
def marketplace_watches(
    current_user = Depends(require_role(["user", "admin", "store", "evaluator"])),
    db: Session = Depends(get_db)
):
    """Lista relógios disponíveis para compra no marketplace"""
    return db.query(Watch).filter(
        Watch.status == "for_sale"
    ).all()

@router.get("/{watch_id}", response_model=WatchOut)
def get_watch(
    watch_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    watch = db.query(Watch).filter(Watch.id == watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado")
    
    return watch

@router.post("/{watch_id}/list-for-sale")
def list_for_sale(
    watch_id: int,
    listing: MarketplaceListing,
    current_user = Depends(require_role(["store"])),  # Apenas lojas podem listar para venda direta
    db: Session = Depends(get_db)
):
    # Verificar se o usuário é uma loja e é dona do relógio
    user = db.query(User).filter(User.id == int(current_user["sub"])).first()
    if user.role != "store":
        raise HTTPException(status_code=403, detail="Apenas lojas podem listar relógios para venda direta")
    
    watch = db.query(Watch).filter(
        Watch.id == watch_id,
        Watch.current_owner_user_id == int(current_user["sub"])
    ).first()
    
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado ou você não é o proprietário")
    
    # Atualizar status para venda (apenas lojas podem fazer venda direta)
    watch.status = "for_sale"
    db.commit()
    
    return {"message": "Relógio listado para venda pela loja", "price_brl": listing.price_brl}

@router.post("/{watch_id}/purchase")
def purchase_watch(
    watch_id: int,
    purchase: PurchasePayload,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    # Buscar relógio
    watch = db.query(Watch).filter(Watch.id == watch_id, Watch.status == "for_sale").first()
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não disponível para venda")
    
    # Verificar se o relógio pertence a uma LOJA (não a usuário comum)
    owner = db.query(User).filter(User.id == watch.current_owner_user_id).first()
    if not owner or owner.role != "store":
        raise HTTPException(status_code=400, detail="Usuários só podem comprar relógios de lojas credenciadas")
    
    # Verificar se não é o próprio dono
    if watch.current_owner_user_id == int(current_user["sub"]):
        raise HTTPException(status_code=400, detail="Você não pode comprar seu próprio relógio")
    
    # Simular preço (seria obtido da tabela de listings)
    price_brl = watch.current_value_brl or 50000.0  # Usar valor atual do relógio
    
    # Processar pagamento com validações específicas
    try:
        installments = purchase.installments or 1
        
        # Validação específica por método de pagamento
        if purchase.payment_method == "credit_card":
            if not all([purchase.card_number, purchase.card_name, purchase.card_expiry, purchase.card_cvv]):
                raise HTTPException(status_code=400, detail="Dados do cartão incompletos")
            if not purchase.cpf:
                raise HTTPException(status_code=400, detail="CPF é obrigatório para pagamento com cartão")
        elif purchase.payment_method == "pix":
            if not purchase.cpf:
                raise HTTPException(status_code=400, detail="CPF é obrigatório para PIX")
        
        payment_result = simulate_payment_conversion(price_brl, purchase.payment_method, installments)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na simulação de pagamento: {str(e)}")
    
    if payment_result["status"] == "success":
        # Buscar comprador
        buyer = db.query(User).filter(User.id == int(current_user["sub"])).first()
        seller = db.query(User).filter(User.id == watch.current_owner_user_id).first()
        
        if not buyer or not seller:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        # Transferir NFT (simulado)
        try:
            transfer_result = transfer_nft(
                asset_code=watch.nft_code or f"NFT{watch.id}",
                from_secret=seller.stellar_secret or "SIMULATED_SECRET",
                to_public=buyer.stellar_public_key or "SIMULATED_PUBLIC"
            )
        except Exception as e:
            transfer_result = {
                "status": "success",
                "tx_hash": f"simulated_transfer_{watch.id}_{int(current_user['sub'])}"
            }
        
        if transfer_result["status"] == "success":
            # Criar registro de transferência
            transfer = OwnershipTransfer(
                watch_id=watch.id,
                from_user_id=watch.current_owner_user_id,
                to_user_id=int(current_user["sub"]),
                stellar_tx_hash=transfer_result["tx_hash"],
                type="sale",
                price_brl=price_brl,
                admin_fee_brl=price_brl * 0.03  # 3% fee
            )
            db.add(transfer)
            
            # Atualizar proprietário
            watch.current_owner_user_id = int(current_user["sub"])
            watch.status = "sold"
            
            # Criar comissão para admin
            commission = Commission(
                transaction_id=transfer.id,
                transaction_type="sale",
                recipient_user_id=1,  # Admin user
                amount_brl=price_brl * 0.03,
                description=f"Comissão da venda do relógio {watch.brand} {watch.model}"
            )
            db.add(commission)
            
            db.commit()
            
            # Notificar ambas as partes
            create_notification(
                db=db,
                user_id=seller.id,
                title="Relógio Vendido",
                message=f"Seu relógio {watch.brand} {watch.model} foi vendido por R$ {price_brl:,.2f}",
                type="success"
            )
            
            create_notification(
                db=db,
                user_id=buyer.id,
                title="Compra Realizada",
                message=f"Você comprou o relógio {watch.brand} {watch.model} por R$ {price_brl:,.2f}",
                type="success"
            )
            
            return {
                "message": "Compra realizada com sucesso",
                "transfer_id": transfer.id,
                "payment_hash": payment_result["tx_hash"],
                "nft_transfer_hash": transfer_result["tx_hash"],
                "price_brl": price_brl,
                "payment_method": purchase.payment_method,
                "installments": installments,
                "payment_fees": payment_result.get("fees", {}),
                "buyer": {
                    "id": buyer.id,
                    "name": buyer.full_name
                },
                "seller": {
                    "id": seller.id,
                    "name": seller.full_name
                },
                "watch": {
                    "id": watch.id,
                    "brand": watch.brand,
                    "model": watch.model
                }
            }
    
    raise HTTPException(status_code=400, detail="Falha no pagamento")

@router.get("/{watch_id}/history", response_model=List[OwnershipTransferOut])
def watch_history(
    watch_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    transfers = db.query(OwnershipTransfer).filter(OwnershipTransfer.watch_id == watch_id).all()
    return transfers

@router.get("/{watch_id}/blockchain-history")
def watch_blockchain_history(
    watch_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    watch = db.query(Watch).filter(Watch.id == watch_id).first()
    if not watch or not watch.nft_code:
        raise HTTPException(status_code=404, detail="NFT não encontrado")
    
    return get_nft_history(watch.nft_code)

@router.post("/{watch_id}/sell")
def put_watch_for_sale(
    watch_id: int,
    sale_data: dict,
    current_user = Depends(require_role(["store", "admin"])),
    db: Session = Depends(get_db)
):
    """Loja coloca relógio à venda"""
    user_role = current_user.get("role", "user")
    
    # Verificar se é uma loja
    if user_role == "store":
        from app.models import Store
        store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
        if not store:
            raise HTTPException(status_code=404, detail="Loja não encontrada")
        
        # Verificar se o relógio pertence à loja
        watch = db.query(Watch).filter(
            Watch.id == watch_id,
            Watch.store_id == store.id
        ).first()
    else:
        # Admin pode colocar qualquer relógio à venda
        watch = db.query(Watch).filter(Watch.id == watch_id).first()
    
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado ou não autorizado")
    
    # Atualizar relógio para venda
    watch.status = "for_sale"
    watch.price_brl = sale_data.get("price_brl", watch.current_value_brl)
    
    db.commit()
    db.refresh(watch)
    
    return {
        "status": "success",
        "message": "Relógio colocado à venda",
        "watch_id": watch.id,
        "price_brl": watch.price_brl
    }

@router.post("/{watch_id}/purchase")
def purchase_watch(
    watch_id: int,
    purchase_data: dict,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    """Cliente compra relógio"""
    watch = db.query(Watch).filter(
        Watch.id == watch_id,
        Watch.status == "for_sale"
    ).first()
    
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado ou não disponível")
    
    # Criar escrow para a compra
    from app.models import Escrow
    escrow = Escrow(
        watch_id=watch_id,
        buyer_id=int(current_user["sub"]),
        seller_id=watch.current_owner_user_id,
        amount_brl=watch.price_brl,
        status="pending"
    )
    
    db.add(escrow)
    db.commit()
    db.refresh(escrow)
    
    # Atualizar status do relógio
    watch.status = "sold"
    db.commit()
    
    return {
        "status": "success",
        "message": "Compra iniciada",
        "escrow_id": escrow.id,
        "total_paid_brl": watch.price_brl,
        "watch_id": watch_id
    }

@router.get("/store/info")
def get_store_info(
    current_user = Depends(require_role(["store"])),
    db: Session = Depends(get_db)
):
    """Buscar informações da loja do usuário logado"""
    # Buscar a loja do usuário
    store = db.query(Store).filter(Store.user_id == int(current_user["sub"])).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    
    # Buscar usuário para pegar saldo
    user = db.query(User).filter(User.id == int(current_user["sub"])).first()
    
    # Estatísticas da loja
    total_watches_store = db.query(Watch).filter(Watch.store_id == store.id).count()
    watches_for_sale = db.query(Watch).filter(
        Watch.store_id == store.id,
        Watch.status == "for_sale"
    ).count()
    sold_watches = db.query(Watch).filter(
        Watch.store_id == store.id,
        Watch.status == "sold"
    ).count()
    
    # Calcular receita total simulada
    estimated_revenue = sold_watches * 95000.0 * store.commission_rate
    
    return {
        "store_info": {
            "id": store.id,
            "name": store.name,
            "credentialed": store.credentialed,
            "commission_rate": store.commission_rate,
            "created_at": store.created_at
        },
        "user_balance": {
            "balance_brl": user.balance_brl,
            "balance_xlm": user.balance_xlm
        },
        "statistics": {
            "total_watches": total_watches_store,
            "watches_for_sale": watches_for_sale,
            "sold_watches": sold_watches,
            "estimated_revenue": estimated_revenue
        },
        "stellar_info": {
            "public_key": user.stellar_public_key
        }
    }

@router.get("/store/sales-history")
def store_sales_history(
    current_user = Depends(require_role(["store"])),
    db: Session = Depends(get_db)
):
    """Histórico detalhado de vendas da loja"""
    user_id = int(current_user["sub"])
    
    # Buscar a loja do usuário
    store = db.query(Store).filter(Store.user_id == user_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    
    # Buscar relógios vendidos da loja com detalhes
    sold_watches = db.query(Watch).filter(
        Watch.store_id == store.id,
        Watch.status == "sold"
    ).all()
    
    # Buscar transferências de propriedade para obter datas de venda
    sales_details = []
    total_revenue = 0.0
    
    for watch in sold_watches:
        # Buscar última transferência (venda)
        last_transfer = db.query(OwnershipTransfer).filter(
            OwnershipTransfer.watch_id == watch.id
        ).order_by(OwnershipTransfer.created_at.desc()).first()
        
        sale_price = watch.current_value_brl
        commission = sale_price * store.commission_rate
        total_revenue += commission
        
        sales_details.append({
            "watch_id": watch.id,
            "serial_number": watch.serial_number,
            "brand": watch.brand,
            "model": watch.model,
            "sale_price_brl": sale_price,
            "commission_brl": commission,
            "sale_date": last_transfer.created_at if last_transfer else watch.created_at,
            "buyer_id": last_transfer.new_owner_user_id if last_transfer else None
        })
    
    return {
        "store": {
            "id": store.id,
            "name": store.name,
            "commission_rate": store.commission_rate
        },
        "summary": {
            "total_sales": len(sold_watches),
            "total_revenue_brl": total_revenue,
            "average_sale_price": sum(w.current_value_brl for w in sold_watches) / len(sold_watches) if sold_watches else 0,
            "average_commission": total_revenue / len(sold_watches) if sold_watches else 0
        },
        "sales": sales_details
    }
