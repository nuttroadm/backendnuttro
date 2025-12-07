# 🚀 Guia de Deploy no Render

Este guia explica como fazer deploy do backend Nuttro no Render.

## 📋 Pré-requisitos

1. Conta no [Render](https://render.com)
2. Banco de dados PostgreSQL (pode criar no Render)
3. Chaves de API configuradas:
   - Gemini API Key (Google)
   - Evolution API (WhatsApp) - opcional

## 🔧 Passo 1: Preparar o Banco de Dados

1. No Render Dashboard, crie um novo **PostgreSQL Database**
2. Anote a **Internal Database URL** (será usada nas variáveis de ambiente)
3. O Render fornece automaticamente a variável `DATABASE_URL`

## 🔧 Passo 2: Criar Web Service

1. No Render Dashboard, clique em **New +** → **Web Service**
2. Conecte seu repositório GitHub/GitLab
3. Configure:
   - **Name**: `nuttro-backend`
   - **Region**: Escolha a mais próxima (ex: Oregon)
   - **Branch**: `main` ou `master`
   - **Root Directory**: `backendsolo`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`

## 🔧 Passo 3: Configurar Variáveis de Ambiente

No Render Dashboard, vá em **Environment** e adicione:

### Obrigatórias:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
SECRET_KEY=sua-chave-secreta-forte-aqui
GEMINI_API_KEY=sua-chave-gemini-aqui
```

### Opcionais (mas recomendadas):

```bash
EVOLUTION_API_URL=https://sua-evolution-api.com
EVOLUTION_API_KEY=sua-chave-evolution
GOOGLE_CLIENT_ID=seu-google-client-id
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENVIRONMENT=production
```

### Gerar SECRET_KEY:

```bash
# No terminal:
openssl rand -hex 32
```

## 🔧 Passo 4: Deploy

1. Render detecta automaticamente mudanças no repositório
2. Ou clique em **Manual Deploy** → **Deploy latest commit**
3. Aguarde o build completar (pode levar 5-10 minutos na primeira vez)

## 🔧 Passo 5: Verificar Deploy

1. Após o deploy, você terá uma URL: `https://nuttro-backend.onrender.com`
2. Teste a API: `https://nuttro-backend.onrender.com/docs`
3. Verifique os logs em **Logs** no dashboard

## 🔧 Passo 6: Configurar App Mobile

1. Atualize `nuttro-react-native-mobile/frontend/app.config.js`:
   ```javascript
   backendUrl: "https://nuttro-backend.onrender.com"
   ```

2. Ou configure via variável de ambiente no build:
   ```bash
   EXPO_PUBLIC_BACKEND_URL=https://nuttro-backend.onrender.com
   ```

3. Rebuild o app:
   ```bash
   eas build --profile production --platform android
   ```

## ⚠️ Importante

- **Auto-Deploy**: Render faz deploy automático a cada push no branch configurado
- **Sleep Mode**: Planos gratuitos entram em sleep após 15min de inatividade (primeira requisição pode demorar)
- **Logs**: Sempre verifique os logs em caso de erro
- **Database Migrations**: Execute manualmente se necessário após o primeiro deploy

## 🔍 Troubleshooting

### Erro de conexão com banco:
- Verifique se `DATABASE_URL` está correta
- Certifique-se que o banco está rodando
- Verifique se o formato é `postgresql+asyncpg://...`

### Erro 500 no servidor:
- Verifique os logs no Render Dashboard
- Confirme que todas as variáveis de ambiente estão configuradas
- Verifique se o `SECRET_KEY` está definido

### Timeout nas requisições:
- Planos gratuitos têm timeout de 30s
- Considere upgrade para planos pagos para maior performance

## 📝 Checklist Final

- [ ] Banco PostgreSQL criado
- [ ] Web Service criado
- [ ] Todas as variáveis de ambiente configuradas
- [ ] Deploy bem-sucedido
- [ ] API respondendo em `/docs`
- [ ] App mobile configurado com URL do Render
- [ ] Testes realizados

## 🔗 Links Úteis

- [Render Docs](https://render.com/docs)
- [Render PostgreSQL](https://render.com/docs/databases)
- [FastAPI Deploy](https://fastapi.tiangolo.com/deployment/)

