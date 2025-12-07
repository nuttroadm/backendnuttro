# 🔐 Variáveis de Ambiente - Render

## 📋 Lista Completa de Variáveis

### ✅ OBRIGATÓRIAS

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão PostgreSQL | `postgresql+asyncpg://user:pass@host:port/db` |
| `SECRET_KEY` | Chave secreta para JWT | `openssl rand -hex 32` |
| `GEMINI_API_KEY` | Chave API do Google Gemini | `AIza...` |

### ⚙️ OPCIONAIS (mas recomendadas)

| Variável | Descrição | Valor Padrão |
|----------|-----------|--------------|
| `EVOLUTION_API_URL` | URL da Evolution API (WhatsApp) | `https://orderlymanatee-evolution.cloudfy.live` |
| `EVOLUTION_API_KEY` | Chave da Evolution API | - |
| `GOOGLE_CLIENT_ID` | Client ID do Google OAuth | - |
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiração do token (min) | `1440` (24h) |
| `ENVIRONMENT` | Ambiente (dev/prod) | `production` |
| `ALLOWED_ORIGINS` | CORS origins (separados por vírgula) | `*` |
| `PORT` | Porta do servidor | `8000` (Render usa `$PORT`) |

## 🔑 Como Obter as Chaves

### 1. SECRET_KEY
```bash
# Gere uma chave forte:
openssl rand -hex 32
```

### 2. GEMINI_API_KEY
1. Acesse: https://makersuite.google.com/app/apikey
2. Crie um novo projeto ou selecione existente
3. Gere uma nova API key
4. Copie e cole no Render

### 3. EVOLUTION_API_KEY
1. Acesse sua instância Evolution API
2. Vá em Settings → API Keys
3. Crie uma nova chave
4. Copie e cole no Render

### 4. GOOGLE_CLIENT_ID
1. Acesse: https://console.cloud.google.com
2. Crie um projeto ou selecione existente
3. Vá em APIs & Services → Credentials
4. Crie OAuth 2.0 Client ID
5. Copie o Client ID

### 5. DATABASE_URL
- Render fornece automaticamente quando você cria um PostgreSQL
- Vá em Dashboard → Database → Internal Database URL
- Copie a URL completa

## 📝 Configuração no Render

1. Vá em **Dashboard** → **Seu Web Service** → **Environment**
2. Clique em **Add Environment Variable**
3. Adicione cada variável uma por uma
4. Clique em **Save Changes**
5. O serviço será reiniciado automaticamente

## ⚠️ Importante

- **NUNCA** commite arquivos `.env` no Git
- Use valores diferentes para desenvolvimento e produção
- Rotacione `SECRET_KEY` periodicamente em produção
- Mantenha as chaves seguras e não compartilhe

## 🔄 Após Adicionar Variáveis

1. Render reinicia automaticamente
2. Verifique os logs para confirmar que iniciou corretamente
3. Teste a API em `/docs`

