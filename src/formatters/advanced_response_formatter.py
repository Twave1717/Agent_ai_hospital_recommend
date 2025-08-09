"""
고급 응답 포맷터
Google ADK 스타일의 구조화된 응답 생성
"""

import json
from typing import Dict, Any, List
from dataclasses import dataclass
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI


@dataclass
class FormattedSection:
    """포맷된 응답 섹션"""
    title: str
    content: str
    emoji: str = ""
    confidence_level: str = ""


class AdvancedResponseFormatter:
    """고급 응답 포맷터 - 구조화된 아름다운 응답 생성"""
    
    def __init__(self, llm: ChatGoogleGenerativeAI):
        self.llm = llm
        
    def format_consultation_response(self, consultation_json: Dict[str, Any]) -> str:
        """상담 JSON을 아름답게 포맷된 응답으로 변환"""
        
        try:
            # JSON이 문자열인 경우 파싱
            if isinstance(consultation_json, str):
                consultation_data = json.loads(consultation_json)
            else:
                consultation_data = consultation_json
                
            sections = []
            
            # 1. 헤더 섹션
            sections.append(self._create_header_section(consultation_data))
            
            # 2. 상태 분석 섹션
            sections.append(self._create_analysis_section(consultation_data))
            
            # 3. 추천 시술 섹션들
            sections.extend(self._create_treatment_sections(consultation_data))
            
            # 4. 병원 선택 가이드 섹션
            sections.append(self._create_clinic_guide_section(consultation_data))
            
            # 5. 마무리 섹션
            sections.append(self._create_closing_section())
            
            # 전체 응답 조립
            return self._assemble_response(sections)
            
        except Exception as e:
            return f"❌ 응답 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _create_header_section(self, data: Dict[str, Any]) -> FormattedSection:
        """헤더 섹션 생성"""
        stage = data.get('consultation_stage', '상담')
        concern = data.get('clarified_user_concern', '피부 상담')
        
        content = f"""안녕하세요! 👋 20년차 피부과 전문 상담 실장입니다.

**📋 {stage} 내용**
{concern}

고객님의 피부 상태를 꼼꼼히 분석해보았습니다. 전문적이면서도 이해하기 쉽게 설명드릴게요! 💫"""
        
        return FormattedSection("인사말", content, "👋")
    
    def _create_analysis_section(self, data: Dict[str, Any]) -> FormattedSection:
        """상태 분석 섹션 생성"""
        summary = data.get('overall_summary', '종합적인 분석을 진행했습니다.')
        analyzed_data = data.get('analyzed_data', {})
        
        content = f"""**🔍 종합 분석 결과**

{summary}

**📸 제출하신 사진 분석:**
"""
        
        submitted_photos = analyzed_data.get('submitted_photos', [])
        if submitted_photos:
            for photo_desc in submitted_photos:
                content += f"• {photo_desc}\n"
        else:
            content += "• 제출된 사진이 없어 텍스트 상담을 기준으로 분석했습니다.\n"
            
        return FormattedSection("상태 분석", content, "🔍")
    
    def _create_treatment_sections(self, data: Dict[str, Any]) -> List[FormattedSection]:
        """추천 시술 섹션들 생성"""
        sections = []
        skin_issues = data.get('skin_issues', [])
        
        for idx, issue in enumerate(skin_issues, 1):
            problem = issue.get('identified_problem', '피부 문제')
            detailed_analysis = issue.get('detailed_analysis', [])
            
            content = f"""**🎯 진단된 문제:** {problem}

**💡 추천 시술 옵션들:**
"""
            
            for analysis in detailed_analysis:
                option = analysis.get('option', '시술')
                confidence = analysis.get('confidence_score', 0)
                explanation = analysis.get('detailed_explanation', '')
                medical_principle = analysis.get('medical_principle', '')
                citation = analysis.get('citation', '')
                procedure_plan = analysis.get('procedure_plan', {})
                
                # 신뢰도에 따른 이모지 선택
                if confidence >= 8:
                    conf_emoji = "🟢"
                elif confidence >= 6:
                    conf_emoji = "🟡" 
                else:
                    conf_emoji = "🟠"
                    
                content += f"""
**{conf_emoji} {option}** (신뢰도: {confidence}/10)

**의학적 원리:** {medical_principle}

**상세 설명:** {explanation}

**시술 계획:**
• 권장 횟수: {procedure_plan.get('recommended_sessions', '상담 후 결정')}
• 회복 기간: {procedure_plan.get('expected_downtime', '개인차 있음')}
• 시술 전 준비: {procedure_plan.get('pre_procedure_care', '별도 안내')}
• 시술 후 관리: {procedure_plan.get('post_procedure_care', '별도 안내')}
• 예상 비용: {procedure_plan.get('expected_cost_range', '상담 시 안내')}

**참고 문헌:** {citation}
"""
            
            title = f"추천 시술 #{idx}" if len(skin_issues) > 1 else "추천 시술"
            sections.append(FormattedSection(title, content, "💎"))
            
        return sections
    
    def _create_clinic_guide_section(self, data: Dict[str, Any]) -> FormattedSection:
        """병원 선택 가이드 섹션 생성"""
        guide = data.get('clinic_selection_guide', '전문적인 병원을 선택하시길 권합니다.')
        
        content = f"""**🏥 좋은 병원 선택 가이드**

{guide}

**✅ 체크포인트:**
• 전문의 자격증 확인
• 사용 장비의 최신성
• 상담의 충실성
• 사후 관리 체계
• 합리적인 가격 정책"""
        
        return FormattedSection("병원 선택 가이드", content, "🏥")
    
    def _create_closing_section(self) -> FormattedSection:
        """마무리 섹션 생성"""
        content = """**💌 마무리 말씀**

고객님의 피부 고민이 잘 해결되길 바랍니다! 
추가 궁금한 점이 있으시면 언제든 문의해 주세요. 

아름다운 피부를 위한 여정을 함께 하겠습니다! ✨

---
*본 상담은 AI 기반 분석 결과이며, 최종 진단 및 치료는 반드시 전문의와 상의하시기 바랍니다.*"""
        
        return FormattedSection("마무리", content, "💌")
    
    def _assemble_response(self, sections: List[FormattedSection]) -> str:
        """섹션들을 조립하여 최종 응답 생성"""
        response_parts = []
        
        for section in sections:
            response_parts.append(section.content)
            response_parts.append("")  # 빈 줄 추가
            
        return "\n".join(response_parts).strip()


def create_advanced_response_formatter(llm: ChatGoogleGenerativeAI) -> AdvancedResponseFormatter:
    """고급 응답 포맷터 생성 헬퍼 함수"""
    return AdvancedResponseFormatter(llm)