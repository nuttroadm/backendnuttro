# 🔑 Configurar Groq API Key

## ⚠️ Importante

A chave API do Groq foi removida do código por segurança. Configure-a como variável de ambiente.

## 📝 Configuração

### 1. No Render (Produção)

1. Acesse o dashboard do Render
2. Vá em **Environment** → **Environment Variables**
3. Adicione:
   - **Key:** `GROQ_API_KEY`
   - **Value:** `[sua-chave-groq-aqui]`

### 2. Localmente (.env)

Adicione no arquivo `.env`:

```env
GROQ_API_KEY=[sua-chave-groq-aqui]
```

**Nota:** Obtenha sua chave em: https://console.groq.com/keys

## ✅ Funcionalidades Ativadas

- ✅ Análise de refeições (com descrição textual)
- ✅ Chat com pacientes
- ✅ Análise de check-ins
- ✅ Insights de consultas
- ✅ Geração de planos alimentares

## 🚀 Próximos Passos

Após configurar a chave, o backend estará pronto para usar Groq AI!

