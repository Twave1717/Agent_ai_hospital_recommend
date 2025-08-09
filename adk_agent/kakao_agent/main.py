# adk_agent/main.py
import os
import asyncio
import traceback
from dotenv import load_dotenv
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# agent_def.py에서 에이전트 생성 함수를 가져옵니다.
from agent_def import get_kakao_agent_async

# 프로젝트 루트의 .env 파일을 로드합니다.
# main.py는 adk_agent/ 안에 있으므로 상위 디렉토리의 .env를 찾아야 합니다.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

async def async_main():
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        state={}, app_name='kakao_mcp_app', user_id='user_kakao'
    )

    query = "나에게 'ADK 프로젝트 구조화 성공!' 이라고 카톡 보내줘"
    print(f"User Query: '{query}'")
    content = types.Content(role='user', parts=[types.Part(text=query)])

    # 정의 파일에서 에이전트와 툴셋을 가져옵니다.
    root_agent, toolset = await get_kakao_agent_async()

    runner = Runner(
        app_name='kakao_mcp_app',
        agent=root_agent,
        session_service=session_service,
    )

    print("Running agent...")
    events_async = runner.run_async(
        session_id=session.id, user_id=session.user_id, new_message=content
    )

    async for event in events_async:
        print(f"Event received: {event}")
    
    print("Closing MCP server connection...")
    await toolset.close()
    print("Cleanup complete.")

if __name__ == '__main__':
    try:
        asyncio.run(async_main())
    except Exception as e:
        # 이 부분이 상세 오류를 출력해줍니다.
        print(f"An error occurred: {e}")
        print("--- Full Traceback ---")
        traceback.print_exc()
        print("----------------------")