"""
PDF 업로드 전용 서버
한번 실행하면 PDF들을 업로드하고 캐시해서 메인 앱에서 재사용
"""

import os
import json
import time
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

from google import genai
from google.genai.types import File

# 환경 변수 로드
load_dotenv()

app = FastAPI(title="PDF Upload Server", description="PDF 업로드 및 캐시 서버")

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 변수
pdf_cache: Dict[str, Dict[str, Any]] = {}
client = None

def initialize_client():
    """Google GenAI 클라이언트 초기화"""
    global client
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")
    client = genai.Client(api_key=api_key)
    print("✅ Google GenAI 클라이언트 초기화 완료")

def upload_pdfs_from_directory(directory_path: str) -> Dict[str, Dict[str, Any]]:
    """디렉토리의 모든 PDF를 업로드하고 메타데이터와 함께 캐시"""
    uploaded_files = {}
    
    print(f"📂 PDF 디렉토리 스캔: {directory_path}")
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                filepath = os.path.join(root, file)
                try:
                    print(f"📄 업로드 중: {file}")
                    start_time = time.time()
                    
                    uploaded_file = client.files.upload(file=filepath)
                    
                    upload_time = time.time() - start_time
                    file_size = os.path.getsize(filepath)
                    
                    uploaded_files[file] = {
                        "handle": uploaded_file,
                        "file_path": filepath,
                        "file_size": file_size,
                        "upload_time": upload_time,
                        "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    print(f"✅ 업로드 완료: {file} ({file_size/1024/1024:.1f}MB, {upload_time:.1f}초)")
                    
                except Exception as e:
                    print(f"❌ 업로드 실패: {file} - {e}")
                    
    return uploaded_files

@app.on_event("startup")
async def startup_event():
    """서버 시작시 PDF 업로드"""
    try:
        print("🚀 PDF 서버 시작...")
        initialize_client()
        
        # PDF 디렉토리 설정
        data_dir = os.path.join(os.getcwd(), "data", "textbooks")
        
        if not os.path.exists(data_dir):
            print(f"❌ PDF 디렉토리가 존재하지 않습니다: {data_dir}")
            return
            
        # PDF 업로드 시작
        global pdf_cache
        pdf_cache = upload_pdfs_from_directory(data_dir)
        
        print(f"🎉 PDF 서버 준비 완료! 총 {len(pdf_cache)}개 파일 업로드됨")
        
    except Exception as e:
        print(f"❌ 서버 시작 실패: {e}")

@app.get("/")
async def root():
    """서버 상태 확인"""
    return {
        "message": "PDF Upload Server",
        "status": "running",
        "cached_pdfs": len(pdf_cache),
        "pdf_list": list(pdf_cache.keys())
    }

@app.get("/pdf-cache")
async def get_pdf_cache():
    """캐시된 PDF 정보 반환"""
    if not pdf_cache:
        raise HTTPException(status_code=404, detail="캐시된 PDF가 없습니다.")
    
    # 핸들 객체는 JSON 직렬화할 수 없으므로 메타데이터만 반환
    cache_info = {}
    for filename, data in pdf_cache.items():
        cache_info[filename] = {
            "file_path": data["file_path"],
            "file_size": data["file_size"],
            "upload_time": data["upload_time"],
            "uploaded_at": data["uploaded_at"],
            "has_handle": data["handle"] is not None
        }
    
    return cache_info

@app.get("/pdf-handle/{filename}")
async def get_pdf_handle(filename: str):
    """특정 PDF 파일의 핸들 반환"""
    if filename not in pdf_cache:
        raise HTTPException(status_code=404, detail=f"PDF 파일을 찾을 수 없습니다: {filename}")
    
    return {
        "filename": filename,
        "handle_info": str(pdf_cache[filename]["handle"]),
        "metadata": {
            "file_size": pdf_cache[filename]["file_size"],
            "uploaded_at": pdf_cache[filename]["uploaded_at"]
        }
    }

@app.post("/reload-pdfs")
async def reload_pdfs():
    """PDF 캐시 재로드"""
    try:
        global pdf_cache
        data_dir = os.path.join(os.getcwd(), "data", "textbooks")
        pdf_cache = upload_pdfs_from_directory(data_dir)
        
        return {
            "message": "PDF 캐시 재로드 완료",
            "cached_pdfs": len(pdf_cache),
            "pdf_list": list(pdf_cache.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 재로드 실패: {str(e)}")

def get_cached_pdf_handles() -> Dict[str, File]:
    """외부에서 캐시된 PDF 핸들을 가져오는 함수"""
    if not pdf_cache:
        return {}
    
    return {filename: data["handle"] for filename, data in pdf_cache.items()}

if __name__ == "__main__":
    print("🚀 PDF 업로드 서버 시작...")
    uvicorn.run(
        "pdf_server:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=False,
        log_level="info"
    )