from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# User schemas
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str = Field(..., pattern="^(admin|store|evaluator|user)$")

class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    stellar_public_key: Optional[str] = None
    balance_brl: float = 0.0
    balance_xlm: float = 0.0
    created_at: datetime
    
    class Config:
        from_attributes = True

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

# User Profile com informações completas
class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    stellar_public_key: Optional[str] = None
    balance_brl: float = 0.0
    balance_xlm: float = 0.0
    created_at: datetime
    my_store: Optional[dict] = None  # Usar dict em vez de StoreOut para evitar referência circular
    total_stores_count: Optional[int] = None  # Total de lojas (para admin)
    
    class Config:
        from_attributes = True
    role: str = Field(..., pattern="^(admin|store|evaluator|user)$")

class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    stellar_public_key: Optional[str] = None
    balance_brl: float = 0.0
    balance_xlm: float = 0.0
    created_at: datetime
    
    class Config:
        from_attributes = True

class LoginPayload(BaseModel):
    email: EmailStr
    password: str

# User Profile com informações completas
class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str
    stellar_public_key: Optional[str] = None
    balance_brl: float = 0.0
    balance_xlm: float = 0.0
    created_at: datetime
    my_store: Optional[dict] = None  # Loja que o usuário criou
    total_stores_count: Optional[int] = None  # Total de lojas (para admin)
    
    class Config:
        from_attributes = True

# Store schemas
class StoreCreate(BaseModel):
    user_id: int
    name: str
    commission_rate: float = 0.05

class StoreOut(BaseModel):
    id: int
    user_id: int
    name: str
    credentialed: bool
    commission_rate: float
    created_at: datetime
    
    class Config:
        from_attributes = True

# Evaluator schemas
class EvaluatorCreate(BaseModel):
    user_id: int
    store_id: int
    evaluation_fee: float = 500.0

class EvaluatorOut(BaseModel):
    id: int
    user_id: int
    store_id: int
    active: bool
    evaluation_fee: float
    created_at: datetime
    
    class Config:
        from_attributes = True

# Stellar schemas
class StellarWatchRegister(BaseModel):
    serial: str
    brand: str
    model: str
    condition: str
    evaluator_id: int
    timestamp: str
    photos_hashes: List[str]
    pdf_hash: str
    estimated_value_brl: float

class NFTTransferRequest(BaseModel):
    watch_id: int
    from_user_id: int
    to_user_id: int

# Watch schemas
class WatchCreate(BaseModel):
    serial_number: str
    brand: str
    model: str
    year: Optional[int] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    purchase_price_brl: Optional[float] = None
    current_value_brl: Optional[float] = None
    photos: Optional[List[str]] = []

class WatchOut(BaseModel):
    id: int
    serial_number: str
    brand: str
    model: str
    year: Optional[int] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    purchase_price_brl: Optional[float] = None
    current_value_brl: Optional[float] = None
    current_owner_user_id: int
    nft_asset_code: Optional[str] = None
    stellar_issuer: Optional[str] = None
    blockchain_address: Optional[str] = None
    status: str
    image_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# Evaluation schemas
class EvaluationCreate(BaseModel):
    watch_id: int
    evaluator_id: int  # Usuário deve selecionar o avaliador
    evaluation_type: Optional[str] = "standard"
    notes: Optional[str] = None

class EvaluationOut(BaseModel):
    id: int
    watch_id: int
    evaluator_id: Optional[int] = None
    requested_by_user_id: Optional[int] = None
    condition: Optional[str] = None
    authenticity: Optional[str] = None
    estimated_value_brl: Optional[float] = None
    evaluation_type: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Resell schemas
class ResellOfferCreate(BaseModel):
    watch_id: int
    store_id: int
    evaluator_id: int
    proposed_price_brl: Optional[float] = None
    description: Optional[str] = None

class ResellOfferOut(BaseModel):
    id: int
    watch_id: int
    seller_user_id: int
    buyer_user_id: Optional[int] = None
    store_id: int
    evaluator_id: int
    proposed_price_brl: Optional[float] = None
    final_price_brl: Optional[float] = None
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProposePricePayload(BaseModel):
    proposed_price_brl: float

# Escrow schemas
class EscrowOut(BaseModel):
    id: int
    resell_offer_id: int
    amount_brl: float
    admin_fee_brl: float
    store_commission_brl: float
    evaluator_fee_brl: float
    seller_net_brl: float
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Notification schemas
class NotificationOut(BaseModel):
    id: int
    title: str
    message: str
    type: str
    read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Transfer schemas
class OwnershipTransferOut(BaseModel):
    id: int
    watch_id: int
    from_user_id: int
    to_user_id: int
    stellar_tx_hash: Optional[str] = None
    type: str
    price_brl: Optional[float] = None
    admin_fee_brl: float
    created_at: datetime
    
    class Config:
        from_attributes = True

# Dashboard schemas
class AdminDashboard(BaseModel):
    total_commissions: float
    pending_disputes: int
    total_watches: int
    total_transactions: int
    recent_commissions: List[dict]
    # Novas informações importantes
    total_stores: int
    active_stores: int
    total_evaluators: int
    platform_balance_brl: float
    platform_balance_xlm: float
    users_by_role: dict

# Marketplace schemas
class MarketplaceListing(BaseModel):
    watch_id: int
    price_brl: float

class PurchasePayload(BaseModel):
    payment_method: str = Field(..., pattern="^(pix|credit_card)$")
    installments: Optional[int] = Field(default=1, ge=1, le=12)
    card_number: Optional[str] = Field(default=None, pattern="^[0-9]{4} [0-9]{4} [0-9]{4} [0-9]{4}$")
    card_name: Optional[str] = Field(default=None, max_length=100)
    card_expiry: Optional[str] = Field(default=None, pattern="^[0-9]{2}/[0-9]{2}$")
    card_cvv: Optional[str] = Field(default=None, pattern="^[0-9]{3,4}$")
    cpf: Optional[str] = Field(default=None, pattern="^[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}$")

# Payment schemas
class ConversionRequest(BaseModel):
    amount_brl: float
    payment_method: str = Field(..., pattern="^(pix|credit_card)$")

class PaymentDetailsResponse(BaseModel):
    payment_id: str
    status: str
    amount_brl: float
    amount_usdc: float
    payment_method: str
    installments: Optional[int] = None
    fees: dict
    tx_hash: str
    qr_code: Optional[str] = None  # Para PIX
    pix_key: Optional[str] = None  # Para PIX
    expiry_time: Optional[str] = None  # Para PIX

class PixPaymentResponse(BaseModel):
    payment_id: str
    qr_code: str
    pix_key: str
    amount_brl: float
    expiry_time: str
    status: str = "pending"

class CreditCardPaymentResponse(BaseModel):
    payment_id: str
    amount_brl: float
    installments: int
    installment_value: float
    total_with_fees: float
    authorization_code: str
    status: str = "approved"
