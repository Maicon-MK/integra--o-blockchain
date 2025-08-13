# 🏪 Marketplace de Relógios Luxo - Stellar Blockchain

Marketplace especializado em relógios de luxo com integração blockchain Stellar para NFTs, escrow e pagamentos seguros.

## 🚀 Tecnologias

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL/SQLite
- **Blockchain**: Stellar SDK, NFTs, Smart Contracts
- **Autenticação**: JWT, OAuth2
- **Pagamentos**: PIX, Cartão de Crédito, Stellar (XLM/USDC)

## ⚡ Instalação Rápida

```bash
# Clonar repositório
git clone <repository-url>
cd block

# Instalar dependências
pip install -r requirements.txt

# Configurar ambiente
cp .env.example .env
# Editar .env com suas configurações

# Executar aplicação
uvicorn app.main:app --reload
```

## 🔧 Funcionalidades

### 👤 Usuários
- Cadastro e autenticação
- Compra de relógios
- Solicitação de avaliações

### 🏬 Lojas
- Venda de relógios
- Gestão de estoque
- Histórico de vendas

### 📊 Avaliadores
- Avaliação de relógios
- Emissão de certificados
- Sistema de comissões

### 🛡️ Admin
- Dashboard completo
- Gestão de usuários e lojas
- Configuração de comissões

### ⭐ Stellar/NFT
- Tokenização de relógios
- Transferências seguras
- Contratos de escrow
- Histórico blockchain

## 🧪 Testes

```bash
# Executar testes específicos
python tests/teste_usuario_completo.py
python tests/teste_loja_completo_novo.py
python tests/teste_avaliacao_completa.py
python tests/teste_admin_completo_final.py
python tests/teste_revenda_completa_v2.py

# Análise de cobertura
python tests/analise_cobertura.py
```

## 📡 API Endpoints

- **Auth**: `/auth/login`, `/auth/register`
- **Relógios**: `/watches/`, `/watches/marketplace`
- **Avaliações**: `/evaluations/request`, `/evaluations/complete`
- **Admin**: `/admin/dashboard`, `/admin/users`
- **Stellar**: `/stellar/nft/create`, `/stellar/escrow/`
- **Pagamentos**: `/payments/process`, `/payments/history`

## 🌟 Arquitetura

```
app/
├── main.py          # FastAPI app principal
├── models.py        # Modelos SQLAlchemy
├── schemas.py       # Schemas Pydantic
├── auth.py          # Autenticação JWT
├── stellar.py       # Integração Stellar
├── database.py      # Configuração DB
└── routers/         # Endpoints organizados
    ├── auth.py
    ├── watches.py
    ├── evaluations.py
    ├── admin.py
    ├── payments.py
    ├── resell.py
    └── stellar_contracts.py
```

## 📄 Licença

Este projeto é propriedade privada. Todos os direitos reservados.

---

**Status**: ✅ Produção Ready  
**Cobertura de Testes**: 85%+  
**Última Atualização**: Agosto 2025
