"""
Sistema de IA com LangChain + LangGraph
Agentes especializados para nutrição
"""

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from pydantic import BaseModel, Field
import json
import os
import logging
import base64
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Carregar .env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# ============================================
# CONFIGURAÇÃO - GROQ
# ============================================

# Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    logger.warning("⚠️ GROQ_API_KEY não configurada no .env!")
else:
    logger.info(f"✅ GROQ_API_KEY configurada (primeiros 10 chars: {GROQ_API_KEY[:10]}...)")

# Modelos Groq
# Modelos atualizados (llama-3.1-70b-versatile foi descontinuado)
GROQ_MODEL_TEXT = "llama-3.1-8b-instant"  # Modelo rápido e eficiente para texto
GROQ_MODEL_VISION = "llama-3.2-11b-vision-preview"  # Modelo com suporte a análise de imagens

# ============================================
# STATE SCHEMAS
# ============================================

class AgentState(TypedDict):
    """Estado compartilhado entre os nós do grafo"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    next_action: Optional[str]

class MealAnalysisResult(BaseModel):
    """Schema para análise de refeição"""
    itens: List[str] = Field(description="Lista de alimentos identificados")
    porcoes: Dict[str, str] = Field(description="Porções estimadas")
    macros: Dict[str, float] = Field(description="Macronutrientes em gramas")
    calorias_estimadas: int = Field(description="Calorias totais estimadas")
    feedback: str = Field(description="Feedback motivador")
    sugestoes: List[str] = Field(description="Sugestões de melhoria")
    alinhamento_plano: str = Field(description="excelente, bom ou atencao")

class CheckInAnalysisResult(BaseModel):
    """Schema para análise de check-in"""
    pontos_fortes: List[str] = Field(description="O que está indo bem")
    areas_atencao: List[str] = Field(description="O que precisa melhorar")
    tendencias: Dict[str, str] = Field(description="Tendências identificadas")
    sugestoes: List[str] = Field(description="Sugestões práticas")
    mensagem_motivacional: str = Field(description="Mensagem de apoio")
    alerta_nutricionista: bool = Field(description="Se deve alertar o nutricionista")
    motivo_alerta: Optional[str] = Field(description="Motivo do alerta se houver")

class ConsultaInsight(BaseModel):
    """Schema para insights de consulta"""
    resumo_progresso: str = Field(description="Resumo do progresso do paciente")
    principais_conquistas: List[str] = Field(description="Conquistas desde última consulta")
    desafios_identificados: List[str] = Field(description="Desafios observados")
    recomendacoes_plano: List[str] = Field(description="Sugestões para o plano")
    metas_sugeridas: List[Dict[str, Any]] = Field(description="Metas sugeridas")
    pontos_atencao: List[str] = Field(description="Pontos que precisam de atenção")

# ============================================
# LLM FACTORY
# ============================================

def get_llm(model: str = None, temperature: float = 0.7) -> ChatGroq:
    """Factory para criar instâncias do LLM usando Groq"""
    if not GROQ_API_KEY:
        logger.warning("⚠️ GROQ_API_KEY não configurada!")
        return None
    
    return ChatGroq(
        model=model or GROQ_MODEL_TEXT,
        groq_api_key=GROQ_API_KEY,
        temperature=temperature
    )

# ============================================
# PROMPTS ESPECIALIZADOS
# ============================================

MEAL_ANALYSIS_PROMPT = """Você é Nuttro IA, um nutricionista virtual especializado em análise de refeições.
Analise a refeição descrita pelo usuário com MÁXIMA PRECISÃO e atenção aos detalhes.

CONTEXTO DO PACIENTE:
{patient_context}

PLANO ALIMENTAR ATUAL:
{meal_plan}

DESCRIÇÃO DA REFEIÇÃO FORNECIDA PELO USUÁRIO:
{descricao_refeicao}

INSTRUÇÕES CRÍTICAS:
1. Analise EXATAMENTE o que o usuário descreveu - não invente alimentos que não foram mencionados
2. Identifique TODOS os alimentos mencionados na descrição acima
3. Estime porções realistas baseado em tamanhos padrão brasileiros:
   - Arroz branco cozido: 1 concha média = ~150g = ~200 calorias, 45g carboidratos, 4g proteína
   - Ovo: 1 unidade média = ~60g = ~90 calorias, 6g proteína, 6g gordura
   - Frango grelhado: 1 filé médio = ~100g = ~165 calorias, 31g proteína, 3.6g gordura
   - Feijão cozido: 1 concha = ~100g = ~130 calorias, 8g proteína, 23g carboidratos
   - Salada: 1 prato raso = ~100g = ~20-50 calorias (dependendo do tipo)
4. Calcule macros em GRAMAS com precisão baseado nos alimentos identificados
5. Estime calorias totais somando todos os alimentos
6. Avalie alinhamento com o objetivo do paciente:
   - Se objetivo é "perda de peso": verifique se está dentro das calorias recomendadas
   - Se objetivo é "ganho de massa": verifique proteína suficiente
   - Se objetivo é "manutenção": verifique equilíbrio nutricional
7. Dê feedback ESPECÍFICO sobre a refeição descrita, não genérico
8. Sugira melhorias práticas baseadas no que foi realmente consumido

IMPORTANTE:
- NÃO invente alimentos que não foram mencionados
- Se o usuário disse "arroz com ovo", analise APENAS arroz e ovo
- Use valores nutricionais médios brasileiros para cada alimento
- Seja específico: "Esta refeição de arroz com ovo fornece..." não "Uma refeição balanceada..."
- Considere o objetivo do paciente ao avaliar
- Seja positivo mas realista

Responda APENAS em JSON válido, sem markdown, sem explicações, com a estrutura:
{{
    "itens": ["lista EXATA de alimentos mencionados na descrição"],
    "porcoes": {{"alimento": "porção estimada (ex: 1 concha, 100g, 1 unidade)"}},
    "macros": {{"proteinas_g": 0.0, "carboidratos_g": 0.0, "gorduras_g": 0.0, "fibras_g": 0.0}},
    "calorias_estimadas": 0,
    "feedback": "feedback ESPECÍFICO sobre esta refeição específica, mencionando os alimentos reais",
    "sugestoes": ["sugestões práticas baseadas nos alimentos realmente consumidos"],
    "alinhamento_plano": "excelente|bom|atencao"
}}"""

PATIENT_CHAT_PROMPT = """Você é Nuttro IA, um coach de nutrição virtual amigável e motivador.

CONTEXTO DO PACIENTE:
- Nome: {nome}
- Objetivo: {objetivo}
- Dias na jornada: {dias_jornada}
- Nível de adesão: {nivel_adesao}
- Última consulta: {ultima_consulta}
- Metas ativas: {metas}

HISTÓRICO RECENTE:
- Check-ins: {checkins_resumo}
- Refeições: {refeicoes_resumo}

PERSONALIDADE:
- Seja empático, motivador e positivo
- Use linguagem clara e acessível
- Celebre conquistas
- Ofereça apoio em dificuldades
- Dê sugestões práticas
- Seja breve (máximo 3 parágrafos)

FUNÇÕES:
1. Responder dúvidas sobre nutrição
2. Motivar a seguir o plano
3. Oferecer sugestões práticas
4. Fornecer apoio emocional
5. Analisar padrões comportamentais

NÃO FAÇA:
- Diagnósticos médicos
- Promessas irrealistas
- Críticas severas
- Substituir o nutricionista

Responda em português do Brasil."""

CHECKIN_ANALYSIS_PROMPT = """Você é um analista de dados nutricionais especializado.
Analise os check-ins do paciente para identificar padrões e gerar insights.

DADOS DO PACIENTE:
{patient_info}

CHECK-INS RECENTES (últimos 7-30 dias):
{checkins_data}

METAS ATUAIS:
{metas}

Analise:
1. Tendências nos indicadores (melhorando, estável, piorando)
2. Padrões comportamentais
3. Correlações entre métricas
4. Progresso em relação às metas
5. Se há sinais de alerta que precisam de atenção do nutricionista

Responda em JSON com:
{{
    "pontos_fortes": ["lista"],
    "areas_atencao": ["lista"],
    "tendencias": {{"metrica": "melhorando|estavel|piorando"}},
    "sugestoes": ["lista de sugestões práticas"],
    "mensagem_motivacional": "mensagem de apoio",
    "alerta_nutricionista": true/false,
    "motivo_alerta": "motivo se houver"
}}"""

CONSULTA_INSIGHT_PROMPT = """Você é um assistente de IA especializado para nutricionistas.
Prepare insights DETALHADOS e ESPECÍFICOS para auxiliar na próxima consulta deste paciente específico.

DADOS DO PACIENTE:
{patient_info}

HISTÓRICO DE CHECK-INS:
{checkins_summary}

HISTÓRICO DE REFEIÇÕES:
{meals_summary}

METAS E PROGRESSO:
{goals_progress}

ÚLTIMA CONSULTA:
{last_consultation}

INSTRUÇÕES CRÍTICAS:
1. Analise os dados ESPECÍFICOS deste paciente - não dê respostas genéricas
2. Identifique padrões reais nos dados fornecidos (check-ins, refeições, metas)
3. Compare o progresso atual com a última consulta registrada
4. Seja específico: mencione números, datas, tendências reais
5. Baseie suas recomendações nos dados reais, não em suposições
6. Se não houver dados suficientes, indique isso claramente

Gere insights ESPECÍFICOS para este paciente:
1. Resumo do progresso desde a última consulta (com números e datas específicas)
2. Principais conquistas do paciente (baseadas nos dados reais)
3. Desafios identificados nos dados (padrões observados, não genéricos)
4. Recomendações para ajustar o plano (baseadas no objetivo e progresso real)
5. Sugestões de novas metas (alinhadas com o objetivo e histórico)
6. Pontos que precisam de atenção especial (alertas baseados em dados)

IMPORTANTE:
- NÃO use frases genéricas como "o paciente está progredindo bem"
- Use dados específicos: "o paciente perdeu 2kg desde a última consulta em [data]"
- Mencione alimentos específicos que aparecem nas refeições
- Cite métricas reais dos check-ins
- Seja prático e acionável

Responda APENAS em JSON válido, sem markdown, com a estrutura:
{{
    "resumo_progresso": "resumo específico com números e datas",
    "principais_conquistas": ["conquistas específicas baseadas em dados reais"],
    "desafios_identificados": ["desafios específicos observados nos dados"],
    "recomendacoes_plano": ["recomendações práticas baseadas no objetivo e progresso"],
    "metas_sugeridas": [{{"meta": "nome", "prazo": "prazo", "motivo": "motivo baseado em dados"}}],
    "pontos_atencao": ["pontos específicos que precisam de atenção"]
}}"""

# ============================================
# AGENTE DE ANÁLISE DE REFEIÇÕES
# ============================================

class MealAnalysisAgent:
    """Agente para análise de refeições com visão"""
    
    def __init__(self):
        self.llm = get_llm(temperature=0.3)
        self.parser = JsonOutputParser(pydantic_object=MealAnalysisResult)
    
    async def _describe_image_with_vision(self, image_base64: str) -> str:
        """Usa modelo de visão do Groq para descrever a imagem de alimentos"""
        try:
            # Limpar base64 - remover prefixo data:image se presente
            if 'base64,' in image_base64:
                image_base64 = image_base64.split('base64,')[1]
            
            # Verificar se temos a API key
            if not GROQ_API_KEY:
                logger.warning("⚠️ GROQ_API_KEY não configurada para análise de visão")
                return "Imagem não pôde ser analisada - API key não configurada"
            
            # Usar modelo de visão do Groq
            try:
                vision_llm = ChatGroq(
                    model=GROQ_MODEL_VISION,
                    groq_api_key=GROQ_API_KEY,
                    temperature=0.3
                )
                
                # Criar mensagem com imagem no formato multimodal
                vision_prompt = """Você é um especialista em nutrição. Analise esta foto de refeição e descreva:

1. TODOS os alimentos visíveis na imagem (seja específico: arroz branco, feijão preto, frango grelhado, etc.)
2. Porções aproximadas (pouco, médio, bastante)
3. Método de preparo visível (grelhado, frito, cozido, cru)

Responda de forma direta e objetiva, listando os alimentos encontrados.
Exemplo: "Arroz branco (porção média), feijão carioca (1 concha), frango grelhado (1 filé médio), salada de alface e tomate"

Se não conseguir identificar alimentos ou a imagem não for de comida, diga claramente."""
                
                message = HumanMessage(content=[
                    {"type": "text", "text": vision_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ])
                
                logger.info(f"🔍 Analisando imagem com modelo de visão {GROQ_MODEL_VISION}...")
                response = await vision_llm.ainvoke([message])
                
                description = response.content.strip()
                logger.info(f"✅ Descrição da imagem: {description[:200]}...")
                
                return description
                
            except Exception as e:
                logger.error(f"Erro ao usar modelo de visão Groq: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return "Não foi possível analisar a imagem automaticamente. Por favor, descreva os alimentos."
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem: {e}")
            return "Erro ao processar imagem"
    
    async def analyze(
        self, 
        image_base64: str, 
        patient_context: Dict, 
        meal_plan: Dict = None,
        descricao: str = None
    ) -> Dict[str, Any]:
        """Analisa uma refeição usando descrição textual ou imagem"""
        
        if not self.llm:
            return self._fallback_response()
        
        try:
            # Preparar contexto
            context_str = json.dumps(patient_context, ensure_ascii=False, indent=2) if patient_context else "Sem contexto do paciente"
            plan_str = json.dumps(meal_plan or {}, ensure_ascii=False, indent=2) if meal_plan else "Sem plano alimentar definido"
            
            # Priorizar descrição textual se fornecida
            if descricao and descricao.strip():
                descricao_refeicao = descricao.strip()
                logger.info(f"📝 Analisando refeição por descrição textual: {descricao_refeicao[:100]}...")
            elif image_base64:
                # Gerar descrição da imagem (em produção, use uma API de visão real)
                descricao_refeicao = await self._describe_image_with_vision(image_base64)
                logger.info(f"📷 Analisando refeição por imagem")
            else:
                logger.warning("⚠️ Nenhuma descrição ou imagem fornecida")
                return self._fallback_response()
            
            # Criar prompt completo com descrição
            prompt = MEAL_ANALYSIS_PROMPT.format(
                patient_context=context_str,
                meal_plan=plan_str,
                descricao_refeicao=descricao_refeicao
            )
            
            message = HumanMessage(content=prompt)
            response = await self.llm.ainvoke([message])
            
            # Parse da resposta
            content = response.content.strip()
            
            # Remover markdown se presente
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content
                if content.endswith('```'):
                    content = content.rsplit('\n', 1)[0]
            
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse JSON na análise de refeição: {e}")
            logger.error(f"Resposta recebida: {response.content[:500] if 'response' in locals() else 'N/A'}")
            # Tentar extrair JSON da resposta
            try:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
            except:
                pass
            return self._fallback_response()
        except Exception as e:
            logger.error(f"Erro na análise de refeição: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_response()
    
    def _fallback_response(self) -> Dict:
        return {
            "itens": ["Não foi possível analisar"],
            "porcoes": {},
            "macros": {"proteinas_g": 0, "carboidratos_g": 0, "gorduras_g": 0, "fibras_g": 0},
            "calorias_estimadas": 0,
            "feedback": "Não consegui analisar esta imagem. Tente uma foto mais clara!",
            "sugestoes": ["Tire fotos com boa iluminação"],
            "alinhamento_plano": "atencao"
        }

# ============================================
# AGENTE DE CHAT COM PACIENTE (LangGraph)
# ============================================

class PatientChatAgent:
    """Agente de chat usando LangGraph para conversas contextuais"""
    
    def __init__(self):
        # Temperature reduzida para respostas mais consistentes
        self.llm = get_llm(temperature=0.4)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Constrói o grafo de conversação"""
        
        # Definir nós
        async def understand_intent(state: AgentState) -> AgentState:
            """Entende a intenção do usuário"""
            # Analisar última mensagem para classificar intenção
            last_msg = state["messages"][-1].content if state["messages"] else ""
            
            intents = ["duvida_nutricional", "motivacao", "relato_dificuldade", "duvida_plano", "outro"]
            # Por simplicidade, vamos direto para resposta
            state["next_action"] = "generate_response"
            return state
        
        async def generate_response(state: AgentState) -> AgentState:
            """Gera resposta contextualizada"""
            if not self.llm:
                state["result"] = {"response": "IA não disponível no momento."}
                return state
            
            try:
                context = state.get("context", {})
                
                system_prompt = PATIENT_CHAT_PROMPT.format(
                    nome=context.get("nome", "Paciente"),
                    objetivo=context.get("objetivo", "não definido"),
                    dias_jornada=context.get("dias_jornada", 0),
                    nivel_adesao=context.get("nivel_adesao", "média"),
                    ultima_consulta=context.get("ultima_consulta", "não registrada"),
                    metas=json.dumps(context.get("metas", []), ensure_ascii=False),
                    checkins_resumo=context.get("checkins_resumo", "sem dados"),
                    refeicoes_resumo=context.get("refeicoes_resumo", "sem dados")
                )
                
                messages = [SystemMessage(content=system_prompt)]
                
                # Adicionar histórico
                for msg in state["messages"]:
                    if isinstance(msg, HumanMessage):
                        messages.append(msg)
                    elif isinstance(msg, AIMessage):
                        messages.append(msg)
                
                response = await self.llm.ainvoke(messages)
                state["result"] = {"response": response.content}
                
            except Exception as e:
                logger.error(f"Erro no chat: {e}")
                state["result"] = {"response": "Desculpe, tive um problema. Tente novamente!"}
            
            return state
        
        # Construir grafo
        workflow = StateGraph(AgentState)
        
        # Adicionar nós
        workflow.add_node("understand", understand_intent)
        workflow.add_node("respond", generate_response)
        
        # Adicionar arestas
        workflow.add_edge(START, "understand")
        workflow.add_edge("understand", "respond")
        workflow.add_edge("respond", END)
        
        return workflow.compile()
    
    async def chat(
        self, 
        message: str, 
        patient_context: Dict, 
        chat_history: List[Dict] = None
    ) -> str:
        """Processa uma mensagem do paciente"""
        
        if not self.llm:
            return "Chat não disponível. Configure a API key."
        
        # Preparar histórico
        messages = []
        for msg in (chat_history or [])[-10:]:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        
        # Adicionar mensagem atual
        messages.append(HumanMessage(content=message))
        
        # Estado inicial
        initial_state = {
            "messages": messages,
            "context": patient_context,
            "result": None,
            "next_action": None
        }
        
        # Executar grafo
        final_state = await self.graph.ainvoke(initial_state)
        
        return final_state.get("result", {}).get("response", "Erro ao processar mensagem.")

# ============================================
# AGENTE DE ANÁLISE DE CHECK-INS
# ============================================

class CheckInAnalysisAgent:
    """Agente para análise de padrões em check-ins"""
    
    def __init__(self):
        self.llm = get_llm(temperature=0.4)
    
    async def analyze(
        self, 
        checkins: List[Dict], 
        patient_info: Dict, 
        metas: List[Dict] = None
    ) -> Dict[str, Any]:
        """Analisa padrões nos check-ins"""
        
        if not self.llm or not checkins:
            return self._fallback_response()
        
        try:
            prompt = CHECKIN_ANALYSIS_PROMPT.format(
                patient_info=json.dumps(patient_info, ensure_ascii=False, indent=2),
                checkins_data=json.dumps(checkins, ensure_ascii=False, indent=2),
                metas=json.dumps(metas or [], ensure_ascii=False, indent=2)
            )
            
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            content = response.content.strip()
            if content.startswith('```'):
                content = content.split('\n', 1)[1]
                if content.endswith('```'):
                    content = content.rsplit('\n', 1)[0]
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Erro na análise de check-ins: {e}")
            return self._fallback_response()
    
    def _fallback_response(self) -> Dict:
        return {
            "pontos_fortes": ["Continue registrando seus check-ins!"],
            "areas_atencao": [],
            "tendencias": {},
            "sugestoes": ["Mantenha a constância nos registros"],
            "mensagem_motivacional": "Cada dia é uma nova oportunidade!",
            "alerta_nutricionista": False,
            "motivo_alerta": None
        }

# ============================================
# AGENTE DE INSIGHTS PARA CONSULTAS
# ============================================

class ConsultaInsightAgent:
    """Agente para gerar insights para o nutricionista"""
    
    def __init__(self):
        self.llm = get_llm(temperature=0.5)
    
    async def generate_insights(
        self,
        patient_info: Dict,
        checkins: List[Dict],
        meals: List[Dict],
        goals: List[Dict],
        last_consultation: Dict = None
    ) -> Dict[str, Any]:
        """Gera insights ESPECÍFICOS para auxiliar na consulta deste paciente"""
        
        if not self.llm:
            return self._fallback_response()
        
        try:
            # Preparar dados detalhados (não apenas resumos)
            patient_info_str = json.dumps(patient_info, ensure_ascii=False, indent=2)
            
            # Resumir check-ins mas manter detalhes importantes
            checkins_summary = self._summarize_checkins(checkins)
            if checkins:
                # Adicionar informações sobre os últimos check-ins
                ultimos_checkins = checkins[-5:] if len(checkins) > 5 else checkins
                checkins_summary += f"\n\nÚltimos check-ins detalhados:\n{json.dumps(ultimos_checkins, ensure_ascii=False, indent=2)}"
            
            # Resumir refeições mas manter detalhes das últimas
            meals_summary = self._summarize_meals(meals)
            if meals:
                # Adicionar informações sobre as últimas refeições
                ultimas_refeicoes = meals[-10:] if len(meals) > 10 else meals
                refeicoes_detalhadas = []
                for meal in ultimas_refeicoes:
                    refeicoes_detalhadas.append({
                        "data": meal.get("data"),
                        "itens": meal.get("itens", []),
                        "calorias": meal.get("calorias_estimadas"),
                        "alinhamento": meal.get("alinhamento_plano")
                    })
                meals_summary += f"\n\nÚltimas refeições detalhadas:\n{json.dumps(refeicoes_detalhadas, ensure_ascii=False, indent=2)}"
            
            # Resumir metas mas manter detalhes
            goals_progress = self._summarize_goals(goals)
            if goals:
                goals_progress += f"\n\nMetas detalhadas:\n{json.dumps(goals, ensure_ascii=False, indent=2)}"
            
            prompt = CONSULTA_INSIGHT_PROMPT.format(
                patient_info=patient_info_str,
                checkins_summary=checkins_summary,
                meals_summary=meals_summary,
                goals_progress=goals_progress,
                last_consultation=json.dumps(last_consultation or {}, ensure_ascii=False, indent=2)
            )
            
            logger.info(f"📊 Gerando insights para paciente: {patient_info.get('nome', 'N/A')}")
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            content = response.content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.split('\n', 1)[1] if '\n' in content else content
                if content.endswith('```'):
                    content = content.rsplit('\n', 1)[0]
            
            result = json.loads(content)
            logger.info(f"✅ Insights gerados com sucesso")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao fazer parse JSON nos insights: {e}")
            logger.error(f"Resposta recebida: {response.content[:500] if 'response' in locals() else 'N/A'}")
            return self._fallback_response()
        except Exception as e:
            logger.error(f"Erro ao gerar insights: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_response()
    
    def _summarize_checkins(self, checkins: List[Dict]) -> str:
        if not checkins:
            return "Sem check-ins registrados"
        
        # Calcular médias
        metrics = ['consistencia_plano', 'frequencia_refeicoes', 'vegetais_frutas', 
                   'ingestao_liquido', 'energia_fisica', 'qualidade_sono']
        
        summary = {}
        for metric in metrics:
            values = [c.get(metric, 0) for c in checkins if c.get(metric)]
            if values:
                summary[metric] = round(sum(values) / len(values), 1)
        
        return json.dumps(summary, ensure_ascii=False)
    
    def _summarize_meals(self, meals: List[Dict]) -> str:
        if not meals:
            return "Sem refeições registradas"
        
        total_calorias = sum(m.get('calorias_estimadas', 0) for m in meals)
        alinhamentos = [m.get('alinhamento_plano', 'atencao') for m in meals]
        
        return json.dumps({
            "total_refeicoes": len(meals),
            "calorias_media": round(total_calorias / len(meals)) if meals else 0,
            "alinhamento_excelente": alinhamentos.count('excelente'),
            "alinhamento_bom": alinhamentos.count('bom'),
            "alinhamento_atencao": alinhamentos.count('atencao')
        }, ensure_ascii=False)
    
    def _summarize_goals(self, goals: List[Dict]) -> str:
        if not goals:
            return "Sem metas definidas"
        
        return json.dumps({
            "total": len(goals),
            "ativas": len([g for g in goals if g.get('status') == 'ativa']),
            "concluidas": len([g for g in goals if g.get('status') == 'concluida']),
            "progresso_medio": round(sum(g.get('progresso_percentual', 0) for g in goals) / len(goals))
        }, ensure_ascii=False)
    
    def _fallback_response(self) -> Dict:
        return {
            "resumo_progresso": "Dados insuficientes para análise",
            "principais_conquistas": [],
            "desafios_identificados": [],
            "recomendacoes_plano": ["Coletar mais dados do paciente"],
            "metas_sugeridas": [],
            "pontos_atencao": []
        }

# ============================================
# FACTORY PARA AGENTES
# ============================================

_meal_agent = None
_chat_agent = None
_checkin_agent = None
_consulta_agent = None

def get_meal_analysis_agent() -> MealAnalysisAgent:
    global _meal_agent
    if _meal_agent is None:
        _meal_agent = MealAnalysisAgent()
    return _meal_agent

def get_patient_chat_agent() -> PatientChatAgent:
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = PatientChatAgent()
    return _chat_agent

def get_checkin_analysis_agent() -> CheckInAnalysisAgent:
    global _checkin_agent
    if _checkin_agent is None:
        _checkin_agent = CheckInAnalysisAgent()
    return _checkin_agent

def get_consulta_insight_agent() -> ConsultaInsightAgent:
    global _consulta_agent
    if _consulta_agent is None:
        _consulta_agent = ConsultaInsightAgent()
    return _consulta_agent

# ============================================
# AGENTE DE GERAÇÃO DE PLANO ALIMENTAR
# ============================================

class MealPlanGenerationAgent:
    """Agente para gerar planos alimentares completos usando IA"""
    
    def __init__(self):
        self.llm = get_llm(temperature=0.7)
    
    async def generate_meal_plan(
        self,
        paciente_info: Dict,
        consulta_data: Dict,
        objetivo: str,
        restricoes: List[str] = None
    ) -> Dict[str, Any]:
        """Gera um plano alimentar completo e personalizado"""
        
        if not self.llm:
            logger.warning("⚠️ LLM não disponível, retornando plano básico")
            return self._fallback_response(objetivo)
        
        try:
            # Calcular IMC
            peso = consulta_data.get('avaliacao_fisica', {}).get('peso') or consulta_data.get('avaliacao_fisica', {}).get('peso_kg') or paciente_info.get('peso_atual_kg', 70)
            altura_cm = consulta_data.get('avaliacao_fisica', {}).get('altura') or consulta_data.get('avaliacao_fisica', {}).get('altura_cm') or paciente_info.get('altura_cm', 170)
            altura_m = altura_cm / 100 if altura_cm > 10 else altura_cm
            imc = peso / (altura_m ** 2) if altura_m > 0 else 0
            
            # Calcular idade
            data_nasc = paciente_info.get('data_nascimento')
            if data_nasc:
                try:
                    from datetime import datetime
                    nasc = datetime.fromisoformat(data_nasc.replace('Z', '+00:00'))
                    idade = (datetime.now(timezone.utc) - nasc).days // 365
                except:
                    idade = 30
            else:
                idade = 30
            
            # Preparar prompt
            prompt = MEAL_PLAN_GENERATION_PROMPT.format(
                nome=paciente_info.get('nome', 'Paciente'),
                idade=idade,
                peso_atual=peso,
                altura=altura_cm,
                imc=round(imc, 1),
                objetivo=objetivo,
                profissao=paciente_info.get('profissao', 'Não informado'),
                atividade_fisica=consulta_data.get('avaliacao_fisica', {}).get('atividade_fisica', 'Sedentária'),
                restricoes=', '.join(restricoes) if restricoes else 'Nenhuma',
                historico_saude=json.dumps(consulta_data.get('anamnese', {}), ensure_ascii=False),
                anamnese=json.dumps(consulta_data.get('anamnese', {}), ensure_ascii=False, indent=2),
                avaliacao_fisica=json.dumps(consulta_data.get('avaliacao_fisica', {}), ensure_ascii=False, indent=2),
                avaliacao_emocional=json.dumps(consulta_data.get('avaliacao_emocional', {}), ensure_ascii=False, indent=2),
                avaliacao_comportamental=json.dumps(consulta_data.get('avaliacao_comportamental', {}), ensure_ascii=False, indent=2),
                avaliacao_bem_estar=json.dumps(consulta_data.get('avaliacao_bem_estar', {}), ensure_ascii=False, indent=2)
            )
            
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            
            content = response.content.strip()
            # Limpar markdown code blocks se houver
            if content.startswith('```'):
                lines = content.split('\n')
                content = '\n'.join(lines[1:-1]) if content.endswith('```') else '\n'.join(lines[1:])
            
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear JSON da IA: {e}")
            logger.error(f"Resposta recebida: {content[:500]}")
            return self._fallback_response(objetivo)
        except Exception as e:
            logger.error(f"Erro ao gerar plano alimentar: {e}")
            return self._fallback_response(objetivo)
    
    def _fallback_response(self, objetivo: str) -> Dict:
        """Resposta fallback caso a IA não esteja disponível"""
        return {
            "calorias_diarias": 1800,
            "macros": {
                "proteinas_g": 135,
                "carboidratos_g": 180,
                "gorduras_g": 60,
                "fibras_g": 25
            },
            "refeicoes": [
                {
                    "tipo": "Café da manhã",
                    "horario": "07:00",
                    "alimentos": [
                        {"nome": "Aveia", "quantidade": "40g", "calorias": 150},
                        {"nome": "Banana", "quantidade": "1 unidade média", "calorias": 90},
                        {"nome": "Leite desnatado", "quantidade": "200ml", "calorias": 70}
                    ],
                    "total_calorias": 310,
                    "observacoes": "Preparar com água morna"
                }
            ],
            "orientacoes_gerais": [
                "Beba pelo menos 2 litros de água por dia",
                "Faça as refeições em horários regulares",
                "Mastigue bem os alimentos"
            ],
            "hidratacao": {
                "quantidade_ml": 2000,
                "dicas": ["Beba água ao longo do dia", "Evite beber durante as refeições"]
            },
            "suplementacao": {
                "recomendada": False,
                "itens": []
            },
            "proxima_consulta_dias": 15,
            "proxima_consulta_justificativa": "Acompanhamento inicial para avaliar adesão ao plano"
        }

_meal_plan_agent = None

def get_meal_plan_agent() -> MealPlanGenerationAgent:
    global _meal_plan_agent
    if _meal_plan_agent is None:
        _meal_plan_agent = MealPlanGenerationAgent()
    return _meal_plan_agent

