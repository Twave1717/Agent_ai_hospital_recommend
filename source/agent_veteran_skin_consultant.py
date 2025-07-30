import os
import sys
import pandas as pd
from dotenv import load_dotenv
from typing import Dict, List, Any

# LangChain 및 Pydantic 관련 라이브러리
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

# google.genai 클라이언트 직접 임포트
from google import genai
from google.genai import types
from google.genai.types import File, ContentDict

# --- 1. 사전 설정 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("'.env' 파일에 GOOGLE_API_KEY를 설정해주세요.")

# 프로젝트 기본 경로 설정
# 이 파일(agent_veteran_skin_consultant.py)이 'source' 폴더 안에 있다고 가정합니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_FILE_PATH = os.path.join(BASE_DIR, "source", "prompt", "veteran_skin_consultant.txt")
HOSPITAL_CSV_PATH = os.path.join(BASE_DIR, "data", "hospital_list", "gangnam_unni_final_aggressive.csv")
TEXTBOOK_DIR_PATH = os.path.join(BASE_DIR, "data", "textbook")

PROCEDURE_CATEGORIES = ["필러", "보톡스", "모발이식", "제모", '피부', '리프팅']

# --- 2. Pydantic 모델 정의 ---
class ProcedureCategory(BaseModel):
    is_detected: bool = Field(description="주어진 선택지 중에서 관련 시술 카테고리를 찾았는지 여부")
    category: str = Field(description=f"사용자 질문과 가장 관련 있는 시술 카테고리. 반드시 다음 선택지 중 하나여야 함: {', '.join(PROCEDURE_CATEGORIES)}")

class PdfSelection(BaseModel):
    selected_filename: str = Field(description="제공된 PDF 요약 목록을 참고하여, 사용자 질문에 답변하는 데 가장 도움이 될 PDF 파일의 이름을 선택합니다.")

# --- 3. 데이터 로딩 및 체인 생성 함수 ---

def upload_all_pdfs_once(directory_path: str, api_client: genai.Client) -> Dict[str, File]:
    """[최초 1회 실행] 디렉토리의 모든 PDF를 업로드하고, 파일명을 키로 하는 핸들 딕셔너리를 반환합니다."""
    uploaded_file_handles = {}
    print(f"'{directory_path}'의 모든 PDF 파일을 업로드합니다 (최초 1회 실행)...")
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                filepath = os.path.join(root, file)
                try:
                    print(f"-> Uploading: {file}")
                    # ✅ 수정: 'create' -> 'upload_file'로 변경하고, 파일 경로를 직접 사용
                    uploaded_file = api_client.files.upload(
                        file=filepath
                    )
                    uploaded_file_handles[file] = uploaded_file
                except Exception as e:
                    print(f"🚨 경고: '{file}' 파일 업로드 중 오류 발생. 이 파일은 건너뜁니다. 오류: {e}")
    print(f"✅ 총 {len(uploaded_file_handles)}개의 PDF 파일이 성공적으로 업로드 및 저장되었습니다.")
    return uploaded_file_handles

def get_pdf_summaries() -> Dict[str, str]:
    return {
        "Cosmetic Dermatology- Products And Procedures Cosmetic -- Draelos, Zoe Kececioglu -- ( WeLib.org ).pdf": "최신 시술 혁신 정보...",
        "Injectable Fillers in Aesthetic Medicine -- Mauricio de Maio, Berthold Rzany (auth.) -- ( WeLib.org ).pdf": "미용 필러의 임상 사용 개요. ...", # <-- 이 부분 수정
        "Skills for Communicating with Patients, 3rd Edition -- Juliet Draper, Suzanne M. Kurtz, Jonathan Silverman -- ( WeLib.org ).pdf": "환자와의 효과적인 소통 기술 탐구. ...",
        "Textbook of Cosmetic Dermatology (Series in Cosmetic and -- Robert L Baran; Howard Ira Maibach -- ( WeLib.org ).pdf": "미용 피부과학의 과학적 근거를 문서화. ..."
    }

def create_pdf_selection_chain(llm: ChatGoogleGenerativeAI, pdf_summaries: Dict[str, str]):
    """PDF 요약본을 보고 가장 적절한 파일을 선택하는 LangChain 체인을 생성합니다."""
    summaries_text = "\n".join([f"- 파일명: {fname}\n  요약: {summary}" for fname, summary in pdf_summaries.items()])
    system_prompt = f"당신은 사용자 질문을 분석하여, 질문에 답변하는 데 가장 도움이 될 참고 자료(PDF)를 단 하나만 골라주는 전문가입니다. 아래 제공된 PDF 파일들의 요약 목록을 보고, 사용자 질문과 가장 관련성이 높은 파일의 이름을 정확히 선택해야 합니다. << PDF 요약 목록 >>\n{summaries_text}"

    # ✅ 수정: list를 ChatPromptTemplate.from_messages로 감싸줍니다.
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "사용자 질문: {query}")
    ])

    structured_llm = llm.with_structured_output(PdfSelection)
    return prompt | structured_llm

def create_category_extraction_chain(llm: ChatGoogleGenerativeAI, categories_list: List[str]):
    """사용자 질문에서 시술 카테고리를 추출하는 LangChain 체인을 생성합니다."""
    system_prompt = f"사용자 질문을 분석하여 다음 카테고리 중 가장 관련성 높은 것을 하나만 분류하세요: {', '.join(categories_list)}. 관련 없으면 is_detected를 false로 설정하세요."

    # ✅ 수정: list를 ChatPromptTemplate.from_messages로 감싸줍니다.
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "사용자 질문: {query}")
    ])

    structured_llm = llm.with_structured_output(ProcedureCategory)
    return prompt | structured_llm

def load_prompt_from_file(filepath: str) -> str:
    """텍스트 파일에서 프롬프트 내용을 읽어옵니다."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f: return f.read()
    except FileNotFoundError:
        print(f"🚨 경고: 프롬프트 파일 '{filepath}'를 찾을 수 없습니다. 기본 프롬프트로 작동합니다.")
        return "당신은 친절한 피부과 상담 실장입니다."

def load_and_filter_hospitals(csv_path: str, category: str | None) -> str:
    """CSV 파일에서 병원 목록을 로드하고 특정 카테고리로 필터링합니다."""
    if not category: return "관련 시술 카테고리를 찾지 못해 병원 정보를 필터링할 수 없습니다."
    try:
        df = pd.read_csv(csv_path)
        filtered_df = df[df['카테고리'].str.contains(category, na=False)]
        if filtered_df.empty: return f"'{category}' 카테고리에 해당하는 병원 정보를 찾을 수 없습니다."
        # 상위 5개 병원 정보만 문자열로 변환하여 반환
        return filtered_df.head(5).to_string(index=False)
    except FileNotFoundError:
        print(f"🚨 경고: 병원 목록 파일 '{csv_path}'를 찾을 수 없습니다.")
        return "병원 목록 파일을 찾을 수 없어 병원 정보를 제공할 수 없습니다."

# --- 4. 메인 실행 로직 ---
if __name__ == "__main__":
    # 표준 입출력(stdin, stdout)의 인코딩을 UTF-8로 강제 설정
    # 터미널 환경에 따라 export 설정이 적용되지 않는 문제를 코드 레벨에서 해결
    try:
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
        print("✅ 스크립트 내부에서 표준 입출력 인코딩을 UTF-8로 설정했습니다.")
    except Exception as e:
        print(f"🚨 경고: 인코딩 설정 중 오류 발생. 일부 환경에서는 지원되지 않을 수 있습니다. 오류: {e}")

    print("🧠 지능형 PDF 선택 기능이 포함된 피부과 상담 챗봇을 시작합니다.")

    # ✅ 1. genai.Client를 처음에 한 번만 생성하여 공유
    client = genai.Client(api_key=GOOGLE_API_KEY)

    # 2. PDF 업로드 및 요약본 로드
    pdf_handles_dict = upload_all_pdfs_once(TEXTBOOK_DIR_PATH, client)
    pdf_summaries_dict = get_pdf_summaries()

    if not pdf_handles_dict:
        print("업로드된 PDF가 없어 챗봇을 실행할 수 없습니다.")
        exit()

    # ✅ 3. 공유된 client를 사용하여 LangChain LLM 초기화
    llm_for_chains = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest",
        temperature=0,
        client=client
    )

    # 4. 구조화된 출력을 위한 체인들 생성
    pdf_selector_chain = create_pdf_selection_chain(llm_for_chains, pdf_summaries_dict)
    category_extraction_chain = create_category_extraction_chain(llm_for_chains, PROCEDURE_CATEGORIES)

    # 5. 시스템 프롬프트 및 대화 기록 초기화
    system_prompt_template = load_prompt_from_file(PROMPT_FILE_PATH)
    conversation_history: List[ContentDict] = []

    while True:
        # --- [수정된 입력 처리 부분 시작] ---
        # 1. 프롬프트 메시지를 수동으로 출력하고, 즉시 표시되도록 합니다.
        print("\nAsk Me Anything! : ", end="", flush=True)

        # 2. 표준 입력 버퍼에서 인코딩되지 않은 원시(raw) 바이트를 직접 읽습니다.
        user_input_bytes = sys.stdin.buffer.readline()

        # 3. 바이트를 'euc-kr'로 디코딩합니다. 실패 시 'utf-8'로 다시 시도합니다.
        try:
            user_input = user_input_bytes.decode('euc-kr').strip()
        except UnicodeDecodeError:
            user_input = user_input_bytes.decode('utf-8').strip()

        # 사용자가 아무것도 입력하지 않고 엔터만 쳤을 경우, 루프의 처음으로 돌아갑니다.
        if not user_input:
            continue
        # --- [수정된 입력 처리 부분 끝] ---

        if user_input.lower() in ['exit', '종료']:
            print("상담을 종료합니다.")
            break

        # 단계 1: 질문에 가장 적합한 PDF 선택
        print("📚 질문에 가장 적합한 참고자료(PDF)를 선택 중입니다...")
        selection_result = pdf_selector_chain.invoke({"query": user_input})
        selected_filename = selection_result.selected_filename
        selected_pdf_handle = pdf_handles_dict.get(selected_filename)
        if selected_pdf_handle:
            print(f"✅ 선택된 파일: {selected_filename}")
        else:
            print(f"🚨 경고: 선택된 파일 '{selected_filename}'의 핸들을 찾을 수 없습니다. 첨부 없이 진행합니다.")

        # 단계 2: 시술 카테고리 추론
        print("💬 사용자 의도를 분석하여 시술 카테고리를 추론 중입니다...")
        category_info = category_extraction_chain.invoke({"query": user_input})
        category = category_info.category if category_info.is_detected else None
        print(f"✅ 추론된 카테고리: {category or '없음'}")

        # 단계 3: 병원 정보 필터링
        hospital_info_str = load_and_filter_hospitals(HOSPITAL_CSV_PATH, category)

        # ✅ [수정] 단계 4: API 호출 전, 현재 사용자 입력을 대화 기록에 미리 추가
        current_user_parts = [user_input]
        if selected_pdf_handle:
            current_user_parts.append(selected_pdf_handle)
        conversation_history.append({'role': 'user', 'parts': current_user_parts})

        # 최종 프롬프트에서 시스템 부분만 분리
        final_system_prompt = system_prompt_template.replace("((HOSPITAL_LIST))", hospital_info_str) \
                                                    .replace("((SUBMITTED_PHOTOS))", "사용자가 제출한 이미지가 없습니다.") \
                                                    .replace("((CONVERSATION_HISTORY))", str(conversation_history))

        print("\n🤖 상담 실장에게 답변을 요청하는 중...")
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest",
            contents=final_system_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        response_text = response.text
        print(f"\n상담 실장: {response_text}")

        # ✅ [수정] 단계 5: 모델의 답변만 대화 기록에 추가 (사용자 입력은 이미 추가됨)
        conversation_history.append({'role': 'model', 'parts': response_text})