# app.py

import streamlit as st
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# 프로젝트 루트 디렉터리를 Python 경로에 추가하여 'source' 모듈을 찾을 수 있도록 설정
sys.path.append(os.getcwd())

# 기존 챗봇 로직 및 설정들을 임포트합니다.
from source.agent_veteran_skin_consultant import (
    upload_all_pdfs_once,
    get_pdf_summaries,
    create_pdf_selection_chain,
    create_category_extraction_chain,
    load_prompt_from_file,
    load_and_filter_hospitals,
    PROCEDURE_CATEGORIES,
    PROMPT_FILE_PATH,
    TEXTBOOK_DIR_PATH,
    HOSPITAL_CSV_PATH
)
from langchain_google_genai import ChatGoogleGenerativeAI

# --- Streamlit 앱 설정 ---
st.set_page_config(page_title="AI 피부과 상담 챗봇", page_icon="👩‍⚕️")
st.title("👩‍⚕️ AI 피부과 상담 챗봇")
st.markdown("피부 시술에 대해 궁금한 점을 무엇이든 물어보세요! AI가 전문 서적을 참고하여 답변해 드립니다.")

# --- 1. 초기화 및 리소스 캐싱 ---

@st.cache_resource
def initialize_chatbot():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("`.env` 파일에 `GOOGLE_API_KEY='당신의 API 키'` 형식으로 키를 설정해주세요.")
        st.stop()
    
    client = genai.Client(api_key=api_key)

    with st.spinner("전문 서적(PDF)을 로딩하고 있습니다..."):
        pdf_handles_dict = upload_all_pdfs_once(TEXTBOOK_DIR_PATH, client)
        if not pdf_handles_dict:
            st.error("업로드할 PDF 파일이 없어 챗봇을 실행할 수 없습니다.")
            st.stop()

    pdf_summaries_dict = get_pdf_summaries()
    llm_for_chains = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest",
        temperature=0,
        client=client
    )
    pdf_selector_chain = create_pdf_selection_chain(llm_for_chains, pdf_summaries_dict)
    category_extraction_chain = create_category_extraction_chain(llm_for_chains, PROCEDURE_CATEGORIES)
    system_prompt_template = load_prompt_from_file(PROMPT_FILE_PATH)

    return client, pdf_handles_dict, pdf_selector_chain, category_extraction_chain, system_prompt_template

try:
    g_client, g_pdf_handles, g_selector_chain, g_cat_chain, g_sys_prompt = initialize_chatbot()
except Exception as e:
    st.error(f"챗봇 초기화 중 오류가 발생했습니다: {e}")
    st.stop()

# --- 2. 채팅 기록 관리 ---

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 3. 사용자 입력 및 챗봇 응답 처리 ---

if prompt := st.chat_input("여기에 질문을 입력하세요..."):
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("AI 상담 실장이 답변을 준비 중입니다..."):
            
            # 단계 1-3: 정보 수집 (PDF 선택, 카테고리 추론, 병원 정보 필터링)
            selection_result = g_selector_chain.invoke({"query": prompt})
            selected_filename = selection_result.selected_filename
            selected_pdf_handle = g_pdf_handles.get(selected_filename)
            if selected_pdf_handle:
                st.info(f"📚 참고자료: `{selected_filename}`")

            category_info = g_cat_chain.invoke({"query": prompt})
            category = category_info.category if category_info.is_detected else None
            if category:
                st.info(f"💬 추론된 카테고리: `{category}`")

            hospital_info_str = load_and_filter_hospitals(HOSPITAL_CSV_PATH, category)



            try:
                # 1. API에 전달할 'parts' 리스트를 생성합니다.
                current_user_parts = [prompt]
                
                # 2. PDF 파일 핸들(리모컨)이 있으면 리스트에 추가합니다.
                if selected_pdf_handle:
                    current_user_parts.append(selected_pdf_handle)
                st.session_state.messages.append({"role": "user", "content": current_user_parts})
                
                # 단계 4: API에 전달할 콘텐츠 구성
                final_prompt_text = g_sys_prompt.replace("((HOSPITAL_LIST))", hospital_info_str) \
                .replace("((SUBMITTED_PHOTOS))", "사용자가 제출한 이미지가 없습니다.") \
                .replace("((CONVERSATION_HISTORY))", str(st.session_state.messages))

                # 3. [텍스트, 파일] 형태의 리스트를 contents에 그대로 전달하여 API를 호출합니다.
                #    이것이 텍스트와 파일을 함께 처리하는 올바른 방법입니다.
                response = g_client.models.generate_content(
                    model="gemini-1.5-flash-latest",
                    contents=final_prompt_text,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                response_text = response.text

            except Exception as e:
                response_text = f"죄송합니다, 답변 생성 중 오류가 발생했습니다: {e}"
                st.error(response_text)

        st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})