from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.schemas import (
    PurchasePayload, ConversionRequest, PaymentDetailsResponse,
    PixPaymentResponse, CreditCardPaymentResponse
)
from app.auth import require_role
from app.database import get_db
from app.stellar import (
    simulate_payment_conversion, generate_pix_payment, 
    generate_credit_card_payment, calculate_payment_fees
)
import time
from datetime import datetime, timedelta

router = APIRouter(prefix="/payments", tags=["payments"])

# Schemas adicionais
class FeeCalculationRequest(BaseModel):
    amount_brl: float
    payment_method: str
    installments: int = 1

class PixProcessRequest(BaseModel):
    watch_id: int
    cpf: str

@router.post("/calculate-fees")
def calculate_fees(
    request: FeeCalculationRequest,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    """
    Calcula as taxas de pagamento para PIX ou cartão de crédito com splits detalhados
    """
    if request.amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if request.payment_method == "pix":
        # PIX: 1% de taxa total (0.5% plataforma + 0.5% stellar)
        platform_fee = request.amount_brl * 0.005  # 0.5% para plataforma
        stellar_fee = request.amount_brl * 0.005   # 0.5% para Stellar
        payment_processor_fee = 0.10  # Taxa fixa PIX
        total_fees = platform_fee + stellar_fee + payment_processor_fee
        total_amount = request.amount_brl + total_fees
        
        return {
            "amount_brl": request.amount_brl,
            "payment_method": "pix",
            "fees": {
                "platform_fee_brl": platform_fee,
                "stellar_fee_brl": stellar_fee,
                "payment_processor_fee_brl": payment_processor_fee,
                "total_fees_brl": total_fees
            },
            "total_amount_brl": total_amount,
            "installments": 1,
            "fee_breakdown": {
                "platform_percentage": 0.5,
                "stellar_percentage": 0.5,
                "processor_fixed": 0.10
            },
            "usdc_conversion": {
                "amount_usdc": request.amount_brl / 5.2,  # Simulação BRL/USD
                "fees_usdc": total_fees / 5.2,
                "total_usdc": total_amount / 5.2
            }
        }
        
    elif request.payment_method == "credit_card":
        # Cartão: 3.5% + 1.5% por parcela adicional
        base_fee_percentage = 0.035  # 3.5% base
        installment_fee = max(0, request.installments - 1) * 0.015  # 1.5% por parcela adicional
        total_percentage = base_fee_percentage + installment_fee
        
        # Divisão das taxas
        platform_fee = request.amount_brl * (total_percentage * 0.6)  # 60% plataforma
        stellar_fee = request.amount_brl * (total_percentage * 0.3)   # 30% stellar
        processor_fee = request.amount_brl * (total_percentage * 0.1) # 10% processador
        
        total_fees = platform_fee + stellar_fee + processor_fee
        total_amount = request.amount_brl + total_fees
        installment_value = total_amount / request.installments
        
        return {
            "amount_brl": request.amount_brl,
            "payment_method": "credit_card",
            "installments": request.installments,
            "fees": {
                "platform_fee_brl": platform_fee,
                "stellar_fee_brl": stellar_fee,
                "payment_processor_fee_brl": processor_fee,
                "total_fees_brl": total_fees
            },
            "total_amount_brl": total_amount,
            "installment_value_brl": installment_value,
            "fee_breakdown": {
                "base_percentage": base_fee_percentage * 100,
                "installment_percentage": installment_fee * 100,
                "total_percentage": total_percentage * 100,
                "platform_share": 60,
                "stellar_share": 30,
                "processor_share": 10
            },
            "usdc_conversion": {
                "amount_usdc": request.amount_brl / 5.2,
                "fees_usdc": total_fees / 5.2,
                "total_usdc": total_amount / 5.2,
                "installment_usdc": installment_value / 5.2
            }
        }
    
    else:
        raise HTTPException(status_code=400, detail="Método de pagamento inválido. Use 'pix' ou 'credit_card'")

@router.post("/stellar/simulate-transaction")
def simulate_stellar_transaction(
    transaction_data: dict,
    current_user = Depends(require_role(["user", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Simula uma transação na rede Stellar com fees separados
    """
    amount_brl = transaction_data.get("amount_brl", 0)
    transaction_type = transaction_data.get("type", "payment")  # payment, nft_transfer, escrow
    
    if amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    # Simular fees da rede Stellar
    stellar_base_fee = 0.00001  # Fee base da rede Stellar em XLM
    stellar_network_fee = 0.00001 * 2  # Fee adicional para operações complexas
    
    # Conversões simuladas
    xlm_to_brl = 2.5  # 1 XLM = R$ 2.50 (simulado)
    usd_to_brl = 5.2  # 1 USD = R$ 5.20 (simulado)
    
    # Calcular fees em BRL
    network_fee_brl = (stellar_base_fee + stellar_network_fee) * xlm_to_brl
    platform_fee_brl = amount_brl * 0.001  # 0.1% da plataforma
    
    # Simular transação
    tx_hash = f"stellar_sim_{int(time.time())}_{transaction_type}"
    
    return {
        "transaction_hash": tx_hash,
        "status": "confirmed",
        "amount_brl": amount_brl,
        "amount_usdc": amount_brl / usd_to_brl,
        "fees": {
            "stellar_network_fee_xlm": stellar_base_fee + stellar_network_fee,
            "stellar_network_fee_brl": network_fee_brl,
            "platform_fee_brl": platform_fee_brl,
            "total_fees_brl": network_fee_brl + platform_fee_brl
        },
        "net_amount_brl": amount_brl - network_fee_brl - platform_fee_brl,
        "transaction_type": transaction_type,
        "stellar_account": "GAYJA3XAVTTHEF5QLZRMQ374P4MSXJSRJMGBVSDECLHGANUOXBBAZU5C",
        "timestamp": datetime.utcnow().isoformat(),
        "simulation": True
    }

@router.post("/process-pix")
def process_pix_payment(
    request: PixProcessRequest,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
):
    """
    Processa um pagamento via PIX
    """
    from app.models import Watch
    
    # Buscar relógio
    watch = db.query(Watch).filter(Watch.id == request.watch_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Relógio não encontrado")
    
    # Calcular valor com taxa PIX
    amount = watch.current_value_brl or 50000.0
    fee = amount * 0.01
    total = amount + fee
    
    # Simular processamento PIX
    payment_id = f"PIX_{int(time.time())}_{request.watch_id}"
    
    return {
        "payment_id": payment_id,
        "status": "confirmed",
        "amount_brl": amount,
        "fee_brl": fee,
        "total_amount_brl": total,
        "payment_method": "pix",
        "cpf": request.cpf,
        "watch_id": request.watch_id,
        "qr_code": f"00020126360014BR.GOV.BCB.PIX0114{request.cpf}5204000053039865802BR5913MARKETPLACE6009SAO PAULO62070503***6304",
        "pix_key": request.cpf
    }

@router.post("/simulate-conversion")
def simulate_conversion(
    request: ConversionRequest,
    current_user = Depends(require_role(["admin", "store", "user"])),
    db: Session = Depends(get_db)
):
    """
    Simula conversão de pagamento BRL para stablecoin testnet
    """
    if request.amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if request.payment_method not in ["pix", "credit_card"]:
        raise HTTPException(status_code=400, detail="Método de pagamento inválido")
    
    result = simulate_payment_conversion(request.amount_brl, request.payment_method)
    
    return result

@router.post("/pix/generate")
def generate_pix(
    amount_brl: float,
    buyer_cpf: str,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
) -> PixPaymentResponse:
    """
    Gera um pagamento PIX para o usuário
    """
    if amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if not buyer_cpf or len(buyer_cpf) != 14:  # Formato: 000.000.000-00
        raise HTTPException(status_code=400, detail="CPF inválido")
    
    buyer_name = current_user.get("name", "Cliente")
    
    pix_data = generate_pix_payment(amount_brl, buyer_name, buyer_cpf)
    
    return PixPaymentResponse(
        payment_id=pix_data["payment_id"],
        qr_code=pix_data["qr_code"],
        pix_key=pix_data["pix_key"],
        amount_brl=amount_brl,
        expiry_time=datetime.fromtimestamp(pix_data["expiry_time"]).isoformat(),
        status=pix_data["status"]
    )

@router.post("/credit-card/process")
def process_credit_card(
    purchase: PurchasePayload,
    amount_brl: float,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
) -> CreditCardPaymentResponse:
    """
    Processa pagamento com cartão de crédito
    """
    if amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if purchase.payment_method != "credit_card":
        raise HTTPException(status_code=400, detail="Método de pagamento deve ser credit_card")
    
    # Validar dados do cartão
    if not all([purchase.card_number, purchase.card_name, purchase.card_expiry, purchase.card_cvv]):
        raise HTTPException(status_code=400, detail="Dados do cartão incompletos")
    
    if not purchase.cpf:
        raise HTTPException(status_code=400, detail="CPF é obrigatório para pagamento com cartão")
    
    card_data = {
        "card_number": purchase.card_number,
        "card_name": purchase.card_name,
        "card_expiry": purchase.card_expiry,
        "card_cvv": purchase.card_cvv
    }
    
    installments = purchase.installments or 1
    
    if installments < 1 or installments > 12:
        raise HTTPException(status_code=400, detail="Número de parcelas deve ser entre 1 e 12")
    
    payment_result = generate_credit_card_payment(amount_brl, installments, card_data)
    
    if payment_result["status"] != "approved":
        raise HTTPException(status_code=400, detail=payment_result.get("reason", "Cartão recusado"))
    
    return CreditCardPaymentResponse(
        payment_id=payment_result["payment_id"],
        amount_brl=amount_brl,
        installments=installments,
        installment_value=payment_result["installment_value"],
        total_with_fees=payment_result["total_with_fees"],
        authorization_code=payment_result["authorization_code"],
        status=payment_result["status"]
    )

@router.post("/fees/calculate")
def calculate_fees(
    amount_brl: float,
    payment_method: str,
    installments: int = 1,
    current_user = Depends(require_role(["user", "store"])),
    db: Session = Depends(get_db)
):
    """
    Calcula as taxas para um pagamento
    """
    if amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if payment_method not in ["pix", "credit_card"]:
        raise HTTPException(status_code=400, detail="Método de pagamento inválido")
    
    if installments < 1 or installments > 12:
        raise HTTPException(status_code=400, detail="Número de parcelas deve ser entre 1 e 12")
    
    fees = calculate_payment_fees(amount_brl, payment_method, installments)
    
    return {
        "amount_brl": amount_brl,
        "payment_method": payment_method,
        "installments": installments,
        "fees": fees,
        "summary": {
            "base_amount": fees["base_amount"],
            "processing_fee": fees["processing_fee"],
            "installment_fee": fees.get("installment_fee", 0),
            "total_fees": fees["total_fees"],
            "final_amount": fees["final_amount"],
            "installment_value": fees.get("installment_value", fees["final_amount"])
        }
    }

@router.get("/conversion-rates")
def get_conversion_rates(
    current_user = Depends(require_role(["admin", "store", "user"])),
    db: Session = Depends(get_db)
):
    """
    Retorna taxas de conversão atuais e informações sobre métodos de pagamento
    """
    return {
        "brl_to_usdc": 0.2,
        "brl_to_xlm": 4.5,
        "payment_methods": {
            "pix": {
                "fee_percentage": 1.0,
                "min_amount": 1.0,
                "max_amount": 100000.0,
                "processing_time": "instantâneo",
                "installments": False
            },
            "credit_card": {
                "fee_percentage": 3.5,
                "installment_fee_per_month": 1.5,
                "min_amount": 10.0,
                "max_amount": 50000.0,
                "processing_time": "1-2 dias úteis",
                "max_installments": 12,
                "installments": True
            }
        },
        "updated_at": datetime.now().isoformat()
    }

@router.post("/convert")
def convert_currency(
    request: ConversionRequest,
    current_user = Depends(require_role(["admin", "store", "user"])),
    db: Session = Depends(get_db)
):
    """
    Converte BRL para USDC com base no método de pagamento
    """
    if request.amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if request.payment_method not in ["pix", "credit_card"]:
        raise HTTPException(status_code=400, detail="Método de pagamento inválido")
    
    result = simulate_payment_conversion(request.amount_brl, request.payment_method)
    
    if result["status"] != "confirmed":
        raise HTTPException(status_code=400, detail="Erro na conversão")
    
    return {
        "amount_brl": result["amount_brl"],
        "amount_usdc": result["amount_usdc"],
        "exchange_rate": result["conversion_rate"],
        "payment_method": result["payment_method"],
        "fees": result["fees"],
        "tx_hash": result["tx_hash"],
        "timestamp": datetime.now().isoformat()
    }

@router.post("/process")
def process_payment(
    purchase: PurchasePayload,
    amount_brl: float,
    current_user = Depends(require_role(["user"])),
    db: Session = Depends(get_db)
) -> PaymentDetailsResponse:
    """
    Processa um pagamento completo (PIX ou cartão de crédito)
    """
    if amount_brl <= 0:
        raise HTTPException(status_code=400, detail="Valor deve ser maior que zero")
    
    if purchase.payment_method not in ["pix", "credit_card"]:
        raise HTTPException(status_code=400, detail="Método de pagamento inválido")
    
    installments = purchase.installments or 1
    
    # Processar baseado no método de pagamento
    if purchase.payment_method == "pix":
        if not purchase.cpf:
            raise HTTPException(status_code=400, detail="CPF é obrigatório para PIX")
        
        buyer_name = current_user.get("name", "Cliente")
        pix_data = generate_pix_payment(amount_brl, buyer_name, purchase.cpf)
        
        # Simular conversão para blockchain
        conversion = simulate_payment_conversion(amount_brl, "pix", 1)
        
        return PaymentDetailsResponse(
            payment_id=pix_data["payment_id"],
            status="pending",
            amount_brl=amount_brl,
            amount_usdc=conversion["amount_usdc"],
            payment_method="pix",
            installments=1,
            fees=conversion["fees"],
            tx_hash=conversion["tx_hash"],
            qr_code=pix_data["qr_code"],
            pix_key=pix_data["pix_key"],
            expiry_time=datetime.fromtimestamp(pix_data["expiry_time"]).isoformat()
        )
    
    elif purchase.payment_method == "credit_card":
        # Validar dados do cartão
        if not all([purchase.card_number, purchase.card_name, purchase.card_expiry, purchase.card_cvv]):
            raise HTTPException(status_code=400, detail="Dados do cartão incompletos")
        
        if not purchase.cpf:
            raise HTTPException(status_code=400, detail="CPF é obrigatório para cartão de crédito")
        
        card_data = {
            "card_number": purchase.card_number,
            "card_name": purchase.card_name,
            "card_expiry": purchase.card_expiry,
            "card_cvv": purchase.card_cvv
        }
        
        # Processar cartão
        card_result = generate_credit_card_payment(amount_brl, installments, card_data)
        
        if card_result["status"] != "approved":
            raise HTTPException(status_code=400, detail=card_result.get("reason", "Cartão recusado"))
        
        # Simular conversão para blockchain
        conversion = simulate_payment_conversion(amount_brl, "credit_card", installments)
        
        return PaymentDetailsResponse(
            payment_id=card_result["payment_id"],
            status="confirmed",
            amount_brl=amount_brl,
            amount_usdc=conversion["amount_usdc"],
            payment_method="credit_card",
            installments=installments,
            fees=conversion["fees"],
            tx_hash=conversion["tx_hash"]
        )
    
    raise HTTPException(status_code=400, detail="Método de pagamento não suportado")

@router.post("/process")
def process_payment(
    process_data: dict,
    current_user = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Processar pagamento confirmado"""
    escrow_id = process_data.get("escrow_id")
    payment_confirmed = process_data.get("payment_confirmed", False)
    
    if not payment_confirmed:
        raise HTTPException(status_code=400, detail="Pagamento não confirmado")
    
    # Simular processamento de pagamento
    from app.models import Escrow
    escrow = db.query(Escrow).filter(Escrow.id == escrow_id).first()
    if escrow:
        escrow.status = "completed"
        db.commit()
    
    return {
        "status": "success",
        "message": "Pagamento processado",
        "splits_processed": True
    }

@router.post("/evaluator-fee")
def pay_evaluator_fee(
    fee_data: dict,
    current_user = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    """Pagar taxa do avaliador"""
    evaluator_id = fee_data.get("evaluator_id")
    amount_brl = fee_data.get("amount_brl", 500.0)
    
    # Simular pagamento da taxa
    from app.models import Evaluator
    evaluator = db.query(Evaluator).filter(Evaluator.id == evaluator_id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="Avaliador não encontrado")
    
    return {
        "status": "success",
        "message": "Taxa do avaliador paga",
        "evaluator_id": evaluator_id,
        "amount_paid": amount_brl
    }

@router.get("/")
def list_payments(
    current_user = Depends(require_role(["admin", "user", "store"])),
    db: Session = Depends(get_db)
):
    """Lista todos os pagamentos (simulados) do sistema"""
    # Para MVP, vamos retornar dados simulados
    from app.models import Watch
    
    # Buscar relógios vendidos para simular pagamentos
    sold_watches = db.query(Watch).filter(Watch.status == "sold").all()
    
    simulated_payments = []
    for i, watch in enumerate(sold_watches, 1):
        simulated_payments.append({
            "id": i,
            "watch_id": watch.id,
            "watch_description": f"{watch.brand} {watch.model}",
            "amount_brl": 95000.0 + (i * 5000),  # Valores simulados
            "payment_method": "pix" if i % 2 == 0 else "credit_card",
            "status": "completed",
            "fee_brl": 950.0 if i % 2 == 0 else 2850.0,
            "created_at": watch.created_at.isoformat() if watch.created_at else None
        })
    
    return simulated_payments
