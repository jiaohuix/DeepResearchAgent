import os
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio

# 将项目根目录添加到 Python 路径
root = str(Path(__file__).resolve().parents[1])
sys.path.append(root)

# 导入必要的类
from src.models.base import ChatMessage, ChatMessageToolCall, ChatMessageToolCallDefinition, ApiModel, Model
from src.models.litellm import LiteLLMModel
from src.base.tool_calling_agent import ToolCallingAgent
from src.memory import ActionStep
from src.tools import AsyncTool
from src.registry import register_tool
from src.logger import logger, LogLevel # 导入 logger
logger.setLevel(LogLevel.INFO) # 设置日志级别为INFO，方便查看调试信息

# --- 1. 模拟配置对象 (仅包含必要的属性) ---
class MockConfig:
    class MockToolConfig:
        model_id = "qwen3_8b"
        max_insights = 20
        max_depth = 2
        time_limit_seconds = 60
        max_follow_ups = 3

    deep_researcher_tool = MockToolConfig()

# --- 2. 模拟 model_manager ---
class MockModelManager:
    registed_models = {}

    def init_models(self, use_local_proxy=False):
        # 注册 LiteLLMModel
        self.registed_models["qwen3_8b"] = LiteLLMModel(model_id="qwen3_8b")
        # 确保 LiteLLMModel 的 client 属性被设置
        self.registed_models["qwen3_8b"].client = MockLiteLLMClient()

mock_model_manager = MockModelManager()

# --- 3. 模拟 litellm.completion 的响应对象 ---
class MockFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments

class MockChatCompletionMessageToolCall:
    def __init__(self, index: int, function: MockFunction, id: str, type: str):
        self.index = index
        self.function = function
        self.id = id
        self.type = type
    def model_dump(self):
        return {
            "index": self.index,
            "function": {"name": self.function.name, "arguments": self.function.arguments},
            "id": self.id,
            "type": self.type,
        }

class MockMessage:
    def __init__(self, content: Optional[str] = None, tool_calls: Optional[List[MockChatCompletionMessageToolCall]] = None):
        self.content = content
        self.tool_calls = tool_calls
    def model_dump(self, exclude=None, include=None):
        data = {"role": "assistant", "content": self.content}
        if self.tool_calls is not None:
            data["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        if exclude:
            for key in exclude:
                if key in data:
                    del data[key]
        if include:
            data = {k: v for k, v in data.items() if k in include}
        return data

class MockChoice:
    def __init__(self, message: MockMessage):
        self.message = message

class MockUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

class MockLiteLLMResponse:
    def __init__(self, message_content: str, tool_calls: Optional[List[MockChatCompletionMessageToolCall]] = None):
        self.choices = [MockChoice(MockMessage(content=message_content, tool_calls=tool_calls))]
        self.usage = MockUsage(prompt_tokens=10, completion_tokens=20)


# --- 4. 模拟 LiteLLM client (用于 LiteLLMModel 内部调用) ---
class MockLiteLLMClient:
    async def completion(self, **kwargs):
        # 模拟 LLM 以文本格式返回工具调用 (Action: ...)
        if kwargs.get("tools") and kwargs.get("tool_choice") == "required":
            # 模拟 Qwen/Qwen3-8B 这种行为：tool_calls 为 None，但 content 有 Action
            logger.info("MOCK_LITELM_CLIENT: Simulating LLM returning Action in content.")
            tool_call_str = """
Action:
{
  "name": "final_answer",
  "arguments": {"answer": "This is a simulated final answer from the LLM."}
}
"""
            return MockLiteLLMResponse(message_content=tool_call_str, tool_calls=None)
        
        # 模拟 LLM 以结构化工具调用返回
        if kwargs.get("tools") and kwargs.get("tool_choice") == "auto":
             logger.info("MOCK_LITELM_CLIENT: Simulating LLM returning structured tool_calls.")
             mock_tool_call = MockChatCompletionMessageToolCall(
                 index=0,
                 function=MockFunction(name="some_tool", arguments=json.dumps({"param": "value"})),
                 id="mock_id_123",
                 type="function"
             )
             return MockLiteLLMResponse(message_content=None, tool_calls=[mock_tool_call])

        # 默认返回普通文本响应
        return MockLiteLLMResponse(message_content="This is a simple text response.")


# --- 5. 模拟一个简单的工具，供 ToolCallingAgent 使用 ---
@register_tool("final_answer")
class FinalAnswerTool(AsyncTool):
    name: str = "final_answer"
    description: str = "Returns the final answer to the user."
    parameters: dict = {
        "type": "object",
        "properties": {"answer": {"type": "string", "description": "The final answer to the user."}},
        "required": ["answer"],
    }
    output_type = "str"

    async def forward(self, answer: str) -> str:
        return f"Final Answer: {answer}"

# --- 6. 运行复现代码 ---
async def run_reproduce():
    logger.info("Starting reproduction script...")

    # 初始化模型管理器
    mock_model_manager.init_models()
    model_instance = mock_model_manager.registed_models["qwen3_8b"]

    # 模拟工具
    mock_tools = {
        "final_answer": FinalAnswerTool()
    }
    
    # 实例化 ToolCallingAgent
    # 注意：这里我们使用 mock_config 作为 agent 的配置，并传递模型实例
    # 确保 ToolCallingAgent 能够访问到 model.parse_tool_calls_from_text
    agent = ToolCallingAgent(
        tools=list(mock_tools.values()),
        model=model_instance,
        # 其他可能需要的参数，根据你的实际 ToolCallingAgent 构造函数补充
    )
    
    # 模拟一个 ActionStep
    memory_step = ActionStep(tool_calls=[])
    
    logger.info("Calling agent.step with simulated LLM response...")
    try:
        # 我们需要模拟一个LLM调用的输入消息
        input_messages = [{"role": "user", "content": "Tell me the final answer."}]
        # 直接调用模型获取chat_message，模拟LLM行为
        # 这里需要确保模型能被调用，并且返回的 chat_message 包含 raw 属性
        chat_message_from_model = await model_instance(
            messages=input_messages,
            tools_to_call_from=list(mock_tools.values()), # 模拟工具给LLM
            tool_choice="required" # 确保LLM尝试返回工具调用
        )
        
        # 将模拟的 chat_message 及其 raw 属性赋值给 memory_step.model_output_message
        # 以模拟 ToolCallingAgent 实际接收到的对象
        memory_step.model_output_message = chat_message_from_model
        memory_step.model_output = chat_message_from_model.content # 确保 content 也被设置

        # 调用 step 方法来复现错误
        result = agent.step(memory_step)
        logger.info(f"Step completed successfully! Result: {result}")

    except Exception as e:
        logger.error(f"An error occurred during agent.step: {e}", exc_info=True)
        # 再次打印最终的 chat_message.tool_calls 状态，以便调试
        logger.error(f"DEBUG: Final chat_message.tool_calls state in exception: {memory_step.model_output_message.tool_calls}")

if __name__ == "__main__":
    asyncio.run(run_reproduce())
