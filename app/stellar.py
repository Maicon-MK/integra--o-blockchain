from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset, Account
from stellar_sdk.exceptions import SdkError
import os
import hashlib
import time
import uuid

# Configuração para modo SIMULADO (desenvolvimento)
STELLAR_NETWORK = os.getenv("STELLAR_NETWORK", "simulation")  # simulation, testnet, mainnet
HORIZON_URL = os.getenv("STELLAR_HORIZON_URL", "https://horizon-testnet.stellar.org")

# Modo simulado - não conecta na rede real
SIMULATION_MODE = True

# Chave do emissor de NFTs (simulada para desenvolvimento)
if SIMULATION_MODE:
    # Chaves simuladas para desenvolvimento
    MARKETPLACE_KEYPAIR_PUBLIC = "GAYJA3XAVTTHEF5QLZRMQ374P4MSXJSRJMGBVSDECLHGANUOXBBAZU5C"
    MARKETPLACE_KEYPAIR_SECRET = "SDKJLASDJKLASDJKLASDJKLASDJKLASDJKLASDJKLASDJKLASDJKLASDJKL"
else:
    # Em produção, usar chaves reais do .env
    MARKETPLACE_SECRET = os.getenv("MARKETPLACE_SECRET")
    if MARKETPLACE_SECRET and MARKETPLACE_SECRET.startswith("SD"):
        try:
            MARKETPLACE_KEYPAIR = Keypair.from_secret(MARKETPLACE_SECRET)
            MARKETPLACE_KEYPAIR_PUBLIC = MARKETPLACE_KEYPAIR.public_key
            MARKETPLACE_KEYPAIR_SECRET = MARKETPLACE_SECRET
        except:
            MARKETPLACE_KEYPAIR = Keypair.random()
            MARKETPLACE_KEYPAIR_PUBLIC = MARKETPLACE_KEYPAIR.public_key
            MARKETPLACE_KEYPAIR_SECRET = MARKETPLACE_KEYPAIR.secret
    else:
        MARKETPLACE_KEYPAIR = Keypair.random()
        MARKETPLACE_KEYPAIR_PUBLIC = MARKETPLACE_KEYPAIR.public_key
        MARKETPLACE_KEYPAIR_SECRET = MARKETPLACE_KEYPAIR.secret

def create_nft_asset(watch_id: int, brand: str, model: str, serial_number: str, receiver_public: str):
    """
    Cria um NFT único para um relógio (SIMULADO para desenvolvimento)
    """
    try:
        # Gerar código único do asset baseado no relógio
        asset_code = f"W{watch_id:06d}"  # W000001, W000002, etc.
        
        # MODO SIMULADO - Não conecta na rede Stellar real
        print(f"🎨 Criando NFT simulado: {asset_code} para relógio {brand} {model}")
        
        # Simular criação do NFT com dados realistas
        tx_hash = hashlib.sha256(
            f"{asset_code}{MARKETPLACE_KEYPAIR_PUBLIC}{receiver_public}{time.time()}".encode()
        ).hexdigest()
        
        # Simular endereço blockchain
        blockchain_address = f"stellar:{MARKETPLACE_KEYPAIR_PUBLIC}:{asset_code}"
        
        result = {
            "asset_code": asset_code,
            "issuer": MARKETPLACE_KEYPAIR_PUBLIC,
            "receiver": receiver_public,
            "tx_hash": tx_hash,
            "status": "success",
            "amount": "1",
            "blockchain_address": blockchain_address,
            "network": "stellar-simulation",
            "metadata": {
                "watch_id": watch_id,
                "brand": brand,
                "model": model,
                "serial_number": serial_number,
                "created_at": time.time(),
                "nft_type": "watch_certificate",
                "simulation": True
            }
        }
        
        print(f"✅ NFT simulado criado: {asset_code}")
        return result
    
    except Exception as e:
        print(f"❌ Erro ao criar NFT: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

def transfer_nft(asset_code: str, from_secret: str, to_public: str):
    """
    Transfere um NFT de um usuário para outro
    """
    try:
        # Simular transferência do NFT
        tx_hash = hashlib.sha256(
            f"transfer_{asset_code}_{from_secret}_{to_public}_{time.time()}".encode()
        ).hexdigest()
        
        return {
            "asset_code": asset_code,
            "from_account": Keypair.from_secret(from_secret).public_key,
            "to_account": to_public,
            "tx_hash": tx_hash,
            "status": "success"
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def get_nft_history(asset_code: str):
    """
    Obtém o histórico de transações de um NFT
    """
    try:
        # Simular busca do histórico na blockchain
        # Em ambiente real, consultaria o Horizon API
        return {
            "asset_code": asset_code,
            "issuer": MARKETPLACE_KEYPAIR.public_key,
            "transactions": [
                {
                    "type": "create_account",
                    "hash": f"tx_create_{asset_code}",
                    "created_at": "2025-08-02T10:00:00Z"
                },
                {
                    "type": "payment",
                    "hash": f"tx_mint_{asset_code}",
                    "created_at": "2025-08-02T10:01:00Z"
                }
            ]
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def simulate_payment_conversion(amount_brl: float, payment_method: str, installments: int = 1):
    """
    Simula conversão de pagamento BRL para stablecoin na testnet
    """
    try:
        # Taxa de conversão simulada (1 BRL = 0.2 USDC)
        usdc_rate = 0.2
        usdc_amount = amount_brl * usdc_rate
        
        # Calcular taxas baseadas no método de pagamento
        fees = calculate_payment_fees(amount_brl, payment_method, installments)
        
        # Simular transação de pagamento
        tx_hash = hashlib.sha256(
            f"payment_{amount_brl}_{payment_method}_{installments}_{time.time()}".encode()
        ).hexdigest()
        
        return {
            "amount_brl": amount_brl,
            "amount_usdc": usdc_amount,
            "payment_method": payment_method,
            "installments": installments,
            "fees": fees,
            "tx_hash": tx_hash,
            "status": "success",  # Mudança aqui
            "conversion_rate": usdc_rate
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def calculate_payment_fees(amount_brl: float, payment_method: str, installments: int = 1):
    """
    Calcula taxas baseadas no método de pagamento
    """
    fees = {
        "base_amount": amount_brl,
        "installments": installments,
        "payment_method": payment_method
    }
    
    if payment_method == "pix":
        # PIX: taxa fixa baixa
        fees["processing_fee"] = amount_brl * 0.01  # 1%
        fees["installment_fee"] = 0.0
        fees["total_fees"] = fees["processing_fee"]
        fees["final_amount"] = amount_brl + fees["total_fees"]
        
    elif payment_method == "credit_card":
        # Cartão: taxa de processamento + taxa de parcelamento
        fees["processing_fee"] = amount_brl * 0.035  # 3.5%
        
        if installments > 1:
            # Taxa adicional para parcelamento (1.5% ao mês)
            fees["installment_fee"] = amount_brl * 0.015 * (installments - 1)
        else:
            fees["installment_fee"] = 0.0
            
        fees["total_fees"] = fees["processing_fee"] + fees["installment_fee"]
        fees["final_amount"] = amount_brl + fees["total_fees"]
        fees["installment_value"] = fees["final_amount"] / installments
    
    return fees

def generate_pix_payment(amount_brl: float, buyer_name: str, buyer_cpf: str):
    """
    Gera dados simulados para pagamento PIX
    """
    payment_id = f"PIX_{uuid.uuid4().hex[:8].upper()}"
    
    # Simular chave PIX do marketplace
    pix_key = "marketplace@luxowatches.com"
    
    # Simular QR Code PIX (normalmente seria gerado pela API do banco)
    qr_data = f"00020126580014br.gov.bcb.pix0136{pix_key}0208Pagament52040000530398654{amount_brl:05.2f}5802BR5925MARKETPLACE LUXO WATCHES6009SAO PAULO62070503***6304"
    qr_code = hashlib.md5(qr_data.encode()).hexdigest()
    
    # PIX expira em 30 minutos
    expiry_timestamp = int(time.time()) + (30 * 60)
    
    return {
        "payment_id": payment_id,
        "qr_code": qr_code,
        "pix_key": pix_key,
        "amount_brl": amount_brl,
        "buyer_name": buyer_name,
        "buyer_cpf": buyer_cpf,
        "expiry_time": expiry_timestamp,
        "status": "pending"
    }

def generate_credit_card_payment(amount_brl: float, installments: int, card_data: dict):
    """
    Simula processamento de pagamento com cartão de crédito
    """
    payment_id = f"CC_{uuid.uuid4().hex[:8].upper()}"
    
    # Simular autorização do cartão
    authorization_code = f"AUTH_{uuid.uuid4().hex[:6].upper()}"
    
    # Calcular valores
    fees = calculate_payment_fees(amount_brl, "credit_card", installments)
    
    # Simular validação do cartão (em produção, integraria com gateway)
    card_valid = validate_credit_card(card_data)
    
    if not card_valid:
        return {
            "status": "denied",
            "reason": "Cartão inválido ou dados incorretos"
        }
    
    return {
        "payment_id": payment_id,
        "authorization_code": authorization_code,
        "amount_brl": amount_brl,
        "installments": installments,
        "installment_value": fees["installment_value"],
        "total_with_fees": fees["final_amount"],
        "fees": fees,
        "status": "approved",
        "card_last_digits": card_data.get("card_number", "")[-4:] if card_data.get("card_number") else "****"
    }

def validate_credit_card(card_data: dict):
    """
    Simula validação básica de cartão de crédito
    """
    if not card_data:
        return False
        
    # Verificar se todos os campos obrigatórios estão presentes
    required_fields = ["card_number", "card_name", "card_expiry", "card_cvv"]
    for field in required_fields:
        if not card_data.get(field):
            return False
    
    # Simular validação (em produção, seria mais complexa)
    card_number = card_data["card_number"].replace(" ", "")
    
    # Verificar se tem 16 dígitos
    if len(card_number) != 16 or not card_number.isdigit():
        return False
    
    # Verificar CVV
    cvv = card_data["card_cvv"]
    if len(cvv) < 3 or len(cvv) > 4 or not cvv.isdigit():
        return False
    
    # Verificar formato da data de expiração
    expiry = card_data["card_expiry"]
    if len(expiry) != 5 or expiry[2] != "/":
        return False
    
    try:
        month, year = expiry.split("/")
        month_int = int(month)
        year_int = int("20" + year)
        
        if month_int < 1 or month_int > 12:
            return False
            
        # Verificar se não está expirado (simulação simples)
        current_year = 2025
        current_month = 8
        
        if year_int < current_year or (year_int == current_year and month_int < current_month):
            return False
            
    except ValueError:
        return False
    
    return True
