# adk_agent/agent_def.py
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams


async def get_kakao_agent_async():
    """kakao-bot-mcp-server의 도구를 장착한 ADK 에이전트를 생성합니다."""
    toolset = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params={
                "command": "uv",
                "args": ["run", "mcp-kakao"],
                "cwd": "../kakao-bot-mcp-server",
            }
        ),
    )

    root_agent = LlmAgent(
        model="gemini-1.5-pro-latest",
        name="kakao_assistant",
        instruction="You are a helpful assistant. You can send KakaoTalk messages and create calendar events for the user using the available tools.",
        tools=[toolset],
    )
    return root_agent, toolset
