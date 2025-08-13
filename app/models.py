from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text, JSON, create_engine
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, store, evaluator, user
    stellar_public_key = Column(String)
    stellar_secret = Column(String)
    balance_brl = Column(Float, default=0.0)  # Saldo em BRL
    balance_xlm = Column(Float, default=0.0)  # Saldo em XLM Stellar
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    owned_watches = relationship("Watch", foreign_keys="Watch.current_owner_user_id", back_populates="current_owner")
    notifications = relationship("Notification", back_populates="user")

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    cnpj = Column(String, unique=True, nullable=True)
    address = Column(String)
    phone = Column(String)
    email = Column(String)
    credentialed = Column(Boolean, default=False)  # Corrigir nome do campo
    commission_rate = Column(Float, default=0.05)  # 5% padrão
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    evaluators = relationship("Evaluator", back_populates="store")
    watches = relationship("Watch", back_populates="store")

class Evaluator(Base):
    __tablename__ = "evaluators"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    name = Column(String, nullable=False)
    cpf = Column(String, unique=True, nullable=False)
    specialty = Column(String)
    phone = Column(String)
    email = Column(String)
    active = Column(Boolean, default=True)
    evaluation_fee = Column(Float, default=500.0)  # R$ 500 por avaliação
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    store = relationship("Store", back_populates="evaluators")
    evaluations = relationship("Evaluation", back_populates="evaluator")

class Watch(Base):
    __tablename__ = "watches"
    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, nullable=False)
    brand = Column(String)
    model = Column(String)
    year = Column(Integer)
    condition = Column(String)
    description = Column(Text)
    purchase_price_brl = Column(Float)
    current_value_brl = Column(Float)
    current_owner_user_id = Column(Integer, ForeignKey("users.id"))
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)  # Loja responsável pela venda
    blockchain_address = Column(String)
    status = Column(String, default="registered")  # registered, evaluated, for_sale, sold, tokenized
    image_url = Column(String)
    
    # Campos para contratos Stellar
    laudo_hash = Column(String)  # SHA256 do laudo de avaliação
    nft_code = Column(String)  # Código do asset NFT (NRF-123456)
    nft_issuer = Column(String)  # Conta emissora do NFT na Stellar
    price_brl = Column(Float)  # Preço atual em BRL
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    current_owner = relationship("User", foreign_keys=[current_owner_user_id], back_populates="owned_watches")
    store = relationship("Store", foreign_keys=[store_id], back_populates="watches")
    nft_token = relationship("NFTToken", back_populates="watch", uselist=False)
    evaluations = relationship("Evaluation", back_populates="watch")
    transfers = relationship("OwnershipTransfer", back_populates="watch")

class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id"))
    evaluator_id = Column(Integer, ForeignKey("evaluators.id"), nullable=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Para solicitações de usuários
    condition = Column(String, nullable=True)  # excellent, good, fair, poor
    authenticity = Column(String, nullable=True)  # authentic, replica, unknown
    estimated_value_brl = Column(Float, nullable=True)
    evaluation_type = Column(String, default="standard")  # standard, premium, express
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, in_progress, completed, cancelled
    
    # Relationships
    watch = relationship("Watch", back_populates="evaluations")
    evaluator = relationship("Evaluator", back_populates="evaluations")
    requesting_user = relationship("User", foreign_keys=[requested_by_user_id])

class ResellOffer(Base):
    __tablename__ = "resell_offers"
    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id"))
    seller_user_id = Column(Integer, ForeignKey("users.id"))
    buyer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    evaluator_id = Column(Integer, ForeignKey("evaluators.id"))
    proposed_price_brl = Column(Float)
    final_price_brl = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, price_proposed, accepted, paid, delivered, completed, cancelled
    description = Column(Text)
    asking_price_brl = Column(Float)  # Preço inicial solicitado pelo vendedor
    seller_stellar_key = Column(String)  # Chave Stellar do vendedor para escrow
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watch = relationship("Watch")
    seller = relationship("User", foreign_keys=[seller_user_id])
    buyer = relationship("User", foreign_keys=[buyer_user_id])
    store = relationship("Store")
    evaluator = relationship("Evaluator")
    escrow = relationship("Escrow", back_populates="offer", uselist=False)

class OwnershipTransfer(Base):
    __tablename__ = "ownership_transfers"
    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id"))
    from_user_id = Column(Integer, ForeignKey("users.id"))
    to_user_id = Column(Integer, ForeignKey("users.id"))
    stellar_tx_hash = Column(String)
    type = Column(String)  # sale, resale, gift
    price_brl = Column(Float, nullable=True)
    admin_fee_brl = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watch = relationship("Watch", back_populates="transfers")
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String)  # info, success, warning, error
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="notifications")

class Commission(Base):
    __tablename__ = "commissions"
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer)  # ID da transação relacionada
    transaction_type = Column(String)  # sale, resale
    recipient_user_id = Column(Integer, ForeignKey("users.id"))
    amount_brl = Column(Float)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    recipient = relationship("User")

# ========================= MODELOS PARA CONTRATOS STELLAR =========================

class NFTToken(Base):
    """
    Modelo para tokens NFT dos relógios
    """
    __tablename__ = "nft_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id"), unique=True)
    token_id = Column(String, unique=True, nullable=False)  # asset_code:issuer
    asset_code = Column(String, nullable=False)  # NRF-123456
    issuer_account = Column(String, nullable=False)  # Stellar public key do emissor
    current_owner_stellar_key = Column(String, nullable=False)
    metadata_hash = Column(String, nullable=False)  # SHA256 do laudo
    mint_transaction_hash = Column(String, nullable=False)
    last_transfer_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watch = relationship("Watch", back_populates="nft_token")

class Escrow(Base):
    """
    Modelo para contratos de escrow
    """
    __tablename__ = "escrows"
    
    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("resell_offers.id"))
    escrow_stellar_account = Column(String, nullable=False)  # Conta de escrow na Stellar
    escrow_secret_key = Column(String, nullable=False)  # Chave secreta (criptografada em produção)
    amount_usdc = Column(Float, nullable=False)
    depositor_stellar_key = Column(String, nullable=False)
    
    # Status e confirmações
    status = Column(String, default="holding")  # holding, released, refunded, expired
    seller_confirmed = Column(Boolean, default=False)
    evaluator_confirmed = Column(Boolean, default=False)
    seller_confirmed_at = Column(DateTime)
    evaluator_confirmed_at = Column(DateTime)
    
    # Transações de liberação
    admin_tx_hash = Column(String)
    seller_tx_hash = Column(String)
    admin_amount_usdc = Column(Float)
    seller_amount_usdc = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    released_at = Column(DateTime)
    
    # Relationships
    offer = relationship("ResellOffer", back_populates="escrow")

class StellarTransaction(Base):
    """
    Log de todas as transações Stellar
    """
    __tablename__ = "stellar_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_hash = Column(String, unique=True, nullable=False)
    transaction_type = Column(String, nullable=False)  # nft_mint, nft_transfer, escrow_deposit, escrow_release, payment
    from_account = Column(String)
    to_account = Column(String)
    asset_code = Column(String)
    asset_issuer = Column(String)
    amount = Column(String)
    memo = Column(String)
    
    # Contexto do marketplace
    watch_id = Column(Integer, ForeignKey("watches.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    escrow_id = Column(Integer, ForeignKey("escrows.id"))
    
    # Status
    status = Column(String, default="pending")  # pending, success, failed
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watch = relationship("Watch")
    user = relationship("User")
    escrow = relationship("Escrow")

class EvaluationReport(Base):
    """
    Relatórios de avaliação armazenados off-chain
    """
    __tablename__ = "evaluation_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(Integer, ForeignKey("watches.id"))
    evaluator_id = Column(Integer, ForeignKey("evaluators.id"))
    
    # Dados do laudo
    report_hash = Column(String, unique=True, nullable=False)  # SHA256
    s3_bucket = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    
    # Metadados do laudo
    condition = Column(String, nullable=False)  # excellent, good, fair, poor
    authenticity = Column(String, nullable=False)  # authentic, replica, unknown
    estimated_value_brl = Column(Float)
    
    # Hashes das evidências
    photos_hashes = Column(JSON)  # Lista de hashes SHA256 das fotos
    pdf_hash = Column(String)  # Hash do PDF do laudo
    
    # Assinatura digital
    evaluator_signature = Column(String)  # Assinatura digital do avaliador
    signature_timestamp = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    watch = relationship("Watch")
    evaluator = relationship("Evaluator")
