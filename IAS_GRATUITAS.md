# 🤖 IAs Gratuitas para Teste - Alternativas ao Gemini

## ⚠️ Problema Atual

O Gemini 2.0 Flash está com **quota excedida** (429 errors). A conta free tier tem limite muito baixo.

## ✅ Opções Gratuitas Recomendadas

### **1. Groq (Recomendado)** ⭐⭐⭐⭐⭐

**Por quê:**
- ✅ **Totalmente gratuito** (sem cartão de crédito)
- ✅ **Muito rápido** (inferência ultra-rápida)
- ✅ **Sem limites rígidos** (generoso para testes)
- ✅ **Suporta modelos Llama 3, Mixtral, etc.**

**Como usar:**
```python
# Instalar
pip install langchain-groq

# Configurar
from langchain_groq import ChatGroq

llm = ChatGroq(
    groq_api_key="sua-chave",
    model_name="llama-3.1-70b-versatile"  # ou "mixtral-8x7b-32768"
)
```

**Obter chave:** https://console.groq.com/keys

---

### **2. Hugging Face Inference API** ⭐⭐⭐⭐

**Por quê:**
- ✅ **Gratuito** (com limites generosos)
- ✅ **Muitos modelos** disponíveis
- ✅ **Boa qualidade**

**Como usar:**
```python
# Instalar
pip install langchain-huggingface

# Configurar
from langchain_huggingface import ChatHuggingFace

llm = ChatHuggingFace(
    huggingfacehub_api_token="sua-chave",
    repo_id="meta-llama/Llama-3.1-8B-Instruct"
)
```

**Obter chave:** https://huggingface.co/settings/tokens

---

### **3. Together AI** ⭐⭐⭐⭐

**Por quê:**
- ✅ **Créditos gratuitos** ($25 ao se registrar)
- ✅ **Modelos de alta qualidade**
- ✅ **Boa performance**

**Como usar:**
```python
# Instalar
pip install langchain-together

# Configurar
from langchain_together import ChatTogether

llm = ChatTogether(
    together_api_key="sua-chave",
    model="meta-llama/Llama-3-70b-chat-hf"
)
```

**Obter chave:** https://api.together.xyz/settings/api-keys

---

### **4. Ollama (Local)** ⭐⭐⭐

**Por quê:**
- ✅ **100% gratuito** (roda localmente)
- ✅ **Sem limites**
- ✅ **Privacidade total**

**Desvantagens:**
- ⚠️ Requer instalação local
- ⚠️ Pode ser mais lento
- ⚠️ Consome recursos do servidor

**Como usar:**
```python
# Instalar Ollama localmente primeiro
# https://ollama.ai/download

# Depois usar
from langchain_community.llms import Ollama

llm = Ollama(model="llama3")
```

---

### **5. OpenRouter (Free Tier)** ⭐⭐⭐

**Por quê:**
- ✅ **Modelos gratuitos** disponíveis
- ✅ **Fácil integração**
- ✅ **Boa documentação**

**Limitações:**
- ⚠️ Limites de rate
- ⚠️ Alguns modelos são pagos

**Como usar:**
```python
# Já está configurado no código
# Apenas mudar a chave e modelo
```

---

## 🎯 Recomendação Final

**Para testes rápidos:** **Groq** (mais rápido e generoso)

**Para produção futura:** **Together AI** ou **Hugging Face** (mais estável)

---

## 📝 Próximos Passos

1. Escolher uma das opções acima
2. Obter a chave API
3. Atualizar `ai_agents.py` para usar a nova IA
4. Testar funcionalidades

Qual você prefere? Recomendo **Groq** para começar!

