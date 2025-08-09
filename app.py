# app.py - 새로운 구조 적용

import streamlit as st
import sys
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.getcwd())

from src.services.consultation_service import create_consultation_service
from src.services.advanced_consultation_service import create_advanced_consultation_service
import requests
import json

# --- Streamlit 앱 설정 ---
st.set_page_config(page_title="AI 피부과 상담 챗봇", page_icon="👩‍⚕️")
st.title("👩‍⚕️ AI 피부과 상담 챗봇")
st.markdown("피부 시술에 대해 궁금한 점을 무엇이든 물어보세요! AI가 전문 서적을 참고하여 답변해 드립니다.")

# --- 사이드바 설정 ---
st.sidebar.title("⚙️ 설정")

# 모드 선택
consultation_mode = st.sidebar.radio(
    "상담 모드 선택",
    options=["간단 모드 (빠름)", "풀 모드 (PDF 참조)"],
    index=0,
    help="간단 모드는 빠르게 답변하고, 풀 모드는 PDF를 참조하여 더 정확한 답변을 제공합니다"
)

use_advanced_formatter = st.sidebar.toggle("고급 응답 포맷 사용", value=True, help="구조화된 아름다운 응답 형식을 사용합니다")
show_process_json = st.sidebar.toggle("중간 처리 과정 표시", value=True, help="JSON 형태의 중간 처리 결과를 보여줍니다 (풀 모드만)")

# --- 1. 초기화 및 리소스 캐싱 ---
@st.cache_resource
def initialize_services():
    """상담 서비스들 초기화"""
    try:
        with st.spinner("🔄 AI 상담 시스템을 초기화하고 있습니다..."):
            simple_service = create_consultation_service()
            advanced_service = create_advanced_consultation_service()
            st.success("✅ 초기화 완료!")
        return simple_service, advanced_service
    except Exception as e:
        st.error(f"❌ 초기화 실패: {e}")
        st.stop()

# 서비스 초기화
simple_service, advanced_service = initialize_services()

# PDF 서버 상태 확인
def check_pdf_server():
    try:
        response = requests.get("http://127.0.0.1:8000/", timeout=3)
        return response.status_code == 200, response.json()
    except:
        return False, None

pdf_server_status, pdf_info = check_pdf_server()

# --- 2. 채팅 기록 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 채팅 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 3. 사용자 입력 및 챗봇 응답 처리 ---
if prompt := st.chat_input("여기에 질문을 입력하세요..."):
    # 사용자 메시지 표시
    with st.chat_message("user"):
        st.markdown(prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})

    # AI 응답 생성 및 표시
    with st.chat_message("assistant"):
        if consultation_mode == "간단 모드 (빠름)":
            # 간단 모드
            with st.spinner("🚀 간단 모드로 답변을 준비 중입니다..."):
                try:
                    response = simple_service._simple_consultation(
                        user_query=prompt,
                        use_advanced_formatter=use_advanced_formatter
                    )
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    error_msg = f"❌ 답변 생성 중 오류가 발생했습니다: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        else:
            # 풀 모드 (PDF 참조)
            if not pdf_server_status:
                st.warning("⚠️ PDF 서버가 실행되지 않았습니다. PDF 서버를 먼저 실행해주세요.")
                st.code("python pdf_server.py")
                
                # 폴백으로 간단 모드 사용
                with st.spinner("📋 간단 모드로 폴백..."):
                    try:
                        response = simple_service._simple_consultation(
                            user_query=prompt,
                            use_advanced_formatter=use_advanced_formatter
                        )
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_msg = f"❌ 폴백 모드도 실패했습니다: {str(e)}"
                        st.error(error_msg)
            
            else:
                # PDF 서버 연결됨 - 풀 모드 실행
                with st.spinner("📚 PDF를 참조하여 답변을 준비 중입니다..."):
                    try:
                        # 풀 상담 처리
                        process_log, response = advanced_service.process_full_consultation(
                            user_query=prompt,
                            conversation_history=st.session_state.messages
                        )
                        
                        # 중간 처리 과정 표시 (선택적)
                        if show_process_json:
                            with st.expander("🔍 중간 처리 과정 (JSON)", expanded=False):
                                st.json(process_log)
                        
                        # 최종 답변 표시
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        
                        # 성공 시 추가 정보 표시
                        if process_log.get("success"):
                            with st.expander("📊 처리 통계", expanded=False):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("전체 처리 시간", f"{process_log.get('total_time', 0):.1f}초")
                                with col2:
                                    selected_pdf = process_log.get("steps", {}).get("2_pdf_selection", {}).get("selected_filename", "N/A")
                                    st.metric("참조 PDF", selected_pdf[:20] + "..." if len(selected_pdf) > 20 else selected_pdf)
                                with col3:
                                    category = process_log.get("steps", {}).get("3_category_extraction", {}).get("category", "전체")
                                    st.metric("추론 카테고리", category or "없음")
                        
                    except Exception as e:
                        error_msg = f"❌ 풀 모드 실행 실패: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})

# --- 4. 추가 기능 ---
with st.sidebar:
    st.markdown("---")
    
    # PDF 서버 상태 표시
    if pdf_server_status:
        st.success("🟢 PDF 서버 연결됨")
        if pdf_info:
            st.caption(f"캐시된 PDF: {pdf_info.get('cached_pdfs', 0)}개")
    else:
        st.error("🔴 PDF 서버 연결 안됨")
        st.caption("풀 모드 사용 불가")
    
    if st.button("🗑️ 채팅 기록 삭제"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 PDF 서버 상태 새로고침"):
        st.rerun()
    
    st.markdown("### 📋 사용법")
    st.markdown("""
    **간단 모드**: 빠른 일반적인 답변
    **풀 모드**: PDF 참조 + 상세 분석
    
    1. 모드를 선택하세요
    2. 피부 고민을 자세히 설명해주세요  
    3. AI가 답변해드립니다
    """)
    
    st.markdown("### 🚀 PDF 서버 실행")
    st.code("python pdf_server.py", language="bash")
    st.caption("풀 모드 사용 전 별도 터미널에서 실행")
    
    st.markdown("### ⚠️ 주의사항")
    st.markdown("""
    - 본 서비스는 참고용이며 실제 진료를 대체하지 않습니다
    - 정확한 진단은 전문의와 상담하시기 바랍니다
    """)