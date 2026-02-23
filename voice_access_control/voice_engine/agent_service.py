import os
import json
import logging
from typing import Optional, Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from voice_engine.config import get_path_env

logger = logging.getLogger(__name__)

# 定义工具 (Tools)
@tool
def open_door(user_name: str = "unknown") -> str:
    """
    Open the door for a specific user.
    Use this tool when the user explicitly asks to open the door.
    """
    logger.info(f"Tool called: open_door for {user_name}")
    # 在实际系统中，这里会调用硬件接口
    return f"Door opened for {user_name}."

@tool
def turn_on_light(location: str = "living room") -> str:
    """
    Turn on the lights in a specific location.
    Use this tool when the user asks to turn on lights.
    """
    logger.info(f"Tool called: turn_on_light in {location}")
    return f"Lights turned on in {location}."

@tool
def alert_police(reason: str = "emergency") -> str:
    """
    Call the police or security.
    Use this tool ONLY when there is a clear emergency or threat.
    """
    logger.warning(f"Tool called: alert_police for {reason}")
    return f"Emergency alert sent: {reason}"

class AgentService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        
        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set. Agent will not function correctly.")
            self.agent_executor = None
            return
        
        try:
            self.llm = ChatOpenAI(
                model=self.model_name,
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
                temperature=1.3
            )
            
            self.tools = [open_door, turn_on_light, alert_police]
            
            # 定义 Prompt
            # System prompt 中包含当前用户信息，以便 Agent 做出决策
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a smart home security assistant. "
                           "Your goal is to help the user with security and home automation tasks. "
                           "Current user identity: {user_identity} (Confidence: {confidence}). "
                           "If the user is unknown or confidence is low, be cautious about security-critical actions like opening doors."),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # 创建 Agent
            self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
            self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools, verbose=True)
            
            logger.info(f"AgentService initialized with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize AgentService components: {e}")
            self.agent_executor = None

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
        confidence = user_context.get("score", 0.0)
        
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
                "action_taken": True if "Tool called" in output else False # 简化判断，实际可解析 intermediate_steps
            }
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return {"status": "error", "message": str(e)}
