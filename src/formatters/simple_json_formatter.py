"""
간단한 JSON 포맷터 - JSON을 채팅 스타일 답변으로 변환
"""

import json
from typing import Dict, Any, Union


def format_consultation_json_to_chat(json_data: Union[str, Dict[str, Any]], 
                                     pdf_filename: str = "", 
                                     category: str = "") -> str:
    """JSON 상담 결과를 자연스러운 채팅 스타일로 변환"""
    
    # 문자열인 경우 JSON 파싱
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except:
            return f"""👩‍⚕️ **AI 피부과 상담 실장** (풀 모드)

{json_data}

---
📚 **참조 PDF**: {pdf_filename[:50]}...
🏷️ **카테고리**: {category or '전체'}"""
    else:
        data = json_data
    
    response = """👩‍⚕️ **AI 피부과 상담 실장** (풀 모드)

안녕하세요! 전문 서적을 참조하여 상세히 분석해드렸습니다. ✨

"""
    
    # 질문 이해
    if "clarified_user_concern" in data:
        response += f"""**🎯 고객님 질문 이해**
{data["clarified_user_concern"]}

"""
    
    # 종합 분석
    if "overall_summary" in data:
        response += f"""**📋 종합 분석 결과**
{data["overall_summary"]}

"""
    
    # 피부 문제별 상세 분석
    if "skin_issues" in data:
        for idx, issue in enumerate(data["skin_issues"], 1):
            response += f"""**🔍 분석 결과 #{idx}**
**문제**: {issue.get("identified_problem", "분석 중...")}

**💡 추천 시술 옵션들**:
"""
            # 추천 옵션들
            for option in issue.get("recommended_options", []):
                response += f"• {option}\n"
            
            response += "\n"
            
            # 상세 분석
            for analysis in issue.get("detailed_analysis", []):
                option_name = analysis.get("option", "시술")
                confidence = analysis.get("confidence_score", 0)
                explanation = analysis.get("detailed_explanation", "")
                medical_principle = analysis.get("medical_principle", "")
                
                # 신뢰도에 따른 이모지
                if confidence >= 9:
                    conf_emoji = "🟢"
                    conf_text = "매우 확신"
                elif confidence >= 7:
                    conf_emoji = "🟡"
                    conf_text = "권장"
                else:
                    conf_emoji = "🟠"
                    conf_text = "고려 가능"
                
                response += f"""**{conf_emoji} {option_name}** ({conf_text} - 신뢰도: {confidence}/10)

**의학적 원리**: {medical_principle}

**상세 설명**: {explanation}

"""
                
                # 시술 계획
                if "procedure_plan" in analysis:
                    plan = analysis["procedure_plan"]
                    response += f"""**📅 시술 계획**
• **권장 횟수**: {plan.get("recommended_sessions", "상담 후 결정")}
• **회복 기간**: {plan.get("expected_downtime", "개인차 있음")}
• **시술 전 준비**: {plan.get("pre_procedure_care", "상담 시 안내")}
• **시술 후 관리**: {plan.get("post_procedure_care", "상담 시 안내")}
• **예상 비용**: {plan.get("expected_cost_range", "상담 시 안내")}

"""
                
                # 인용문 (있는 경우)
                if "citation" in analysis and analysis["citation"]:
                    response += f"""**📚 전문 서적 참조**: {analysis["citation"][:100]}...

"""
    
    # 병원 선택 가이드
    if "clinic_selection_guide" in data:
        response += f"""**🏥 좋은 병원 선택 가이드**

{data["clinic_selection_guide"]}

"""
    
    # 마무리
    response += f"""**💬 마무리 말씀**

고객님의 고민이 잘 해결되길 바랍니다! 추가 질문이 있으시면 언제든 문의해 주세요. 😊

---
📚 **참조 PDF**: {pdf_filename[:50]}{"..." if len(pdf_filename) > 50 else ""}
🏷️ **추론 카테고리**: {category or '전체'}
⚡ **처리 모드**: PDF 참조 풀 모드

*본 상담은 AI 분석 결과이며, 최종 진단 및 치료는 반드시 전문의와 상의하시기 바랍니다.*"""
    
    return response