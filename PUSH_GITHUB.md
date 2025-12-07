# 🔐 Como fazer Push para GitHub de Outra Conta

## Método 1: Personal Access Token (Recomendado)

### 1. Criar Personal Access Token na conta do repositório

1. Acesse: https://github.com/settings/tokens (na conta onde criou o repositório)
2. Clique em **Generate new token** → **Generate new token (classic)**
3. Configure:
   - **Note**: `Nuttro Backend Deploy`
   - **Expiration**: Escolha o tempo (ou `No expiration`)
   - **Scopes**: Marque `repo` (acesso completo aos repositórios)
4. Clique em **Generate token**
5. **COPIE O TOKEN** (você só verá uma vez!)

### 2. Fazer Push com Token

Use o token como senha quando pedir credenciais:

```bash
git push -u origin main
```

Quando pedir:
- **Username**: O nome de usuário da conta do GitHub onde criou o repositório
- **Password**: Cole o Personal Access Token (não a senha da conta!)

## Método 2: Incluir Token na URL (Mais Rápido)

Você pode incluir o token diretamente na URL do remote:

```bash
# Remover remote atual
git remote remove origin

# Adicionar com token na URL
git remote add origin https://SEU_TOKEN@github.com/nuttroadm/backendnuttro.git

# Fazer push
git push -u origin main
```

**⚠️ ATENÇÃO**: Este método deixa o token visível no histórico do Git. Use apenas temporariamente e remova depois.

## Método 3: Configurar Credenciais Temporárias

```bash
# Configurar credenciais apenas para este repositório
git config credential.helper store

# Fazer push (vai pedir credenciais uma vez)
git push -u origin main
# Username: nome-da-conta-github
# Password: personal-access-token
```

## Método 4: SSH (Mais Seguro - Requer Configuração)

Se você tem acesso SSH à outra conta:

1. Adicionar chave SSH na outra conta do GitHub
2. Mudar remote para SSH:
```bash
git remote set-url origin git@github.com:nuttroadm/backendnuttro.git
git push -u origin main
```

## 🔒 Segurança

- **NUNCA** commite tokens no código
- Use tokens com escopo mínimo necessário
- Revogue tokens antigos regularmente
- Para produção, use secrets do Render/GitHub Actions

## ✅ Verificação

Após o push, verifique em:
https://github.com/nuttroadm/backendnuttro

