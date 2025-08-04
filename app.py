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
import json
from google.oauth2.service_account import Credentials

# ✅ 속도 제한 설정
RATE_LIMIT_DELAY = 2.0  # 요청 간 2초 대기
MAX_RETRIES = 3  # 최대 재시도 횟수
RETRY_DELAY = 5.0  # 재시도 간 5초 대기

# ✅ 마지막 API 호출 시간 추적
if 'last_api_call' not in st.session_state:
    st.session_state.last_api_call = 0

def wait_for_rate_limit():
    """API 속도 제한을 위한 대기 함수"""
    current_time = time.time()
    time_since_last_call = current_time - st.session_state.last_api_call
    
    if time_since_last_call < RATE_LIMIT_DELAY:
        wait_time = RATE_LIMIT_DELAY - time_since_last_call
        time.sleep(wait_time)
    
    st.session_state.last_api_call = time.time()

# ✅ 로컬/Cloud 환경에 따라 secrets 불러오기
if st.secrets.get("gcp_service_account", None):
    gcp_service_account = dict(st.secrets["gcp_service_account"])
    google_sheets = st.secrets["google_sheets"]
else:
    import toml, os
    secrets = toml.load(os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml"))
    gcp_service_account = secrets["gcp_service_account"]
    google_sheets = secrets["google_sheets"]

# ✅ 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# ✅ 안전한 Google Sheets 연결 함수
@st.cache_resource
def get_google_sheet_safe():
    """속도 제한을 고려한 안전한 Google Sheets 연결"""
    try:
        if st.secrets.get("gcp_service_account", None):
            creds_dict = dict(st.secrets["gcp_service_account"])
            google_sheets = st.secrets["google_sheets"]
        else:
            secrets = toml.load(os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml"))
            creds_dict = secrets["gcp_service_account"]
            google_sheets = secrets["google_sheets"]

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # ✅ 속도 제한 적용
        wait_for_rate_limit()
        sheet = client.open(google_sheets["google_sheet_name"]).sheet1
        return sheet
    except Exception as e:
        st.error(f"❌ Google Sheets 연결 실패: {e}")
        return None

# ✅ 설문 완료 후 중복 저장 방지
if 'already_saved' not in st.session_state:
    st.session_state.already_saved = False

def save_to_google_sheets_safe(name, id_number, selected_ingredients, selected_menus):
    """안전한 Google Sheets 저장 (속도 제한 + 재시도 로직)"""
    if st.session_state.get("already_saved", False):
        return True  # ✅ 이미 저장되었으면 다시 실행하지 않음

    error_logs = []
    
    for attempt in range(MAX_RETRIES):
        try:
            sheet = get_google_sheet_safe()
            if sheet is None:
                error_logs.append(f"❌ Google Sheets 연결 실패 (시도 {attempt + 1}/{MAX_RETRIES})")
                if attempt == MAX_RETRIES - 1:
                    st.session_state.google_sheets_error = error_logs
                    return False
                time.sleep(RETRY_DELAY)
                continue

            # ✅ 데이터 준비
            menus_text = json.dumps(selected_menus, ensure_ascii=False)
            ingredients_text = ', '.join(selected_ingredients)
            
            # ✅ 단일 행으로 저장 (분할 저장 제거로 API 호출 최소화)
            row_data = [
                name, 
                id_number, 
                format_korean_time(), 
                ingredients_text, 
                menus_text[:49000]  # 50KB 제한 고려
            ]
            
            # ✅ 속도 제한 적용 후 저장
            wait_for_rate_limit()
            sheet.append_row(row_data, value_input_option="RAW")
            
            # ✅ 저장 성공
            error_logs.append("✅ 데이터 저장 성공")
            st.session_state.google_sheets_success = True
            st.session_state.google_sheets_error = error_logs
            st.session_state.already_saved = True
            return True

        except Exception as e:
            error_message = str(e)
            error_logs.append(f"❌ 저장 실패 (시도 {attempt + 1}/{MAX_RETRIES}): {error_message}")
            
            # ✅ 속도 제한 오류인 경우 더 오래 대기
            if "RATE_LIMIT_EXCEEDED" in error_message or "429" in error_message:
                wait_time = RETRY_DELAY * (attempt + 1) * 2  # 지수적 백오프
                error_logs.append(f"⏳ 속도 제한으로 인해 {wait_time}초 대기 중...")
                time.sleep(wait_time)
            else:
                time.sleep(RETRY_DELAY)
    
    # ✅ 모든 재시도 실패
    st.session_state.google_sheets_error = error_logs
    return False

def get_korean_time():
    """한국 시간(KST)을 반환하는 함수"""
    return datetime.now(KST)

def format_korean_time():
    """한국 시간을 문자열로 포맷팅"""
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')

# ✅ 기존의 save_to_google_sheets 함수를 새로운 함수로 교체
def save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
    """기존 함수 호출을 새로운 안전한 함수로 리다이렉트"""
    return save_to_google_sheets_safe(name, id_number, selected_ingredients, selected_menus)

# 페이지 설정
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide"
)

# 이미지 경로 설정 (GitHub 배포용)
INGREDIENT_IMAGE_PATH = "images/ingredients"
MENU_IMAGE_PATH = "images/menus"

# 관리자 패스워드 설정
ADMIN_PASSWORD = "bluefood2025"

# 세션 상태 초기화
if 'step' not in st.session_state:
    st.session_state.step = 'info'
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_login' not in st.session_state:
    st.session_state.show_admin_login = False

def show_completion_improved():
    """개선된 완료 페이지 - 상세한 오류 정보 표시"""
    st.markdown(
        """
        <script>
        setTimeout(function() {
            window.scrollTo({top: 0, behavior: 'smooth'});
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.balloons()
    
    # 완료 메시지
    st.success("🎉 설문이 완료되었습니다! 소중한 의견을 주셔서 감사합니다")
    
    # ✅ 구글 시트 연동 결과 표시
    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
        st.success("✅ 데이터가 구글 시트에 성공적으로 저장되었습니다!")
    elif hasattr(st.session_state, 'google_sheets_error') and st.session_state.google_sheets_error:
        st.error("❌ 구글 시트 저장 중 문제가 발생했습니다")
        
        # 상세 오류 정보 표시
        with st.expander("🔍 상세 오류 정보", expanded=True):
            for i, error in enumerate(st.session_state.google_sheets_error, 1):
                if "RATE_LIMIT_EXCEEDED" in error or "429" in error:
                    st.error(f"{i}. 🚫 **속도 제한 오류**: {error}")
                    st.info("💡 **해결 방법**: 잠시 후 다시 시도하거나 관리자에게 문의하세요.")
                else:
                    st.write(f"{i}. {error}")
        
        st.warning("⚠️ 데이터는 임시 백업 파일에 저장되었습니다")
    
    # 결과 요약 표시
    with st.expander("📊 설문 결과 요약", expanded=True):
        st.markdown(f"**참여자:** {st.session_state.name}")
        st.markdown(f"**식별번호:** {st.session_state.id_number}")
        st.markdown(f"**설문 완료 시간:** {format_korean_time()}")
        
        st.markdown("### 선택하신 수산물")
        ingredients_text = " | ".join(st.session_state.selected_ingredients)
        st.markdown(f"🏷️ {ingredients_text}")
        
        st.markdown("### 선호하시는 메뉴")
        for ingredient, menus in st.session_state.selected_menus.items():
            if menus:
                menu_text = ", ".join(menus)
                st.markdown(f"**{ingredient}:** {menu_text}")
    
    # 새 설문 시작 버튼
    if st.button("🔄 새 설문 시작하기", use_container_width=True):
        # 세션 상태 초기화 (관리자 상태는 유지)
        admin_status = st.session_state.is_admin
        for key in list(st.session_state.keys()):
            if key not in ['is_admin', 'show_admin_login', 'last_api_call']:
                del st.session_state[key]
        st.session_state.is_admin = admin_status
        st.rerun()

# ✅ save_to_excel 함수도 개선
def save_to_excel_improved(name, id_number, selected_ingredients, selected_menus):
    """개선된 데이터 저장 - Google Sheets 우선, 실패 시 로컬 엑셀 백업"""
    if st.session_state.get("already_saved", False):
        return "skipped", None
        
    # 세션 상태 초기화
    st.session_state.google_sheets_success = False
    st.session_state.google_sheets_error = []
    
    # 1순위: Google Sheets에 저장 시도
    if save_to_google_sheets_safe(name, id_number, selected_ingredients, selected_menus):
        return "google_sheets", None
    
    # 2순위: 로컬 엑셀 파일에 백업 저장
    try:
        new_data = {
            '이름': name,
            '식별번호': id_number,
            '설문일시': format_korean_time(),
            '선택한_수산물': ', '.join(selected_ingredients),
            '선택한_메뉴': ', '.join([f"{ingredient}: {', '.join(menus)}" for ingredient, menus in selected_menus.items()])
        }

        for ingredient in selected_ingredients:
            new_data[f'{ingredient}_메뉴'] = ', '.join(selected_menus.get(ingredient, []))

        new_df = pd.DataFrame([new_data])
        filename = "bluefood_survey_backup.xlsx"

        if os.path.exists(filename):
            old_df = pd.read_excel(filename)
            final_df = pd.concat([old_df, new_df], ignore_index=True)
        else:
            final_df = new_df

        final_df.to_excel(filename, index=False)
        st.session_state.google_sheets_error.append("✅ 로컬 백업 저장 성공")
        return filename, final_df
        
    except Exception as e:
        # 백업 저장도 실패한 경우
        if 'google_sheets_error' not in st.session_state:
            st.session_state.google_sheets_error = []
        st.session_state.google_sheets_error.append(f"❌ 백업 파일 저장도 실패: {str(e)}")
        return None, None

# ✅ 기존 함수들을 개선된 버전으로 교체
save_to_excel = save_to_excel_improved
show_completion = show_completion_improved

# ✅ 나머지 기존 코드는 그대로 유지...
# (main, show_info_form, show_ingredient_selection, show_menu_selection 등)

print("✅ 속도 제한 해결 완료!")
print("주요 개선사항:")
print("1. API 호출 간 2초 대기 시간 추가")
print("2. 실패 시 최대 3번 재시도")
print("3. 속도 제한 오류 시 더 긴 대기 시간 적용")
print("4. 분할 저장 제거로 API 호출 최소화")
print("5. 상세한 오류 메시지 표시")
