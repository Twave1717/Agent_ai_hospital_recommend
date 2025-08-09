"""
최종 답변 포맷팅 체인
JSON 형태의 상담 결과를 사용자 친화적인 텍스트로 변환
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI


class ResponseFormatterChain:
    """JSON 상담 결과를 사용자 친화적인 응답으로 변환하는 체인"""
    
    def __init__(self, llm: ChatGoogleGenerativeAI):
        self.llm = llm
        self.chain = self._create_chain()
    
    def _create_chain(self):
        """응답 포맷팅 체인 생성"""
        
        prompt = ChatPromptTemplate.from_template("""
당신은 20년차 경력의 피부과 전문 상담 실장입니다. 
아래 JSON 형태의 상담 분석 결과를 바탕으로 실제 고객에게 전달할 친근하고 전문적인 답변을 작성해주세요.

**작성 가이드라인:**
1. 따뜻하고 친근한 톤으로 작성
2. 전문 용어는 쉽게 풀어서 설명
3. 고객의 걱정을 덜어주는 안심시키는 문체
4. 구체적이고 실용적인 정보 제공
5. 이모지 적절히 활용 (과도하지 않게)

**응답 구조:**
1. 인사 및 공감 표현
2. 고객 상태 분석 결과 설명
3. 추천 시술별 상세 안내
4. 병원 선택 가이드
5. 마무리 격려 및 추가 문의 안내

**분석 결과 JSON:**
{consultation_json}

위 분석 결과를 바탕으로 실제 고객에게 전달할 따뜻하고 전문적인 답변을 작성해주세요.
""")
        
        return prompt | self.llm | StrOutputParser()
    
    def format_response(self, consultation_json: str) -> str:
        """JSON 상담 결과를 사용자 친화적인 응답으로 변환"""
        try:
            result = self.chain.invoke({
                "consultation_json": consultation_json
            })
            return result
        except Exception as e:
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"


def create_response_formatter_chain(llm: ChatGoogleGenerativeAI) -> ResponseFormatterChain:
    """응답 포맷터 체인 생성 헬퍼 함수"""
    return ResponseFormatterChain(llm)