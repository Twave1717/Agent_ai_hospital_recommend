"""
상담 서비스 - 메인 비즈니스 로직
"""

import os
import json
import pandas as pd
from typing import Dict, List, Any
from pathlib import Path

from google import genai
from google.genai import types
from google.genai.types import File
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
import asyncio
import time

from ..config.settings import (
    GOOGLE_API_KEY, GEMINI_MODEL, TEMPERATURE,
    TEXTBOOK_DIR_PATH, HOSPITAL_CSV_PATH, PROMPT_FILE_PATH,
    PROCEDURE_CATEGORIES
)
from ..models.consultation_models import ProcedureCategory, PdfSelection
from ..chains.response_formatter import create_response_formatter_chain
from ..formatters.advanced_response_formatter import create_advanced_response_formatter


class ConsultationService:
    """피부과 상담 서비스"""
    
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            temperature=0,
            client=self.client
        )
        
        # 응답 포맷터 초기화
        self.simple_formatter = create_response_formatter_chain(self.llm)
        self.advanced_formatter = create_advanced_response_formatter(self.llm)
        
        # PDF 핸들 및 체인 캐시
        self._pdf_handles = None
        self._pdf_summaries = None
        self._pdf_selector_chain = None
        self._category_extraction_chain = None
        self._system_prompt = None
    
    @property
    def pdf_handles(self) -> Dict[str, File]:
        """PDF 핸들 지연 로딩"""
        if self._pdf_handles is None:
            self._pdf_handles = self._upload_all_pdfs()
        return self._pdf_handles
    
    @property
    def pdf_summaries(self) -> Dict[str, str]:
        """PDF 요약 지연 로딩"""
        if self._pdf_summaries is None:
            self._pdf_summaries = self._get_pdf_summaries()
        return self._pdf_summaries
    
    @property
    def pdf_selector_chain(self):
        """PDF 선택 체인 지연 로딩"""
        if self._pdf_selector_chain is None:
            self._pdf_selector_chain = self._create_pdf_selection_chain()
        return self._pdf_selector_chain
    
    @property
    def category_extraction_chain(self):
        """카테고리 추출 체인 지연 로딩"""
        if self._category_extraction_chain is None:
            self._category_extraction_chain = self._create_category_extraction_chain()
        return self._category_extraction_chain
    
    @property
    def system_prompt(self) -> str:
        """시스템 프롬프트 지연 로딩"""
        if self._system_prompt is None:
            self._system_prompt = self._load_prompt_from_file()
        return self._system_prompt
    
    def _upload_all_pdfs(self) -> Dict[str, File]:
        """디렉토리의 모든 PDF를 업로드"""
        uploaded_files = {}
        
        for root, _, files in os.walk(TEXTBOOK_DIR_PATH):
            for file in files:
                if file.lower().endswith(".pdf"):
                    filepath = os.path.join(root, file)
                    try:
                        print(f"업로드 중: {file}")
                        # 2025 최신 Google GenAI SDK 방식
                        uploaded_file = self.client.files.upload(file=filepath)
                        uploaded_files[file] = uploaded_file
                        print(f"✓ 업로드 완료: {file}")
                    except Exception as e:
                        print(f"✗ 업로드 실패 {file}: {e}")
        
        return uploaded_files
    
    def _get_pdf_summaries(self) -> Dict[str, str]:
        """PDF 파일별 요약 정보 반환"""
        return {
            "Cosmetic Dermatology- Products And Procedures Cosmetic -- Draelos, Zoe Kececioglu -- ( WeLib.org ).pdf": 
                "화장품 및 미용 시술에 관한 포괄적인 가이드. 다양한 피부 문제와 해결책을 다룹니다.",
            
            "Textbook of Cosmetic Dermatology (Series in Cosmetic and -- Robert L Baran; Howard Ira Maibach -- ( WeLib.org ).pdf": 
                "미용 피부과학의 종합적인 교과서. 전문적인 시술과 치료법을 상세히 설명합니다.",
            
            "Injectable Fillers in Aesthetic Medicine -- Mauricio de Maio, Berthold Rzany (auth.) -- ( WeLib.org ).pdf": 
                "필러 시술에 특화된 전문서. 주사형 필러의 종류, 시술법, 부작용 등을 다룹니다.",
            
            "Skills for Communicating with Patients, 3rd Edition -- Juliet Draper, Suzanne M. Kurtz, Jonathan Silverman -- ( WeLib.org ).pdf": 
                "환자와의 효과적인 소통 방법에 관한 가이드북입니다."
        }
    
    def _create_pdf_selection_chain(self):
        """PDF 선택 체인 생성"""
        
        parser = PydanticOutputParser(pydantic_object=PdfSelection)
        
        prompt = ChatPromptTemplate.from_template("""
다음은 사용 가능한 PDF 파일들과 각각의 요약입니다:

{pdf_summaries}

사용자 질문: {query}

위 질문에 답변하는 데 가장 적합한 PDF 파일을 선택해주세요.

{format_instructions}
""")
        
        return prompt | self.llm | parser
    
    def _create_category_extraction_chain(self):
        """카테고리 추출 체인 생성"""
        
        parser = PydanticOutputParser(pydantic_object=ProcedureCategory)
        
        prompt = ChatPromptTemplate.from_template("""
다음 시술 카테고리 중에서 사용자 질문과 가장 관련 있는 것을 선택하세요:
{categories}

사용자 질문: {query}

{format_instructions}
""")
        
        return prompt | self.llm | parser
    
    def _load_prompt_from_file(self) -> str:
        """프롬프트 파일 로드"""
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as file:
            return file.read()
    
    def _load_and_filter_hospitals(self, category: str = None) -> str:
        """병원 데이터 로드 및 필터링"""
        try:
            df = pd.read_csv(HOSPITAL_CSV_PATH)
            
            if category:
                # 카테고리별 필터링 로직 (필요시 구현)
                pass
            
            # 상위 10개 병원 정보 반환
            top_hospitals = df.head(10)
            hospital_info = []
            
            for _, row in top_hospitals.iterrows():
                info = f"병원명: {row.get('name', 'N/A')}, "
                info += f"지역: {row.get('location', 'N/A')}, "
                info += f"평점: {row.get('rating', 'N/A')}"
                hospital_info.append(info)
            
            return "\n".join(hospital_info)
            
        except Exception as e:
            return f"병원 정보 로드 실패: {str(e)}"
    
    def process_consultation(self, user_query: str, conversation_history: List = None, 
                           use_advanced_formatter: bool = True, simple_mode: bool = False) -> str:
        """상담 처리 메인 메소드"""
        
        if conversation_history is None:
            conversation_history = []
        
        # 간단 모드 - 직접 답변 (PDF 및 복잡한 체인 우회)
        if simple_mode:
            return self._simple_consultation(user_query, use_advanced_formatter)
        
        try:
            # 1. PDF 선택
            pdf_summaries_str = "\n".join([f"- {k}: {v}" for k, v in self.pdf_summaries.items()])
            selection_result = self.pdf_selector_chain.invoke({
                "query": user_query,
                "pdf_summaries": pdf_summaries_str,
                "format_instructions": PydanticOutputParser(pydantic_object=PdfSelection).get_format_instructions()
            })
            
            selected_filename = selection_result.selected_filename
            selected_pdf_handle = self.pdf_handles.get(selected_filename)
            
            # 2. 카테고리 추론
            category_result = self.category_extraction_chain.invoke({
                "query": user_query,
                "categories": ", ".join(PROCEDURE_CATEGORIES),
                "format_instructions": PydanticOutputParser(pydantic_object=ProcedureCategory).get_format_instructions()
            })
            
            category = category_result.category if category_result.is_detected else None
            
            # 3. 병원 정보 로드
            hospital_info = self._load_and_filter_hospitals(category)
            
            # 4. 최종 프롬프트 구성
            final_prompt = self.system_prompt.replace("((HOSPITAL_LIST))", hospital_info) \
                .replace("((SUBMITTED_PHOTOS))", "사용자가 제출한 이미지가 없습니다.") \
                .replace("((CONVERSATION_HISTORY))", str(conversation_history))
            
            # 5. API 호출 (타임아웃 및 재시도 로직 추가)
            current_parts = [user_query]
            if selected_pdf_handle:
                current_parts.append(selected_pdf_handle)
            
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    print(f"📡 API 호출 시도 {attempt + 1}/{max_retries}...")
                    
                    response = self.client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=final_prompt,
                        config=types.GenerateContentConfig(
                            temperature=TEMPERATURE,
                            max_output_tokens=2048  # 출력 길이 제한
                        )
                    )
                    break  # 성공하면 루프 탈출
                    
                except Exception as api_error:
                    print(f"❌ API 호출 실패 (시도 {attempt + 1}): {api_error}")
                    if attempt < max_retries - 1:
                        print(f"⏱️ {retry_delay}초 후 재시도...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 지수 백오프
                    else:
                        raise api_error
            
            raw_json_response = response.text
            
            # 6. 응답 포맷팅
            if use_advanced_formatter:
                return self.advanced_formatter.format_consultation_response(raw_json_response)
            else:
                return self.simple_formatter.format_response(raw_json_response)
            
        except Exception as e:
            print(f"❌ 풀 모드 실패, 간단 모드로 폴백: {e}")
            try:
                return self._simple_consultation(user_query, use_advanced_formatter)
            except Exception as fallback_error:
                print(f"❌ 간단 모드도 실패: {fallback_error}")
                return f"❌ 죄송합니다. 시스템 오류로 답변을 생성할 수 없습니다. 다시 시도해주세요. (오류: {str(e)})"

    def _simple_consultation(self, user_query: str, use_advanced_formatter: bool = True) -> str:
        """간단 상담 모드 - PDF 없이 직접 답변"""
        try:
            print("🚀 간단 모드로 답변 생성 중...")
            
            simple_prompt = f"""당신은 20년차 경력의 피부과 전문 상담 실장입니다.
            
사용자 질문: {user_query}

위 질문에 대해 전문적이고 친근한 답변을 해주세요. 
구체적인 시술 방법, 장단점, 주의사항, 대략적인 비용 등을 포함해주세요."""

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=simple_prompt,
                config=types.GenerateContentConfig(temperature=TEMPERATURE)
            )
            
            simple_answer = response.text
            
            if use_advanced_formatter:
                # 간단한 포맷팅 적용
                formatted_answer = f"""👩‍⚕️ **AI 피부과 상담 실장**

{simple_answer}

---
*간단 모드로 답변드렸습니다. 정확한 진단은 전문의와 상담하시기 바랍니다.*"""
                return formatted_answer
            else:
                return simple_answer
                
        except Exception as e:
            return f"❌ 답변 생성 실패: {str(e)}"


def create_consultation_service() -> ConsultationService:
    """상담 서비스 생성 헬퍼 함수"""
    return ConsultationService()