"""
고급 상담 서비스 - PDF 서버 연동 + JSON 중간 결과 표시
"""

import json
import requests
import time
from typing import Dict, List, Any, Optional, Tuple

from google import genai
from google.genai import types
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ..config.settings import (
    GOOGLE_API_KEY, GEMINI_MODEL, TEMPERATURE,
    HOSPITAL_CSV_PATH, PROMPT_FILE_PATH, PROCEDURE_CATEGORIES
)
from ..models.consultation_models import ProcedureCategory, PdfSelection
from ..formatters.advanced_response_formatter import create_advanced_response_formatter
from ..formatters.simple_json_formatter import format_consultation_json_to_chat


class AdvancedConsultationService:
    """고급 상담 서비스 - PDF 서버 연동"""
    
    def __init__(self, pdf_server_url: str = "http://127.0.0.1:8000"):
        self.pdf_server_url = pdf_server_url
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            temperature=0,
            client=self.client
        )
        
        self.advanced_formatter = create_advanced_response_formatter(self.llm)
        
        # 체인들
        self._pdf_selector_chain = None
        self._category_extraction_chain = None
        self._system_prompt = None
    
    def check_pdf_server_status(self) -> Dict[str, Any]:
        """PDF 서버 상태 확인"""
        try:
            response = requests.get(f"{self.pdf_server_url}/", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_cached_pdfs(self) -> Dict[str, Any]:
        """PDF 서버에서 캐시된 PDF 정보 가져오기"""
        try:
            response = requests.get(f"{self.pdf_server_url}/pdf-cache", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception as e:
            print(f"❌ PDF 캐시 조회 실패: {e}")
            return {}
    
    @property
    def pdf_summaries(self) -> Dict[str, str]:
        """PDF 파일별 요약 정보"""
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
    
    @property
    def pdf_selector_chain(self):
        """PDF 선택 체인"""
        if self._pdf_selector_chain is None:
            parser = PydanticOutputParser(pydantic_object=PdfSelection)
            prompt = ChatPromptTemplate.from_template("""
다음은 사용 가능한 PDF 파일들과 각각의 요약입니다:

{pdf_summaries}

사용자 질문: {query}

위 질문에 답변하는 데 가장 적합한 PDF 파일을 선택해주세요.

{format_instructions}
""")
            self._pdf_selector_chain = prompt | self.llm | parser
        return self._pdf_selector_chain
    
    @property
    def category_extraction_chain(self):
        """카테고리 추출 체인"""
        if self._category_extraction_chain is None:
            parser = PydanticOutputParser(pydantic_object=ProcedureCategory)
            prompt = ChatPromptTemplate.from_template("""
다음 시술 카테고리 중에서 사용자 질문과 가장 관련 있는 것을 선택하세요:
{categories}

사용자 질문: {query}

{format_instructions}
""")
            self._category_extraction_chain = prompt | self.llm | parser
        return self._category_extraction_chain
    
    @property
    def system_prompt(self) -> str:
        """시스템 프롬프트"""
        if self._system_prompt is None:
            with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as file:
                self._system_prompt = file.read()
        return self._system_prompt
    
    def process_full_consultation(self, user_query: str, conversation_history: List = None) -> Tuple[Dict[str, Any], str]:
        """
        풀 상담 처리 - 중간 JSON과 최종 답변을 모두 반환
        
        Returns:
            Tuple[Dict, str]: (중간_JSON_결과, 최종_포맷된_답변)
        """
        
        if conversation_history is None:
            conversation_history = []
        
        # 단계별 결과 저장
        process_log = {
            "user_query": user_query,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "steps": {}
        }
        
        try:
            # 1. PDF 서버 상태 확인
            pdf_status = self.check_pdf_server_status()
            process_log["steps"]["1_pdf_server_status"] = pdf_status
            
            if pdf_status.get("status") != "running":
                raise Exception(f"PDF 서버 연결 실패: {pdf_status.get('message', 'Unknown error')}")
            
            # 2. PDF 선택
            pdf_summaries_str = "\n".join([f"- {k}: {v}" for k, v in self.pdf_summaries.items()])
            selection_result = self.pdf_selector_chain.invoke({
                "query": user_query,
                "pdf_summaries": pdf_summaries_str,
                "format_instructions": PydanticOutputParser(pydantic_object=PdfSelection).get_format_instructions()
            })
            
            process_log["steps"]["2_pdf_selection"] = {
                "selected_filename": selection_result.selected_filename,
                "available_pdfs": list(self.pdf_summaries.keys())
            }
            
            # 3. 카테고리 추론
            category_result = self.category_extraction_chain.invoke({
                "query": user_query,
                "categories": ", ".join(PROCEDURE_CATEGORIES),
                "format_instructions": PydanticOutputParser(pydantic_object=ProcedureCategory).get_format_instructions()
            })
            
            process_log["steps"]["3_category_extraction"] = {
                "is_detected": category_result.is_detected,
                "category": category_result.category if category_result.is_detected else None,
                "available_categories": PROCEDURE_CATEGORIES
            }
            
            # 4. 병원 정보 로드 (간단 버전)
            hospital_info = "병원 정보 로딩 중..."  # 실제 구현 시 병원 데이터 로드
            process_log["steps"]["4_hospital_info"] = {
                "category_filter": category_result.category if category_result.is_detected else "전체",
                "hospital_count": "로딩됨"
            }
            
            # 5. 최종 프롬프트 구성
            final_prompt = self.system_prompt.replace("((HOSPITAL_LIST))", hospital_info) \
                .replace("((SUBMITTED_PHOTOS))", "사용자가 제출한 이미지가 없습니다.") \
                .replace("((CONVERSATION_HISTORY))", str(conversation_history))
            
            process_log["steps"]["5_prompt_preparation"] = {
                "prompt_length": len(final_prompt),
                "has_hospital_list": "((HOSPITAL_LIST))" not in final_prompt,
                "has_conversation": len(conversation_history) > 0
            }
            
            # 6. API 호출
            start_time = time.time()
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=final_prompt,
                config=types.GenerateContentConfig(temperature=TEMPERATURE)
            )
            api_time = time.time() - start_time
            
            raw_json_response = response.text if response and hasattr(response, 'text') else ""
            
            # JSON 코드 블록 제거 (```json으로 감싸져 있는 경우)
            cleaned_response = raw_json_response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]  # ```json 제거
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # ``` 제거
            cleaned_response = cleaned_response.strip()
            
            process_log["steps"]["6_api_call"] = {
                "api_call_time": round(api_time, 2),
                "response_length": len(raw_json_response),
                "model_used": GEMINI_MODEL,
                "response_preview": raw_json_response[:200] + "..." if len(raw_json_response) > 200 else raw_json_response,
                "cleaned_response_preview": cleaned_response[:200] + "..." if len(cleaned_response) > 200 else cleaned_response
            }
            
            # API 응답이 비어있는 경우 처리
            if not cleaned_response.strip():
                raise Exception("API 응답이 비어있습니다. 다시 시도해주세요.")
            
            # 정리된 응답을 사용
            raw_json_response = cleaned_response
            
            # 7. JSON 파싱 시도
            try:
                parsed_json = json.loads(raw_json_response)
                process_log["steps"]["7_json_parsing"] = {
                    "parsing_success": True,
                    "json_keys": list(parsed_json.keys()) if isinstance(parsed_json, dict) else "non-dict response"
                }
            except json.JSONDecodeError as e:
                parsed_json = {"raw_response": raw_json_response}
                process_log["steps"]["7_json_parsing"] = {
                    "parsing_success": False,
                    "fallback_used": True,
                    "error": str(e),
                    "response_start": raw_json_response[:100] + "..." if len(raw_json_response) > 100 else raw_json_response
                }
            
            # 8. 최종 포맷팅 - 항상 간단하고 확실한 포맷팅 사용
            try:
                # JSON 파싱이 성공했으면 파싱된 데이터를 사용
                if process_log["steps"]["7_json_parsing"]["parsing_success"]:
                    consultation_data = parsed_json
                else:
                    # 파싱 실패시 원시 응답 사용
                    consultation_data = {"raw_response": raw_json_response}
                
                # 새로운 간단한 JSON 포맷터 사용
                formatted_response = format_consultation_json_to_chat(
                    consultation_data,
                    selection_result.selected_filename,
                    category_result.category if category_result.is_detected else None
                )
                
            except Exception as format_error:
                # 모든 포맷팅 실패시 최후의 수단
                formatted_response = f"""👩‍⚕️ **AI 피부과 상담 실장** (풀 모드 - 원본 응답)

{raw_json_response}

---
📚 **참조 PDF**: {selection_result.selected_filename}
🏷️ **카테고리**: {category_result.category if category_result.is_detected else '전체'}
⚠️ **포맷 에러**: {str(format_error)}"""
            
            process_log["steps"]["8_formatting"] = {
                "formatted_length": len(formatted_response),
                "formatter_used": "advanced"
            }
            
            process_log["success"] = True
            process_log["total_time"] = round(time.time() - time.mktime(time.strptime(process_log["timestamp"], "%Y-%m-%d %H:%M:%S")), 2)
            
            return process_log, formatted_response
            
        except Exception as e:
            process_log["error"] = str(e)
            process_log["success"] = False
            
            # 간단 모드로 폴백
            simple_response = f"""👩‍⚕️ **AI 피부과 상담 실장** (간단 모드)

{user_query}에 대한 답변을 준비하는 중 일부 기능에 문제가 발생했습니다.
간단한 답변을 드리겠습니다:

**쥬베룩 시술**은 히알루론산과 PDLLA 성분을 결합한 콜라겐 재생 시술입니다.
- 주요 효과: 잔주름 개선, 모공 축소, 피부 탄력 증진
- 지속 기간: 6개월-2년
- 예상 비용: 20-40만원대

상세한 상담을 위해서는 전문의와 직접 상담받으시길 권합니다.

---
*일부 기능 오류로 간단 모드로 답변드렸습니다.*"""
            
            return process_log, simple_response

    def _format_consultation_directly(self, consultation_data: Dict[str, Any], 
                                       pdf_filename: str, category: Optional[str], 
                                       raw_response: str) -> str:
        """JSON 데이터를 직접 사용자 친화적인 텍스트로 변환"""
        
        # raw_response가 있는 경우 (JSON 파싱 실패)  
        if "raw_response" in consultation_data:
            print("DEBUG: JSON 파싱 실패 - raw_response 사용")
            return f"""👩‍⚕️ **AI 피부과 상담 실장** (풀 모드)

{consultation_data["raw_response"]}

---
📚 **참조 PDF**: {pdf_filename[:50]}...
🏷️ **추론 카테고리**: {category or '전체'}
ℹ️ **처리 모드**: PDF 참조 풀 모드"""

        # 정상적인 JSON 데이터가 있는 경우
        print("DEBUG: JSON 파싱 성공 - 구조화된 포맷팅 시작")
        print(f"DEBUG: consultation_data keys: {list(consultation_data.keys())}")
        try:
            response = f"""👩‍⚕️ **AI 피부과 상담 실장** (풀 모드)

안녕하세요! 전문 서적을 참조하여 답변드리겠습니다.

"""
            
            # 사용자 질문 명확화
            if "clarified_user_concern" in consultation_data:
                response += f"""**🎯 질문 이해**
{consultation_data["clarified_user_concern"]}

"""
            
            # 전체 요약
            if "overall_summary" in consultation_data:
                response += f"""**📋 종합 분석**
{consultation_data["overall_summary"]}

"""
            
            # 피부 문제들 처리
            if "skin_issues" in consultation_data:
                for idx, issue in enumerate(consultation_data["skin_issues"], 1):
                    response += f"""**🔍 피부 문제 #{idx}**
**문제**: {issue.get("identified_problem", "분석 중")}

**💡 추천 시술 옵션들**:
"""
                    for option in issue.get("recommended_options", []):
                        response += f"• {option}\n"
                    
                    response += "\n**📊 상세 분석**:\n"
                    
                    for analysis in issue.get("detailed_analysis", []):
                        option_name = analysis.get("option", "시술")
                        confidence = analysis.get("confidence_score", 0)
                        explanation = analysis.get("detailed_explanation", "")
                        
                        confidence_emoji = "🟢" if confidence >= 8 else "🟡" if confidence >= 6 else "🟠"
                        
                        response += f"""
**{confidence_emoji} {option_name}** (신뢰도: {confidence}/10)
{explanation}

"""
                        
                        # 시술 계획
                        if "procedure_plan" in analysis:
                            plan = analysis["procedure_plan"]
                            response += f"""**📅 시술 계획**:
• 권장 횟수: {plan.get("recommended_sessions", "상담 후 결정")}
• 회복 기간: {plan.get("expected_downtime", "개인차 있음")}
• 예상 비용: {plan.get("expected_cost_range", "상담 시 안내")}

"""
            
            # 병원 선택 가이드
            if "clinic_selection_guide" in consultation_data:
                response += f"""**🏥 병원 선택 가이드**
{consultation_data["clinic_selection_guide"]}

"""
            
            response += f"""---
📚 **참조 PDF**: {pdf_filename[:50]}...
🏷️ **추론 카테고리**: {category or '전체'}
⚡ **처리 모드**: PDF 참조 풀 모드

*본 상담은 AI 분석 결과이며, 최종 진단 및 치료는 반드시 전문의와 상의하시기 바랍니다.*"""
            
            return response
            
        except Exception as e:
            # JSON 파싱은 성공했지만 포맷팅에서 문제 발생
            return f"""👩‍⚕️ **AI 피부과 상담 실장** (풀 모드)

전문 서적을 참조한 상담 결과입니다:

{raw_response}

---
📚 **참조 PDF**: {pdf_filename[:50]}...
🏷️ **추론 카테고리**: {category or '전체'}
⚠️ **포맷팅 이슈**: {str(e)}"""


def create_advanced_consultation_service(pdf_server_url: str = "http://127.0.0.1:8000") -> AdvancedConsultationService:
    """고급 상담 서비스 생성"""
    return AdvancedConsultationService(pdf_server_url)