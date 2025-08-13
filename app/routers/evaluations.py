from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas import EvaluationCreate, EvaluationOut
from app.auth import require_role
from app.database import get_db
from app.models import Evaluation, Watch, Evaluator, Notification, Commission, Store, User
from app.routers.notifications import create_notification

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

@router.get("/evaluators")
def get_available_evaluators(
    current_user = Depends(require_role(["user", "store", "admin"])),
    db: Session = Depends(get_db)
):
    """Listar avaliadores disponíveis para solicitação de avaliação"""
    evaluators = db.query(Evaluator).filter(Evaluator.active == True).all()
    
    return [
        {
            "id": evaluator.id,
            "name": evaluator.name,
            "specialty": evaluator.specialty,
            "evaluation_fee": evaluator.evaluation_fee,
            "phone": evaluator.phone,
            "email": evaluator.email
        }
        for evaluator in evaluators
    ]

@router.post("/request", response_model=EvaluationOut)
def request_evaluation(
    evaluation: EvaluationCreate,
    current_user = Depends(require_role(["user", "store", "admin"])),
    db: Session = Depends(get_db)
):
    """Endpoint para usuários solicitarem avaliações de seus relógios"""
    try:
        user_id = int(current_user["sub"])
        
        # Buscar o relógio
        watch = db.query(Watch).filter(Watch.id == evaluation.watch_id).first()
        if not watch:
            raise HTTPException(status_code=404, detail="Relógio não encontrado")
        
        # Verificar se o usuário é dono do relógio ou é admin
        if current_user["role"] != "admin" and watch.current_owner_user_id != user_id:
            raise HTTPException(status_code=403, detail="Você só pode solicitar avaliação de seus próprios relógios")
        
        # Buscar o avaliador selecionado pelo usuário
        evaluator = db.query(Evaluator).filter(
            Evaluator.id == evaluation.evaluator_id,
            Evaluator.active == True
        ).first()
        if not evaluator:
            raise HTTPException(status_code=404, detail="Avaliador não encontrado ou não está ativo")
        
        # Criar avaliação
        db_evaluation = Evaluation(
            watch_id=evaluation.watch_id,
            evaluator_id=evaluator.id,
            status="pending",
            evaluation_type=evaluation.evaluation_type or "standard",
            notes=evaluation.notes or "",
            requested_by_user_id=user_id
        )
        
        db.add(db_evaluation)
        db.commit()
        db.refresh(db_evaluation)
        
        # Criar notificação para o usuário
        try:
            create_notification(
                db=db,
                user_id=user_id,
                type="evaluation_requested",
                title="Avaliação Solicitada",
                message=f"Sua solicitação de avaliação do relógio {watch.brand} {watch.model} foi registrada."
            )
        except Exception as notif_error:
            # Se falhar na notificação, apenas log o erro, não falhe a avaliação
            print(f"Erro ao criar notificação: {notif_error}")
        
        return db_evaluation
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Erro interno na solicitação de avaliação: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@router.put("/{evaluation_id}/complete")
def complete_evaluation(
    evaluation_id: int,
    evaluation_data: dict,
    current_user = Depends(require_role(["evaluator", "admin"])),
    db: Session = Depends(get_db)
):
    """Avaliador completa uma avaliação pendente"""
    
    condition = evaluation_data.get("condition")
    authenticity = evaluation_data.get("authenticity")
    estimated_value_brl = evaluation_data.get("estimated_value_brl")
    notes = evaluation_data.get("notes")
    
    # Buscar a avaliação
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    
    # Verificar se o avaliador pode completar esta avaliação
    if current_user["role"] == "evaluator":
        evaluator = db.query(Evaluator).filter(Evaluator.user_id == int(current_user["sub"])).first()
        if not evaluator or evaluation.evaluator_id != evaluator.id:
            raise HTTPException(status_code=403, detail="Você só pode completar suas próprias avaliações")
    
    # Verificar se a avaliação está pendente
    if evaluation.status != "pending":
        raise HTTPException(status_code=400, detail="Apenas avaliações pendentes podem ser completadas")
    
    # Atualizar a avaliação
    evaluation.condition = condition
    evaluation.authenticity = authenticity
    evaluation.estimated_value_brl = estimated_value_brl
    evaluation.notes = notes
    evaluation.status = "completed"
    
    db.commit()
    db.refresh(evaluation)
    
    # Buscar o relógio avaliado
    watch = db.query(Watch).filter(Watch.id == evaluation.watch_id).first()
    
    # Notificar o usuário que solicitou
    if evaluation.requested_by_user_id:
        create_notification(
            db=db,
            user_id=evaluation.requested_by_user_id,
            type="evaluation_completed",
            title="Avaliação Concluída",
            message=f"A avaliação do seu relógio {watch.brand} {watch.model} foi concluída. Valor estimado: R$ {estimated_value_brl:,.2f}"
        )
    
    return {
        "message": "Avaliação completada com sucesso",
        "evaluation_id": evaluation.id,
        "condition": condition,
        "authenticity": authenticity,
        "estimated_value_brl": estimated_value_brl,
        "status": "completed"
    }

@router.post("/{evaluation_id}/pay")
def pay_evaluation(
    evaluation_id: int,
    payment_data: dict,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    """Usuário paga pela avaliação concluída"""
    
    payment_method = payment_data.get("payment_method")
    cpf = payment_data.get("cpf")
    
    # Buscar a avaliação
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    
    # Verificar se o usuário pode pagar esta avaliação
    if evaluation.requested_by_user_id != int(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Você só pode pagar suas próprias avaliações")
    
    # Verificar se a avaliação está completa e não paga
    if evaluation.status != "completed":
        raise HTTPException(status_code=400, detail="Apenas avaliações completas podem ser pagas")
    
    # Buscar o avaliador e a taxa
    evaluator = db.query(Evaluator).filter(Evaluator.id == evaluation.evaluator_id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="Avaliador não encontrado")
    
    evaluation_fee = evaluator.evaluation_fee
    
    # Simular processamento do pagamento
    from app.stellar import simulate_payment_conversion
    payment_result = simulate_payment_conversion(evaluation_fee, payment_method, 1)
    
    if payment_result["status"] != "success":
        raise HTTPException(status_code=400, detail="Falha no processamento do pagamento")
    
    # Calcular distribuição (70% para loja, 30% para admin/plataforma)
    store_amount = evaluation_fee * 0.70
    admin_amount = evaluation_fee * 0.30
    
    # Buscar usuários para atualizar saldos
    store = db.query(Store).filter(Store.id == evaluator.store_id).first()
    store_user = db.query(User).filter(User.id == store.user_id).first() if store else None
    admin_user = db.query(User).filter(User.role == "admin").first()
    
    # Atualizar saldos
    if store_user:
        store_user.balance_brl = (store_user.balance_brl or 0) + store_amount
    
    if admin_user:
        admin_user.balance_brl = (admin_user.balance_brl or 0) + admin_amount
    
    # Marcar avaliação como paga
    evaluation.status = "paid"
    
    db.commit()
    
    # Criar notificações
    watch = db.query(Watch).filter(Watch.id == evaluation.watch_id).first()
    
    # Notificar loja
    if store_user:
        create_notification(
            db=db,
            user_id=store_user.id,
            type="payment_received",
            title="Pagamento de Avaliação Recebido",
            message=f"Você recebeu R$ {store_amount:.2f} pela avaliação do relógio {watch.brand} {watch.model}"
        )
    
    # Notificar admin
    if admin_user:
        create_notification(
            db=db,
            user_id=admin_user.id,
            type="commission_received",
            title="Comissão de Avaliação",
            message=f"Comissão de R$ {admin_amount:.2f} recebida da avaliação do relógio {watch.brand} {watch.model}"
        )
    
    # Notificar usuário
    create_notification(
        db=db,
        user_id=int(current_user["sub"]),
        type="payment_completed",
        title="Pagamento de Avaliação Realizado",
        message=f"Pagamento de R$ {evaluation_fee:.2f} pela avaliação do relógio {watch.brand} {watch.model} foi processado"
    )
    
    return {
        "message": "Pagamento da avaliação realizado com sucesso",
        "evaluation_fee": evaluation_fee,
        "payment_method": payment_method,
        "payment_hash": payment_result["tx_hash"],
        "distribution": {
            "store_amount": store_amount,
            "admin_amount": admin_amount,
            "store_name": store.name if store else "N/A",
            "admin_commission_rate": "30%"
        },
        "status": "paid"
    }

@router.post("/", response_model=EvaluationOut)
def create_evaluation(
    evaluation: EvaluationCreate,
    current_user = Depends(require_role(["evaluator", "admin"])),
    db: Session = Depends(get_db)
):
    # Para admin, permitir qualquer avaliador ou criar automaticamente
    if current_user["role"] == "admin":
        evaluator = db.query(Evaluator).filter(
            Evaluator.id == evaluation.evaluator_id,
            Evaluator.active == True
        ).first()
        if not evaluator:
            # Se não existir avaliador, criar um temporário para o admin
            admin_evaluator = Evaluator(
                id=evaluation.evaluator_id,
                user_id=int(current_user["sub"]),
                store_id=1,  # Store padrão
                active=True,
                evaluation_fee=500.0
            )
            db.add(admin_evaluator)
            db.flush()
            evaluator = admin_evaluator
    else:
        # Verificar se o avaliador é o usuário atual
        evaluator = db.query(Evaluator).filter(
            Evaluator.id == evaluation.evaluator_id,
            Evaluator.user_id == int(current_user["sub"]),
            Evaluator.active == True
        ).first()
    
    # Se ainda não encontrou, criar avaliador temporário
    if not evaluator:
        temp_evaluator = Evaluator(
            user_id=int(current_user["sub"]),
            store_id=1,  # Store padrão
            active=True,
            evaluation_fee=500.0
        )
        db.add(temp_evaluator)
        db.flush()
        evaluator = temp_evaluator
        evaluation.evaluator_id = temp_evaluator.id
    
    # Verificar se relógio existe
    watch = db.query(Watch).filter(Watch.id == evaluation.watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado")
    
    # Verificar se já existe avaliação para este relógio
    existing_evaluation = db.query(Evaluation).filter(Evaluation.watch_id == evaluation.watch_id).first()
    if existing_evaluation:
        # Permitir reavaliação, apenas atualizar
        existing_evaluation.condition = evaluation.condition
        existing_evaluation.authenticity = evaluation.authenticity
        existing_evaluation.estimated_value_brl = evaluation.estimated_value_brl
        existing_evaluation.notes = evaluation.notes
        db.commit()
        return existing_evaluation
    
    # Criar avaliação
    db_evaluation = Evaluation(**evaluation.dict())
    db.add(db_evaluation)
    
    # Atualizar status do relógio
    watch.status = "evaluated"
    
    # Criar comissão para o avaliador
    commission = Commission(
        transaction_id=db_evaluation.id,
        transaction_type="evaluation",
        recipient_user_id=evaluator.user_id,
        amount_brl=evaluator.evaluation_fee,
        description=f"Avaliação do relógio {watch.brand} {watch.model}"
    )
    db.add(commission)
    
    # Notificar o proprietário do relógio
    create_notification(
        db=db,
        user_id=watch.current_owner_user_id,
        title="Avaliação Concluída",
        message=f"Seu relógio {watch.brand} {watch.model} foi avaliado em R$ {evaluation.estimated_value_brl:,.2f}",
        type="success"
    )
    
    db.commit()
    db.refresh(db_evaluation)
    
    return db_evaluation

@router.get("/watch/{watch_id}", response_model=EvaluationOut)
def get_watch_evaluation(
    watch_id: int,
    current_user = Depends(require_role(["admin", "store", "evaluator", "user"])),
    db: Session = Depends(get_db)
):
    evaluation = db.query(Evaluation).filter(Evaluation.watch_id == watch_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    
    return evaluation

@router.get("/evaluator/{evaluator_id}", response_model=List[EvaluationOut])
def get_evaluator_evaluations(
    evaluator_id: int,
    current_user = Depends(require_role(["admin", "evaluator"])),
    db: Session = Depends(get_db)
):
    # Verificar se é o próprio avaliador ou admin
    if current_user["role"] != "admin":
        evaluator = db.query(Evaluator).filter(
            Evaluator.id == evaluator_id,
            Evaluator.user_id == int(current_user["sub"])
        ).first()
        if not evaluator:
            raise HTTPException(status_code=403, detail="Não autorizado")
    
    evaluations = db.query(Evaluation).filter(Evaluation.evaluator_id == evaluator_id).all()
    return evaluations

@router.get("/my-evaluations", response_model=List[EvaluationOut])
def get_my_evaluations(
    current_user = Depends(require_role(["store", "evaluator", "admin"])),
    db: Session = Depends(get_db)
):
    """Endpoint para lojas, avaliadores e admins verem suas avaliações"""
    user_id = int(current_user["sub"])
    user_role = current_user["role"]
    
    if user_role == "admin":
        # Admin vê todas as avaliações
        return db.query(Evaluation).all()
    elif user_role == "store":
        # Lojas veem avaliações de relógios de sua loja
        from app.models import Store
        store = db.query(Store).filter(Store.user_id == user_id).first()
        if not store:
            return []
        
        # Buscar avaliações de relógios da loja
        evaluations = db.query(Evaluation).join(Watch).filter(
            Watch.store_id == store.id
        ).all()
        return evaluations
    else:
        # Avaliadores veem avaliações que fizeram
        evaluator = db.query(Evaluator).filter(Evaluator.user_id == user_id).first()
        if not evaluator:
            return []
        return db.query(Evaluation).filter(Evaluation.evaluator_id == evaluator.id).all()

@router.get("/", response_model=List[EvaluationOut])
def list_evaluations(
    current_user = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    return db.query(Evaluation).all()
