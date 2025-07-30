import time
import pandas as pd
import multiprocessing
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys # Keys 임포트
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException

# 크롤링할 카테고리와 URL 목록
URLS = {
    "리프팅": "https://www.gangnamunni.com/events?q=%EB%A6%AC%ED%94%84%ED%8C%85",
    "피부": "https://www.gangnamunni.com/events?q=%ED%94%BC%EB%B6%80",
    "지방성형": "https://www.gangnamunni.com/events?q=%EC%A7%80%EB%B0%A9%EC%8%B1%ED%98%95",
    "보톡스": "https://www.gangnamunni.com/events?q=%EB%B3%B4%ED%86%A1%EC%8A%A4",
    "필러": "https://www.gangnamunni.com/events?q=%ED%95%84%EB%9F%AC",
    "제모": "https://www.gangnamunni.com/events?q=%EC%A0%9C%EB%AA%A8",
    "모발이식": "https://www.gangnamunni.com/events?q=%EB%AA%A8%EB%B0%9C%EC%9D%B4%EC%8B%9D"
}

OUTPUT_FILE = 'gangnam_unni_final_aggressive.csv'

def scrape_category(category, url, output_file, lock):
    print(f"✅ [{category}] 작업 시작...")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920x1080')
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(service=service, options=options)
        stealth(driver, languages=["ko-KR", "ko"], vendor="Google Inc.", platform="MacIntel",
                webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
        
        driver.get(url)
        
        try:
            wait = WebDriverWait(driver, 15)
            scroll_container = wait.until(EC.visibility_of_element_located((By.ID, "frameMain")))
        except TimeoutException:
            print(f"❌ [{category}] 스크롤 컨테이너를 찾지 못했습니다.")
            return

        scraped_links = set()
        all_events_data = []
        patience = 10 # 인내심 횟수를 10으로 늘림

        print(f"📜 [{category}] 최종 스크롤 로직 시작...")
        while patience > 0:
            previous_item_count = len(scraped_links)

            # --- 1. 자바스크립트로 스크롤 ---
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_container)
            
            # --- 2. 키보드 Page Down 키 전송으로 추가 스크롤 시도 ---
            body = driver.find_element(By.TAG_NAME, 'body')
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(2.5)
            
            # 현재 화면의 데이터 파싱
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            events = soup.select('a[id^="event-card-component-ui-"]')
            
            for event in events:
                link = event.get('href')
                if link and link not in scraped_links:
                    scraped_links.add(link)
                    
                    try:
                        title = event.select_one('h2').get_text(strip=True)
                        clinic_info = event.select_one('h2 + span').get_text(strip=True)
                        price = event.select_one('h3').get_text(strip=True)
                        location, hospital_name = clinic_info.split('・') if '・' in clinic_info else ('N/A', clinic_info)

                        all_events_data.append({
                            '카테고리': category, '병원 이름': hospital_name.strip(), '위치': location.strip(),
                            '이벤트 제목': title, '가격': price
                        })
                    except (AttributeError, IndexError):
                        continue
            
            # --- 3. 실제 데이터 증가 여부로 종료 조건 판단 ---
            current_item_count = len(scraped_links)
            if current_item_count == previous_item_count:
                patience -= 1
                print(f"⚠️ [{category}] 새로운 데이터 없음. (남은 기회: {patience})")
                
                # --- 4. '더보기' 버튼이 있는지 확인하고 클릭 시도 ---
                try:
                    more_button = driver.find_element(By.XPATH, "//button[contains(text(), '더보기')]")
                    if more_button.is_displayed():
                        print("🖱️ '더보기' 버튼 발견! 클릭합니다.")
                        more_button.click()
                        patience = 10 # 버튼 클릭 후 다시 인내심 초기화
                except (ElementNotInteractableException, Exception):
                    pass # 버튼이 없거나 클릭할 수 없으면 그냥 넘어감

            else:
                patience = 10 # 새로운 데이터가 있으면 인내심 초기화
                print(f"📄 [{category}] {current_item_count}개 수집 완료...")

        if all_events_data:
            df = pd.DataFrame(all_events_data)
            with lock:
                df.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
            print(f"👍 [{category}] 작업 완료! 총 {len(all_events_data)}개 신규 저장.")
        else:
            print(f"⚠️ [{category}] 수집된 데이터가 없습니다.")

    except Exception as e:
        print(f"❌ [{category}] 작업 중 치명적 오류 발생: {e}")
    finally:
        if driver:
            driver.quit()

# 메인 실행 부분 (이전과 동일)
if __name__ == "__main__":
    core_count = multiprocessing.cpu_count()
    PROCESSES = min(4, core_count)
    print(f"병렬 작업을 위해 {PROCESSES}개의 프로세스를 사용합니다.")
    
    df_header = pd.DataFrame(columns=['카테고리', '병원 이름', '위치', '이벤트 제목', '가격'])
    df_header.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

    manager = multiprocessing.Manager()
    lock = manager.Lock()
    tasks = [(category, url, OUTPUT_FILE, lock) for category, url in URLS.items()]
    
    with multiprocessing.Pool(processes=PROCESSES) as pool:
        pool.starmap(scrape_category, tasks)

    print(f"\n🎉 모든 병렬 크롤링 작업이 완료되었습니다! '{OUTPUT_FILE}' 파일을 확인하세요.")