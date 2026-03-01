import os
import json
import logging
from typing import Optional, Dict, Any, List

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from ..config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL
)
from .nlu import LocalNLU
from .knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

# 定义工具 (Tools)
@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the local knowledge base for information about house rules, emergency contacts, wifi passwords, device manuals, or community info.
    Use this tool when the user asks a question that is not a command to open/close something.
    """
    try:
        service = KnowledgeService.get_instance()
        if not service:
            return "知识库服务暂时不可用。"
        return service.get_knowledge_context(query)
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return "查询知识库时发生错误。"

@tool
def open_door(user_name: str = "unknown") -> str:
    """
    Open the door for a specific user.
    Use this tool when the user explicitly asks to open the door.
    """
    logger.info(f"Tool called: open_door for {user_name}")
    # 在实际系统中，这里会调用硬件接口
    return f"已为用户 {user_name} 执行开门操作。"

@tool
def turn_on_light(location: str = "客厅") -> str:
    """
    Turn on the lights in a specific location.
    Use this tool when the user asks to turn on lights.
    """
    logger.info(f"Tool called: turn_on_light in {location}")
    return f"已开启 {location} 的灯光。"

@tool
def alert_police(reason: str = "紧急情况") -> str:
    """
    Call the police or security.
    Use this tool ONLY when there is a clear emergency or threat.
    """
    logger.warning(f"Tool called: alert_police for {reason}")
    return f"已发送紧急报警：{reason}"

class AgentService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL
        self.model_name = DEEPSEEK_MODEL
        
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set. Agent will not function correctly.")
            self.agent_executor = None
            return
        
        try:
            self.llm = ChatOpenAI(
                model=self.model_name,
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
                temperature=0.1  # 降低温度，提高工具调用的稳定性
            )
            
            self.tools = [search_knowledge_base]
            
            # 定义 Prompt
            # System prompt 中包含当前用户信息，以便 Agent 做出决策
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个智能家居安防助手。你仅负责知识库查询与日常问答，不执行开门/报警/开灯等高频指令。"
                           "当前识别到的用户身份: {user_identity} (置信度得分: {confidence})。"
                           "规则："
                           "1. 如果用户询问家庭信息（如WiFi、电话、规定），请调用 search_knowledge_base 工具。"
                           "2. 其他问题请用简体中文直接回答。"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # 创建 Agent
            self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
            self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
            
            # Initialize Local NLU for Hybrid Intelligence
            self.local_nlu = LocalNLU()
            
            logger.info(f"AgentService initialized with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AgentService components: {e}")
            self.agent_executor = None

    @staticmethod
    def _get_verify_threshold() -> float:
        """
        获取本地 NLU 使用的全局阈值。
        优先级：
        1) 通过 Django 后端 /api/threshold/ 读取当前阈值（与前端滑块一致）
        2) 读取环境变量 VOICE_VERIFY_THRESHOLD
        3) 兜底使用 0.70
        """
        # 1) 从 Django 后端读取
        backend_base = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        try:
            url = f"{backend_base}/api/threshold/"
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json() or {}
                v = float(data.get("threshold"))
                if 0.0 < v < 1.0:
                    return v
        except Exception:
            # 后端不可达时静默回退到环境变量逻辑
            pass

        # 2) 环境变量
        try:
            env_val = os.getenv("VOICE_VERIFY_THRESHOLD")
            if env_val is not None:
                v = float(env_val)
                if 0.0 < v < 1.0:
                    return v
        except Exception:
            pass
        # 3) 默认兜底
        return 0.70

    async def process_command(self, text: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理自然语言指令
        :param text: 用户说的文本
        :param user_context: 用户上下文 (身份, 分数等)
        :return: Agent 执行结果
        """
        if self.agent_executor is None:
            return {"status": "error", "message": "Agent not initialized (missing API key?)"}

        if not text or len(text.strip()) < 2:
            return {"status": "ignored", "message": "Text too short"}
            
        user_identity = user_context.get("user", "unknown")
        confidence = float(user_context.get("score", 0.0) or 0.0)

        # === Hybrid Intelligence Strategy ===
        # Step 1: Edge-Side NLU (High Priority, Low Latency, Safety Critical)
        # Check if the intent can be resolved locally without Cloud LLM
        intent_name, slots = self.local_nlu.parse(text)

        # Use global threshold instead of a hard-coded 0.7
        thr = self._get_verify_threshold()
        
        if intent_name == "open_door":
            if confidence > thr:
                logger.info(f"Local NLU triggered 'open_door' for {user_identity} "
                            f"(Score: {confidence}, Threshold: {thr})")
                tool_resp = open_door(user_identity)
                return {
                    "status": "success",
                    "response": tool_resp,
                    "action_taken": True,
                    "source": "local_nlu",
                    "threshold_used": thr,
                }
            else:
                logger.warning(
                    f"Local NLU blocked 'open_door' due to low confidence: "
                    f"{confidence} (Threshold: {thr})"
                )
                return {
                    "status": "reject",
                    "response": f"识别到开门指令，但您的身份置信度 ({confidence:.2f}) "
                                f"低于当前阈值 ({thr:.2f})，无法执行。",
                    "action_taken": False,
                    "source": "local_nlu",
                    "threshold_used": thr,
                }

        if intent_name == "turn_on_light":
            location = slots.get("location", "客厅")
            tool_resp = turn_on_light(location)
            return {
                "status": "success",
                "response": tool_resp,
                "action_taken": True,
                "source": "local_nlu",
            }

        if intent_name == "alert_police":
            reason = slots.get("reason", "紧急情况")
            tool_resp = alert_police(reason)
            return {
                "status": "success",
                "response": tool_resp,
                "action_taken": True,
                "source": "local_nlu",
            }
        
        # Step 2: Cloud LLM (Complex Reasoning)
        try:
            # 调用 Agent
            result = await self.agent_executor.ainvoke({
                "input": text,
                "user_identity": user_identity,
                "confidence": f"{confidence:.2f}"
            })
            
            output = result.get("output", "")
            return {
                "status": "success",
                "response": output,
                "action_taken": False,
                "source": "cloud_agent",
            }
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return {"status": "error", "message": str(e)}
