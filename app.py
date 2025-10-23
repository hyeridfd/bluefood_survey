# UX 개선된 블루푸드 선호도 조사 앱
import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image
import base64
import gspread
import toml
import os
import time
import random
import traceback
from google.oauth2.service_account import Credentials

import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib import rcParams
from matplotlib import font_manager as fm
import urllib.request

# ✅ NanumGothic 폰트 다운로드 경로 (Streamlit Cloud에서도 사용 가능)
FONT_PATH = "/tmp/NanumGothic.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

# ✅ 폰트 다운로드 (없으면 자동 다운로드)
if not os.path.exists(FONT_PATH):
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    except Exception as e:
        print(f"⚠️ 폰트 다운로드 실패: {e}")

# ✅ fontprop 전역 정의
try:
    fontprop = fm.FontProperties(fname=FONT_PATH)
    rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"⚠️ 폰트 로드 실패, 기본 폰트 사용: {e}")
    fontprop = None


def show_admin_dashboard(df):
    """관리자 대시보드: 응답 현황 시각화 및 중복 응답 감지"""
    st.markdown("## 📊 관리자 대시보드")

    if df is None or df.empty:
        st.warning("⚠️ 응답 데이터가 없습니다.")
        return

    # ✅ 1. 응답 요약 정보
    st.markdown(f"**총 응답자 수:** {df['식별번호'].nunique()}명")
    st.markdown(f"**총 응답 수:** {len(df)}건")
    st.markdown(f"**최근 응답 시간:** {df['설문일시'].max()}")

    # ✅ 2. 중복 응답 감지
    st.markdown("### 🔍 중복 응답 감지")
    dup = df[df.duplicated('식별번호', keep=False)]
    if not dup.empty:
        st.warning(f"⚠️ {dup['식별번호'].nunique()}명의 중복 응답 발견")
        st.dataframe(dup)
    else:
        st.success("✅ 중복 응답 없음")

    # ✅ 3. 수산물 선호도 TOP5
    st.markdown("### 🐟 수산물 선호도 TOP5")
    if '선택한_수산물' in df.columns:
        try:
            all_ingredients = (
                df['선택한_수산물']
                .dropna()
                .astype(str)
                .str.split(',')
                .explode()
                .str.strip()
            )
            top_ing = all_ingredients.value_counts().head(5)

            if not top_ing.empty:
                fig1, ax1 = plt.subplots()
                sns.barplot(x=top_ing.values, y=top_ing.index, ax=ax1, palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"])

                # ✅ fontprop이 정의되어 있을 때만 적용
                try:
                    ax1.set_title("선호 수산물 TOP5", fontproperties=fontprop)
                    ax1.set_xlabel("응답 수", fontproperties=fontprop)
                    ax1.set_ylabel("수산물", fontproperties=fontprop)

                # ✅ y축 ticklabel (수산물 이름) 폰트 적용
                    for label in ax1.get_yticklabels():
                        label.set_fontproperties(fontprop)
                    for label in ax1.get_xticklabels():
                        label.set_fontproperties(fontprop)

                except NameError:
                    ax1.set_title("선호 수산물 TOP5")

                st.pyplot(fig1)
            else:
                st.info("📌 수산물 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (수산물): {e}")
    else:
        st.error("⚠️ '선택한_수산물' 컬럼이 없습니다.")


    # --- 4. 메뉴 선호도 ---
    st.markdown("### 🍽️ 메뉴 선호도 TOP5")
    menu_list = []
    if '선택한_메뉴' in df.columns:
        try:
            for menus in df['선택한_메뉴'].dropna():
                for item in str(menus).split(","):
                    if ":" in item:
                        menu_list.append(item.split(":", 1)[1].strip())
                    else:
                        menu_list.append(item.strip())

            if menu_list:
                menu_series = pd.Series(menu_list)
                top_menu = menu_series.value_counts().head(5)

                fig2, ax2 = plt.subplots()
                sns.barplot(x=top_menu.values, y=top_menu.index, ax=ax2, palette=["#A7C7E7", "#89CFF0", "#7EC8E3", "#5DADE2", "#3498DB"])
                ax2.set_title("선호 메뉴 TOP5", fontproperties=fontprop)
                ax2.set_xlabel("응답 수", fontproperties=fontprop)
                ax2.set_ylabel("메뉴", fontproperties=fontprop)

                for label in ax2.get_yticklabels():
                    label.set_fontproperties(fontprop)
                for label in ax2.get_xticklabels():
                    label.set_fontproperties(fontprop)

                st.pyplot(fig2)
            else:
                st.info("📌 메뉴 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (메뉴): {e}")
    else:
        st.error("⚠️ '선택한_메뉴' 컬럼이 없습니다.")

    # --- 5. 날짜별 응답 추이 ---
    st.markdown("### ⏱️ 날짜별 응답 추이")
    if '설문일시' in df.columns:
        try:
            df['설문일자'] = pd.to_datetime(df['설문일시'], errors='coerce').dt.date
            daily_count = df.groupby('설문일자').size().reset_index(name='응답수')

            if not daily_count.empty:
                fig3, ax3 = plt.subplots()
                ax3.plot(daily_count['설문일자'], daily_count['응답수'], marker='o')
                ax3.set_ylabel("응답 수")
                ax3.set_xlabel("날짜")
                ax3.set_title("날짜별 응답 추이", fontproperties=fontprop)
                ax3.set_xlabel("날짜", fontproperties=fontprop)
                ax3.set_ylabel("응답 수", fontproperties=fontprop)

                ax3.grid(True, linestyle="--", alpha=0.5)
                fig3.autofmt_xdate()
                st.pyplot(fig3)
            else:
                st.info("📌 날짜별 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터 로드 오류 (날짜): {e}")
    
# ✅ 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# ✅ 관리자 패스워드 설정
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    """한국 시간(KST)을 반환하는 함수"""
    return datetime.now(KST)

def format_korean_time():
    """한국 시간을 문자열로 포맷팅"""
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')


#@st.cache_resource
def get_google_sheet_cached():
    """개선된 Google Sheets 연결 함수"""
    # 디버깅 정보를 항상 표시하도록 수정
    debug_container = st.empty()
    with debug_container.container():
        st.write("🟢 [DEBUG] Google Sheets 연결 시도 시작됨")
        
        try:
            # Secrets 확인
            if "gcp_service_account" not in st.secrets:
                st.error("❌ [DEBUG] gcp_service_account 누락")
                return None
            
            if "google_sheets" not in st.secrets:
                st.error("❌ [DEBUG] google_sheets 설정 누락")
                return None
            
            # 서비스 계정 정보 가져오기
            creds_dict = dict(st.secrets["gcp_service_account"])
            st.write("🟢 [DEBUG] 서비스 계정 이메일:", creds_dict.get("client_email", "없음"))
            st.write("🟢 [DEBUG] 프로젝트 ID:", creds_dict.get("project_id", "없음"))

            # private_key 줄바꿈 변환 확인
            if "private_key" in creds_dict:
                original_key = creds_dict["private_key"]
                if "\\n" in original_key:
                    creds_dict["private_key"] = original_key.replace("\\n", "\n")
                    st.write("🟢 [DEBUG] private_key 줄바꿈 변환 완료")
                else:
                    st.write("🟢 [DEBUG] private_key 이미 올바른 형태")
                
                st.write("🟢 [DEBUG] private_key 길이:", len(creds_dict["private_key"]))
                st.write("🟢 [DEBUG] private_key 시작:", creds_dict["private_key"][:50] + "...")
                st.write("🟢 [DEBUG] private_key 끝:", "..." + creds_dict["private_key"][-50:])

            # Google Sheets 설정
            google_sheets_config = st.secrets["google_sheets"]
            sheet_name = google_sheets_config.get("google_sheet_name")
            sheet_id = google_sheets_config.get("google_sheet_id")
            
            st.write("🟢 [DEBUG] 구글 시트 이름:", sheet_name)
            st.write("🟢 [DEBUG] 구글 시트 ID:", sheet_id)

            # Scope 설정
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 인증 객체 생성 - JSON 형태로 변환
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            st.write("🟢 [DEBUG] 인증 객체 생성 성공")
            
            # gspread 클라이언트 생성
            client = gspread.authorize(creds)
            st.write("🟢 [DEBUG] gspread 클라이언트 생성 성공")
            
            # Google Sheet 접근 시도 - ID로 접근
            if sheet_id:
                try:
                    sheet = client.open_by_key(sheet_id).sheet1
                    st.write("🟢 [DEBUG] 시트 ID로 접근 성공")
                except Exception as e:
                    st.error(f"❌ [DEBUG] 시트 ID로 접근 실패: {e}")
                    # 이름으로 시도
                    if sheet_name:
                        try:
                            sheet = client.open(sheet_name).sheet1
                            st.write("🟢 [DEBUG] 시트 이름으로 접근 성공")
                        except Exception as e2:
                            st.error(f"❌ [DEBUG] 시트 이름으로도 접근 실패: {e2}")
                            return None
                    else:
                        return None
            elif sheet_name:
                try:
                    sheet = client.open(sheet_name).sheet1
                    st.write("🟢 [DEBUG] 시트 이름으로 접근 성공")
                except Exception as e:
                    st.error(f"❌ [DEBUG] 시트 접근 실패: {e}")
                    return None
            else:
                st.error("❌ [DEBUG] 시트 이름과 ID 모두 없음")
                return None
            
            # 시트 정보 확인
            rows = sheet.row_count
            cols = sheet.col_count
            st.write(f"🟢 [DEBUG] 시트 크기: {rows}행 × {cols}열")
            
            # 현재 데이터 확인
            existing_data = sheet.get_all_records()
            st.write(f"🟢 [DEBUG] 현재 저장된 데이터: {len(existing_data)}행")
            
            # 5초 후 디버깅 정보 제거
            time.sleep(5)
            debug_container.empty()
            
            return sheet
            
        except Exception as e:
            st.error(f"❌ [CRITICAL] Google Sheets 연결 실패")
            st.error(f"에러 타입: {type(e).__name__}")
            st.error(f"에러 메시지: {str(e)}")
            st.error(f"상세 트레이스백:")
            st.code(traceback.format_exc())
            return None
        

def get_google_sheet():
    """Google Sheets 연결 함수 (캐싱 없음) - 매번 호출 시 실제 연결 시도"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ gcp_service_account 설정이 누락되었습니다.")
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 줄바꿈 처리
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # 인증
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # 시트 접근
        google_sheets_config = st.secrets["google_sheets"]
        sheet_id = google_sheets_config.get("google_sheet_id")
        sheet_name = google_sheets_config.get("google_sheet_name")
        
        if sheet_id:
            try:
                return client.open_by_key(sheet_id).sheet1
            except:
                if sheet_name:
                    return client.open(sheet_name).sheet1
        elif sheet_name:
            return client.open(sheet_name).sheet1
        
        return None
        
    except Exception as e:
        st.error(f"❌ Google Sheets 연결 실패: {e}")
        return None

def save_to_google_sheet(sheet, name, id_number, ingredients, menus):
    """Google Sheets에 설문 데이터 저장"""
    try:
        # 메뉴를 문자열로 변환
        menu_str = ""
        for ingredient, menu_list in menus.items():
            if menu_list:
                menu_items = ", ".join(menu_list)
                menu_str += f"{ingredient}: {menu_items} | "
        menu_str = menu_str.rstrip(" | ")
        
        # 새 데이터 행
        new_row = [
            format_korean_time(),
            name,
            id_number,
            ", ".join(ingredients),
            menu_str
        ]
        
        # 헤더가 없으면 추가
        if sheet.row_count == 0 or not sheet.get_all_records():
            headers = ['설문일시', '이름', '식별번호', '선택한_수산물', '선택한_메뉴']
            sheet.append_row(headers)
        
        # 데이터 추가
        sheet.append_row(new_row)
        
        st.success("✅ Google Sheets 저장 성공!")
        return True
        
    except Exception as e:
        st.error(f"❌ Google Sheets 저장 실패: {e}")
        return False

def save_to_excel(name, id_number, ingredients, menus):
    """엑셀 파일로 저장하고 Google Sheets에도 저장 시도"""
    survey_dir = Path("survey_responses")
    survey_dir.mkdir(exist_ok=True)
    
    filename = survey_dir / f"survey_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    # 메뉴를 문자열로 변환
    menu_str = ""
    for ingredient, menu_list in menus.items():
        if menu_list:
            menu_items = ", ".join(menu_list)
            menu_str += f"{ingredient}: {menu_items} | "
    menu_str = menu_str.rstrip(" | ")
    
    # 데이터프레임 생성
    new_data = pd.DataFrame({
        '설문일시': [format_korean_time()],
        '이름': [name],
        '식별번호': [id_number],
        '선택한_수산물': [", ".join(ingredients)],
        '선택한_메뉴': [menu_str]
    })
    
    # 기존 파일이 있으면 읽어서 추가
    if filename.exists():
        try:
            existing_data = pd.read_excel(filename)
            combined_data = pd.concat([existing_data, new_data], ignore_index=True)
        except:
            combined_data = new_data
    else:
        combined_data = new_data
    
    # 엑셀 파일로 저장
    try:
        combined_data.to_excel(filename, index=False)
        st.success(f"✅ 로컬 백업 파일 저장 성공: {filename}")
    except Exception as e:
        st.error(f"❌ 파일 저장 실패: {e}")
        return None, combined_data
    
    # Google Sheets 저장 시도
    try:
        sheet = get_google_sheet()
        if sheet:
            success = save_to_google_sheet(sheet, name, id_number, ingredients, menus)
            st.session_state.google_sheets_success = success
        else:
            st.session_state.google_sheets_success = False
    except Exception as e:
        st.error(f"❌ Google Sheets 저장 중 오류: {e}")
        st.session_state.google_sheets_success = False
    
    return filename, combined_data

# 수산물 카테고리별 데이터
SEAFOOD_CATEGORIES = {
    "🐟 생선류": {
        "items": ["고등어", "갈치", "조기", "명태", "연어", "참치", "삼치", "대구", "가자미", "광어", "도미", "농어"],
        "description": "신선한 바다와 민물의 다양한 생선",
        "icon": "🐟"
    },
    "🦐 갑각류": {
        "items": ["새우", "게", "랍스터", "가재"],
        "description": "영양 만점 갑각류 해산물",
        "icon": "🦐"
    },
    "🦑 연체류": {
        "items": ["오징어", "문어", "낙지", "주꾸미", "한치"],
        "description": "쫄깃한 식감의 연체동물",
        "icon": "🦑"
    },
    "🦪 패류": {
        "items": ["굴", "전복", "홍합", "바지락", "가리비", "꼬막", "조개", "소라"],
        "description": "미네랄이 풍부한 조개류",
        "icon": "🦪"
    },
    "🌊 해조류": {
        "items": ["미역", "다시마", "김", "파래", "톳", "매생이"],
        "description": "건강한 바다의 채소",
        "icon": "🌊"
    },
    "🐠 기타 수산물": {
        "items": ["멸치", "꽁치", "정어리", "장어", "미꾸라지", "해삼", "멍게", "성게"],
        "description": "특별한 맛과 영양의 수산물",
        "icon": "🐠"
    }
}

# 메뉴 데이터
MENU_DATA = {
    '고등어': {
        '구이/조림': ['고등어구이', '고등어조림', '고등어김치찜'],
        '기타': ['고등어무조림', '고등어된장조림']
    },
    '갈치': {
        '구이/조림': ['갈치구이', '갈치조림'],
        '국/탕': ['갈치국']
    },
    '조기': {
        '구이': ['조기구이'],
        '국/탕': ['조깃국']
    },
    '명태': {
        '국/탕': ['명태국', '동태찌개'],
        '기타': ['명태전', '황태해장국']
    },
    '연어': {
        '구이': ['연어스테이크', '연어구이'],
        '회/초밥': ['연어회', '연어초밥'],
        '샐러드': ['연어샐러드']
    },
    '참치': {
        '회/초밥': ['참치회', '참치초밥'],
        '구이': ['참치스테이크'],
        '기타': ['참치김밥', '참치마요덮밥']
    },
    '삼치': {
        '구이': ['삼치구이'],
        '조림': ['삼치조림']
    },
    '대구': {
        '국/탕': ['대구탕', '대구지리'],
        '찜': ['대구뽈찜']
    },
    '가자미': {
        '구이': ['가자미구이'],
        '조림': ['가자미조림'],
        '회': ['가자미회']
    },
    '광어': {
        '회': ['광어회', '광어초밥'],
        '국/탕': ['광어매운탕']
    },
    '도미': {
        '구이': ['도미구이'],
        '찜': ['도미찜'],
        '회': ['도미회']
    },
    '농어': {
        '회': ['농어회'],
        '구이': ['농어구이'],
        '찜': ['농어찜']
    },
    '새우': {
        '구이': ['새우구이', '대하구이'],
        '튀김': ['새우튀김', '새우천부라'],
        '볶음': ['새우볶음밥'],
        '기타': ['새우장', '새우깡']
    },
    '게': {
        '찜': ['꽃게찜', '대게찜'],
        '탕': ['꽃게탕', '게장탕'],
        '기타': ['간장게장', '양념게장']
    },
    '랍스터': {
        '구이': ['랍스터구이', '버터랍스터'],
        '찜': ['랍스터찜']
    },
    '가재': {
        '구이': ['가재구이'],
        '국/탕': ['가재미역국']
    },
    '오징어': {
        '볶음': ['오징어볶음', '오징어덮밥'],
        '회': ['오징어회'],
        '튀김': ['오징어튀김'],
        '기타': ['오징어순대', '오징어무국']
    },
    '문어': {
        '숙회': ['문어숙회'],
        '볶음': ['문어볶음'],
        '기타': ['타코야키']
    },
    '낙지': {
        '볶음': ['낙지볶음', '낙곱새'],
        '탕': ['낙지연포탕'],
        '회': ['산낙지']
    },
    '주꾸미': {
        '볶음': ['주꾸미볶음'],
        '삼겹살': ['주꾸미삼겹살'],
        '샤브샤브': ['주꾸미샤브샤브']
    },
    '한치': {
        '회': ['한치회'],
        '구이': ['한치구이'],
        '볶음': ['한치볶음']
    },
    '굴': {
        '전': ['굴전'],
        '국': ['굴국밥'],
        '무침': ['굴무침'],
        '튀김': ['굴튀김']
    },
    '전복': {
        '죽': ['전복죽'],
        '구이': ['전복버터구이'],
        '찜': ['전복찜'],
        '회': ['전복회']
    },
    '홍합': {
        '탕': ['홍합탕'],
        '찜': ['홍합찜'],
        '파스타': ['홍합파스타']
    },
    '바지락': {
        '국': ['바지락칼국수', '바지락된장국'],
        '술찜': ['바지락술찜'],
        '파스타': ['봉골레파스타']
    },
    '가리비': {
        '구이': ['가리비구이'],
        '찜': ['가리비찜'],
        '버터구이': ['가리비버터구이']
    },
    '꼬막': {
        '무침': ['꼬막무침'],
        '비빔밥': ['꼬막비빔밥'],
        '전': ['꼬막전']
    },
    '조개': {
        '구이': ['조개구이'],
        '탕': ['조개탕'],
        '찜': ['조개찜']
    },
    '소라': {
        '무침': ['소라무침'],
        '구이': ['소라구이'],
        '숙회': ['소라숙회']
    },
    '미역': {
        '국': ['미역국', '산모미역국'],
        '무침': ['미역무침'],
        '냉국': ['미역냉국']
    },
    '다시마': {
        '육수': ['다시마육수'],
        '무침': ['다시마무침'],
        '튀각': ['다시마튀각']
    },
    '김': {
        '구이': ['김구이'],
        '무침': ['김무침'],
        '김밥': ['김밥']
    },
    '파래': {
        '무침': ['파래무침'],
        '전': ['파래전'],
        '김': ['파래김']
    },
    '톳': {
        '무침': ['톳무침'],
        '볶음': ['톳볶음']
    },
    '매생이': {
        '국': ['매생이국'],
        '전': ['매생이전']
    },
    '멸치': {
        '볶음': ['멸치볶음'],
        '국물': ['멸치국수', '멸치육수'],
        '조림': ['멸치조림']
    },
    '꽁치': {
        '구이': ['꽁치구이'],
        '조림': ['꽁치조림'],
        '김치찌개': ['꽁치김치찌개']
    },
    '정어리': {
        '구이': ['정어리구이'],
        '조림': ['정어리조림']
    },
    '장어': {
        '구이': ['장어구이', '장어소금구이'],
        '탕': ['장어탕'],
        '덮밥': ['장어덮밥']
    },
    '미꾸라지': {
        '탕': ['추어탕', '미꾸라지매운탕'],
        '튀김': ['미꾸라지튀김']
    },
    '해삼': {
        '회': ['해삼회'],
        '초무침': ['해삼초무침']
    },
    '멍게': {
        '회': ['멍게회'],
        '비빔밥': ['멍게비빔밥']
    },
    '성게': {
        '비빔밥': ['성게비빔밥'],
        '초밥': ['성게초밥
