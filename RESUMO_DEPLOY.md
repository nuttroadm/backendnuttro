# 🚀 Resumo: Deploy no Render

## ✅ O que foi configurado

### Backend
- ✅ `server.py` configurado para usar `$PORT` do Render
- ✅ CORS configurável via variáveis de ambiente
- ✅ `render.yaml` criado para deploy automático
- ✅ `runtime.txt` especificando Python 3.11

### App Mobile
- ✅ `app.config.js` atualizado com URL do Render
- ✅ `eas.json` configurado para produção
- ✅ `utils/api.ts` usando URL do Render como fallback

## 📋 Variáveis de Ambiente Obrigatórias no Render

### 1. DATABASE_URL
- Render fornece automaticamente ao criar PostgreSQL
- Formato: `postgresql+asyncpg://user:pass@host:port/db`

### 2. SECRET_KEY
- Gere com: `openssl rand -hex 32`
- **OBRIGATÓRIO** para segurança JWT

### 3. GEMINI_API_KEY
- Obtenha em: https://makersuite.google.com/app/apikey
- **OBRIGATÓRIO** para funcionalidades de IA

## 📋 Variáveis Opcionais

- `EVOLUTION_API_URL` - URL da Evolution API (WhatsApp)
- `EVOLUTION_API_KEY` - Chave da Evolution API
- `GOOGLE_CLIENT_ID` - Para login com Google
- `ALLOWED_ORIGINS` - CORS (padrão: `*`)

## 🚀 Passos para Deploy

1. **Criar PostgreSQL no Render**
   - Dashboard → New + → PostgreSQL
   - Anotar Internal Database URL

2. **Criar Web Service**
   - Dashboard → New + → Web Service
   - Conectar repositório
   - Root Directory: `backendsolo`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn server:socket_app --host 0.0.0.0 --port $PORT`

3. **Configurar Variáveis**
   - Environment → Add Environment Variable
   - Adicionar: `DATABASE_URL`, `SECRET_KEY`, `GEMINI_API_KEY`
   - Adicionar opcionais se necessário

4. **Deploy**
   - Render faz deploy automático
   - Ou Manual Deploy → Deploy latest commit

5. **Atualizar App Mobile**
   - Editar `app.config.js`: `backendUrl: "https://seu-backend.onrender.com"`
   - Rebuild: `eas build --profile production --platform android`

## 📚 Documentação Completa

- **Guia Detalhado**: `DEPLOY_RENDER.md`
- **Variáveis de Ambiente**: `VARIAVEIS_AMBIENTE.md`
- **Template de Variáveis**: `ENV_TEMPLATE.txt`
- **Config Mobile**: `../nuttro-react-native-mobile/DEPLOY_CONFIG.md`

## 🔗 URLs Após Deploy

- **API**: `https://nuttro-backend.onrender.com`
- **Docs**: `https://nuttro-backend.onrender.com/docs`
- **Health Check**: `https://nuttro-backend.onrender.com/`

## ⚠️ Importante

- Primeira requisição pode demorar (sleep mode em planos gratuitos)
- Verifique logs em caso de erro
- Teste sempre após deploy
- Mantenha variáveis de ambiente seguras

