# Backend Nuttro

Backend completo para o sistema Nuttro - plataforma de nutrição com IA.

## 🚀 Tecnologias

- **FastAPI** - Framework web assíncrono
- **PostgreSQL** - Banco de dados relacional
- **SQLAlchemy** - ORM
- **LangChain + Gemini** - IA para análise nutricional
- **Socket.IO** - Comunicação em tempo real
- **Evolution API** - Integração WhatsApp

## 📁 Estrutura

```
backendsolo/
├── server.py          # Servidor principal
├── serverweb.py       # Rotas web (nutricionistas)
├── serverapp.py       # Rotas mobile (pacientes)
├── shared.py          # Funções compartilhadas
├── models.py          # Modelos SQLAlchemy
├── database.py        # Configuração do banco
├── ai_agents.py       # Agentes de IA
└── requirements.txt   # Dependências
```

## 🔧 Configuração

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure as variáveis de ambiente (veja `.env.example`)

3. Execute o servidor:
```bash
uvicorn server:socket_app --host 0.0.0.0 --port 8000
```

## 📚 Documentação

- **Deploy no Render**: `DEPLOY_RENDER.md`
- **Variáveis de Ambiente**: `VARIAVEIS_AMBIENTE.md`
- **API Docs**: Acesse `/docs` após iniciar o servidor

## 🔐 Variáveis de Ambiente

Veja `VARIAVEIS_AMBIENTE.md` para lista completa.

Principais:
- `DATABASE_URL` - URL do PostgreSQL
- `SECRET_KEY` - Chave secreta JWT
- `GEMINI_API_KEY` - Chave API do Gemini

## 📝 Licença

Proprietário - Nuttro
