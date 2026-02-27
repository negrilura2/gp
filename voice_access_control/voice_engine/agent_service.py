import os
import json
import logging
from typing import Optional, Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from voice_engine.config import get_path_env
from voice_engine.nlu import LocalNLU

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
                temperature=0.1  # 降低温度，提高工具调用的稳定性
            )
            
            self.tools = [open_door, turn_on_light, alert_police]
            
            # 定义 Prompt
            # System prompt 中包含当前用户信息，以便 Agent 做出决策
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个智能家居安防助手。你有能力控制家里的门锁、灯光和报警系统。"
                           "当前识别到的用户身份: {user_identity} (置信度得分: {confidence})。"
                           "请根据用户指令和身份置信度采取行动。"
                           "规则："
                           "1. 只要用户要求开门且置信度大于 0.7，你必须调用 open_door 工具，不要犹豫。"
                           "2. 调用工具后，请根据工具的返回结果回复用户，说明门已打开。"
                           "3. 只有在置信度低于 0.7 或身份未知时，才拒绝开门。"
                           "4. 请使用简体中文回复。"),
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

        # === Hybrid Intelligence Strategy ===
        # Step 1: Edge-Side NLU (High Priority, Low Latency, Safety Critical)
        # Check if the intent can be resolved locally without Cloud LLM
        intent_name, slots = self.local_nlu.parse(text)
        
        if intent_name == "open_door":
            if confidence > 0.7:
                logger.info(f"Local NLU triggered 'open_door' for {user_identity} (Score: {confidence})")
                # Directly execute local logic or tool function
                # Note: In a real system, we might invoke the tool function directly here
                # But to keep consistent response format, we simulate a successful action
                msg = f"已通过本地指令识别为您（{user_identity}）执行开门操作。"
                return {
                    "status": "success",
                    "response": msg,
                    "action_taken": True,
                    "source": "local_nlu"
                }
            else:
                logger.warning(f"Local NLU blocked 'open_door' due to low confidence: {confidence}")
                return {
                    "status": "reject",
                    "response": f"识别到开门指令，但您的身份置信度 ({confidence:.2f}) 不足，无法执行。",
                    "action_taken": False,
                    "source": "local_nlu"
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
                "action_taken": True if "Tool called" in output else False # 简化判断，实际可解析 intermediate_steps
            }
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return {"status": "error", "message": str(e)}
