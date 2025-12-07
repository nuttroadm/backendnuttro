# 🔑 Como Criar Personal Access Token no GitHub

## Passo a Passo Rápido

### 1. Acesse a Página de Tokens
Na conta `nuttroadm`, acesse:
**https://github.com/settings/tokens**

### 2. Gerar Novo Token
1. Clique em **"Generate new token"**
2. Selecione **"Generate new token (classic)"**

### 3. Configurar Token
- **Note**: `Nuttro Backend Deploy`
- **Expiration**: Escolha `No expiration` ou um prazo longo
- **Select scopes**: Marque apenas **`repo`** ✅
  - Isso dá acesso completo aos repositórios privados

### 4. Gerar e Copiar
1. Clique em **"Generate token"** no final da página
2. **⚠️ COPIE O TOKEN IMEDIATAMENTE!** 
   - Ele começa com `ghp_`
   - Você só verá uma vez!
   - Exemplo: `ghp_abc123xyz456789...`

### 5. Usar o Token

Depois de copiar, use no comando:

```bash
git remote remove origin
git remote add origin https://SEU_TOKEN_AQUI@github.com/nuttroadm/backendnuttro.git
git push -u origin main
```

**Substitua `SEU_TOKEN_AQUI` pelo token que você copiou!**

## 🔒 Segurança

- ✅ Tokens são mais seguros que senhas
- ✅ Você pode revogar tokens a qualquer momento
- ✅ Tokens têm escopos específicos (apenas `repo` neste caso)
- ⚠️ Não compartilhe o token publicamente

## 🆘 Se Perder o Token

Se você perder o token, simplesmente:
1. Vá em https://github.com/settings/tokens
2. Revogue o token antigo
3. Crie um novo token
4. Use o novo token

