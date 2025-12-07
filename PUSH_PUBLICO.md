# 🚀 Push para Repositório Público - Outra Conta

## ⚠️ Problema: Autenticação

Mesmo sendo público, você precisa estar autenticado na conta `nuttroadm` para fazer push.

## ✅ Solução: Personal Access Token

### 1. Criar Token na Conta nuttroadm

1. Acesse: https://github.com/settings/tokens (na conta nuttroadm)
2. **Generate new token** → **Generate new token (classic)**
3. Configure:
    - Note: `Nuttro Backend`
    - Expiration: `No expiration`
    - Scopes: Marque **`repo`**
 4. **Generate token** e **COPIE** (começa com `ghp_...`)

### 2. Fazer Push com Token

```bash
# Remover remote
git remote remove origin

# Adicionar com token
git remote add origin https://SEU_TOKEN@github.com/nuttroadm/backendnuttro.git

# Push
git push -u origin main
```

**Exemplo:**
```bash
git remote add origin https://ghp_abc123xyz@github.com/nuttroadm/backendnuttro.git
git push -u origin main
```

### 3. Alternativa: Credenciais Interativas

```bash
git push -u origin main
```

Quando pedir:
- **Username**: `nuttroadm`
- **Password**: Cole o **token** (não a senha!)

## 🔗 Link Rápido para Criar Token

https://github.com/settings/tokens/new

