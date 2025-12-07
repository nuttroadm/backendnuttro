# 🚀 Deploy no Render - Resumo Rápido

## 📋 Checklist de Deploy

### 1. Backend no Render

- [ ] Criar PostgreSQL Database no Render
- [ ] Criar Web Service no Render
- [ ] Configurar variáveis de ambiente (veja `VARIAVEIS_AMBIENTE.md`)
- [ ] Fazer deploy
- [ ] Testar API em `https://seu-backend.onrender.com/docs`

### 2. App Mobile

- [ ] Atualizar URL do backend em `app.config.js` ou `eas.json`
- [ ] Fazer build de produção: `eas build --profile production --platform android`
- [ ] Testar app com backend no Render

## 🔑 Variáveis de Ambiente Obrigatórias

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
SECRET_KEY=sua-chave-secreta-gerada
GEMINI_API_KEY=sua-chave-gemini
```

## 📚 Documentação Completa

- **Guia Completo**: `DEPLOY_RENDER.md`
- **Variáveis de Ambiente**: `VARIAVEIS_AMBIENTE.md`
- **Configuração Mobile**: `../nuttro-react-native-mobile/DEPLOY_CONFIG.md`

## 🔗 URLs Importantes

- **Render Dashboard**: https://dashboard.render.com
- **API Docs**: `https://seu-backend.onrender.com/docs`
- **Gemini API**: https://makersuite.google.com/app/apikey

