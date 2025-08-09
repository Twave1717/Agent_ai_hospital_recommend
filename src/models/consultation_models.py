"""
상담 관련 Pydantic 모델들
"""

from pydantic import BaseModel, Field
from typing import List, Optional


PROCEDURE_CATEGORIES = ["필러", "보톡스", "모발이식", "제모", '피부', '리프팅']


class ProcedureCategory(BaseModel):
    """시술 카테고리 모델"""
    is_detected: bool = Field(description="주어진 선택지 중에서 관련 시술 카테고리를 찾았는지 여부")
    category: str = Field(description=f"사용자 질문과 가장 관련 있는 시술 카테고리. 반드시 다음 선택지 중 하나여야 함: {', '.join(PROCEDURE_CATEGORIES)}")


class PdfSelection(BaseModel):
    """PDF 선택 모델"""
    selected_filename: str = Field(description="제공된 PDF 요약 목록을 참고하여, 사용자 질문에 답변하는 데 가장 도움이 될 PDF 파일의 이름을 선택합니다.")


class ProcedurePlan(BaseModel):
    """시술 계획 모델"""
    recommended_sessions: str = Field(description="권장되는 시술 횟수 및 주기")
    expected_downtime: str = Field(description="예상되는 회복 기간 및 증상")
    pre_procedure_care: str = Field(description="시술 전 준비 및 주의사항")
    post_procedure_care: str = Field(description="시술 후 관리 방법 및 주의사항")
    expected_cost_range: str = Field(description="일반적인 시술 비용 범위")


class DetailedAnalysis(BaseModel):
    """상세 분석 모델"""
    option: str = Field(description="분석 대상이 되는 특정 시술의 이름")
    confidence_score: float = Field(description="제시된 시술 추천에 대한 AI의 확신도 (0-10)")
    medical_principle: str = Field(description="추천의 근거가 되는 의학적 원리")
    citation: str = Field(description="medical_principle을 뒷받침하는 출처")
    detailed_explanation: str = Field(description="해당 시술이 왜 이 사용자에게 적합한지에 대한 상세 설명")
    procedure_plan: ProcedurePlan = Field(description="시술 계획")


class SkinIssue(BaseModel):
    """피부 문제 모델"""
    identified_problem: str = Field(description="분석을 통해 식별된 구체적인 피부 문제")
    recommended_options: List[str] = Field(description="추천 시술 옵션들")
    detailed_analysis: List[DetailedAnalysis] = Field(description="각 시술 옵션에 대한 심층 분석")


class AnalyzedData(BaseModel):
    """분석된 데이터 모델"""
    submitted_photos: List[str] = Field(description="제출된 사진에 대한 객관적인 묘사")
    conversation_history: str = Field(description="사용자와의 전체 대화 내용 기록")


class ConsultationResponse(BaseModel):
    """전체 상담 응답 모델"""
    consultation_stage: str = Field(description="상담 단계", default="초기 상담")
    analyzed_data: AnalyzedData = Field(description="AI가 답변 생성에 사용한 원본 데이터")
    clarified_user_concern: str = Field(description="사용자의 질문을 명확하게 재구성한 내용")
    overall_summary: str = Field(description="상담 내용에 대한 전체적인 요약 및 핵심 권장 사항")
    skin_issues: List[SkinIssue] = Field(description="식별된 피부 문제들과 해결책")
    clinic_selection_guide: str = Field(description="좋은 병원을 선택하기 위한 실질적인 기준과 팁")