"""
프로젝트 설정 파일
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 기본 경로 설정
BASE_DIR = Path(__file__).parent.parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"

# 데이터 파일 경로
TEXTBOOK_DIR_PATH = DATA_DIR / "textbooks"
HOSPITAL_CSV_PATH = DATA_DIR / "hospitals" / "gangnam_unni_final_aggressive.csv"
PROMPT_FILE_PATH = PROMPTS_DIR / "veteran_skin_consultant.txt"

# API 키
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 모델 설정
GEMINI_MODEL = "gemini-2.5-flash"
TEMPERATURE = 0.3

# 시술 카테고리
PROCEDURE_CATEGORIES = ["필러", "보톡스", "모발이식", "제모", '피부', '리프팅']

# 검증
if not GOOGLE_API_KEY:
    raise ValueError("'.env' 파일에 GOOGLE_API_KEY를 설정해주세요.")
    
# 필수 디렉토리 존재 확인
for directory in [TEXTBOOK_DIR_PATH, PROMPTS_DIR]:
    if not directory.exists():
        raise FileNotFoundError(f"필수 디렉토리가 없습니다: {directory}")

# 필수 파일 존재 확인  
for file_path in [HOSPITAL_CSV_PATH, PROMPT_FILE_PATH]:
    if not file_path.exists():
        raise FileNotFoundError(f"필수 파일이 없습니다: {file_path}")