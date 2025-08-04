import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image
import base64
import gspread
import toml
import os
from google.oauth2.service_account import Credentials


# ✅ 로컬/Cloud 환경에 따라 secrets 불러오기
if st.secrets.get("gcp_service_account", None):
    gcp_service_account = dict(st.secrets["gcp_service_account"])
    google_sheets = st.secrets["google_sheets"]
else:
    import toml, os
    secrets = toml.load(os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml"))
    gcp_service_account = secrets["gcp_service_account"]
    google_sheets = secrets["google_sheets"]

# ✅ Google 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(gcp_service_account, scopes=scope)
client = gspread.authorize(creds)

# ✅ Google Sheet 열기
sheet = client.open(google_sheets["google_sheet_name"]).sheet1
#st.success(f"✅ Google Sheets 연결 성공 → {google_sheets['google_sheet_name']}")

# ✅ 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
    """Google Sheets에 데이터 저장 - 상세 오류 정보 포함"""
    error_details = []  # 오류 정보를 저장할 리스트
    
    try:
        # 1단계: Google Sheets 클라이언트 설정
        client = setup_google_sheets()
        if not client:
            error_details.append("❌ Google Sheets 클라이언트 생성 실패")
            st.session_state.google_sheets_error = error_details
            return False
        
        error_details.append("✅ Google Sheets 클라이언트 생성 성공")
        
        # 2단계: 시트 이름 확인
        sheet_name = st.secrets["google_sheets"]["google_sheet_name"]
        error_details.append(f"🔍 찾고 있는 시트 이름: '{sheet_name}'")
        
        # 3단계: 시트 열기 시도
        try:
            sheet = client.open(sheet_name).sheet1
            error_details.append("✅ 구글 시트 열기 성공")
        except Exception as sheet_error:
            error_details.append(f"❌ 시트 열기 실패: {str(sheet_error)}")
            error_details.append(f"오류 타입: {type(sheet_error).__name__}")
            st.session_state.google_sheets_error = error_details
            return False
        
        # 4단계: 데이터 준비
        new_row = [
            name,
            id_number,
            format_korean_time(),
            ', '.join(selected_ingredients),
            ', '.join([f"{ingredient}: {', '.join(menus)}" for ingredient, menus in selected_menus.items()])
        ]
        error_details.append(f"✅ 데이터 준비 완료: {len(new_row)}개 컬럼")
        
        # 5단계: 구글 시트에 데이터 추가
        try:
            sheet.append_row(new_row)
            error_details.append("✅ 구글 시트에 데이터 추가 성공!")
            st.session_state.google_sheets_success = True
            st.session_state.google_sheets_error = error_details  # 성공 시에도 로그 저장
            return True
            
        except Exception as append_error:
            error_details.append(f"❌ 데이터 추가 실패: {str(append_error)}")
            error_details.append(f"오류 타입: {type(append_error).__name__}")
            st.session_state.google_sheets_error = error_details
            return False
        
    except Exception as e:
        error_details.append(f"❌ 전체 프로세스 오류: {str(e)}")
        error_details.append(f"오류 타입: {type(e).__name__}")
        st.session_state.google_sheets_error = error_details
        return False

# setup_google_sheets 함수도 수정
def setup_google_sheets():
    """Google Sheets API 설정 - 상세 오류 정보 포함"""
    try:
        # secrets 확인
        if "gcp_service_account" not in st.secrets:
            return None
            
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 필수 키 확인
        required_keys = ['type', 'project_id', 'private_key', 'client_email']
        for key in required_keys:
            if key not in creds_dict:
                return None
        
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        return client
        
    except Exception as e:
        return None

def get_korean_time():
    """한국 시간(KST)을 반환하는 함수"""
    return datetime.now(KST)

def format_korean_time():
    """한국 시간을 문자열로 포맷팅"""
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')
# 페이지 설정
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide"
)

# 이미지 경로 설정 (GitHub 배포용)
INGREDIENT_IMAGE_PATH = "images/ingredients"
MENU_IMAGE_PATH = "images/menus"

# 기존 코드에서 수정할 부분들

# 1. 관리자 패스워드 설정 (상단에 추가)
ADMIN_PASSWORD = "bluefood2025"  # 원하는 패스워드로 변경하세요

# 2. 세션 상태 초기화 부분에 추가
if 'step' not in st.session_state:
    st.session_state.step = 'info'
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}
# ✅ 관리자 인증 상태 추가
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_login' not in st.session_state:
    st.session_state.show_admin_login = False
def main():
    # ✅ 사이드바 글씨 크기 CSS 적용
    st.markdown(
        """
        <script>
        // 페이지 로드 시 스크롤을 상단으로 이동
        window.onload = function() {
            window.scrollTo(0, 0);
        };
        
        // Streamlit의 페이지 업데이트 감지하여 스크롤 이동
        setTimeout(function() {
            window.scrollTo(0, 0);
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <script>
        // 페이지 로드 시 스크롤을 상단으로 이동
        window.onload = function() {
            window.scrollTo(0, 0);
        };
        
        // Streamlit의 페이지 업데이트 감지하여 스크롤 이동
        setTimeout(function() {
            window.scrollTo(0, 0);
        }, 100);
        </script>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <style>
        /* 사이드바 전체 폰트 크기 */
        section[data-testid="stSidebar"] * {
            font-size: 22px !important;
        }
        /* 사이드바 헤더(타이틀)만 조금 더 크게 */
        section[data-testid="stSidebar"] h2 {
            font-size: 28px !important;
        }
        /* 사이드바 소제목(###) */
        section[data-testid="stSidebar"] h3 {
            font-size: 22px !important;
        }
        /* 사이드바의 리스트 및 일반 텍스트 */
        section[data-testid="stSidebar"] p, 
        section[data-testid="stSidebar"] li {
            font-size: 22px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # ✅ 사이드바 설정 - 관리자 로그인 추가
    with st.sidebar:
        # 🔹 연구 정보 카드
        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                color: white;
                box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            ">
                <h3 style="text-align:center; margin-bottom:10px;">📌 연구 정보</h3>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px;">
                    <strong>🔹 연구명</strong><br>
                    요양원 거주 고령자 대상 건강 상태 및<br>블루푸드 식이 데이터베이스 구축
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px; margin-bottom:10px;">
                    <strong>🔹 정부과제명</strong><br>
                    글로벌 블루푸드 미래리더 양성 프로젝트
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:10px; border-radius:10px;">
                    <strong>🔹 연구 담당자</strong><br>
                    류혜리, 유정연<br>(서울대학교 농생명공학부 박사과정)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # 🔹 관리자 로그인 섹션 추가
        st.markdown("---")
        
        if not st.session_state.is_admin:
            if st.button("🔐 관리자 로그인", use_container_width=True):
                st.session_state.show_admin_login = True
                st.rerun()
            
            if st.session_state.show_admin_login:
                with st.form("admin_login"):
                    password = st.text_input("관리자 패스워드", type="password")
                    login_btn = st.form_submit_button("로그인")
                    
                    if login_btn:
                        if password == ADMIN_PASSWORD:
                            st.session_state.is_admin = True
                            st.session_state.show_admin_login = False
                            st.success("관리자로 로그인되었습니다!")
                            st.rerun()
                        else:
                            st.error("잘못된 패스워드입니다.")
        else:
            # ✅ 관리자 로그인 상태
            st.success("🔐 관리자 모드")
            
            # 전체 데이터 다운로드 버튼
            if os.path.exists("bluefood_survey.xlsx"):
                with open("bluefood_survey.xlsx", 'rb') as file:
                    st.download_button(
                        label="📥 전체 설문 데이터 다운로드",
                        data=file.read(),
                        file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        use_container_width=True
                    )
                
                # 데이터 현황 표시
                try:
                    df = pd.read_excel("bluefood_survey.xlsx")
                    st.markdown(f"**📊 총 응답자: {len(df)}명**")
                    st.markdown(f"**📅 최근 응답: {df['설문일시'].max() if '설문일시' in df.columns else 'N/A'}**")
                except:
                    st.markdown("**📊 데이터 로드 오류**")
            else:
                st.info("아직 설문 데이터가 없습니다.")
            
            # 로그아웃 버튼
            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.is_admin = False
                st.session_state.show_admin_login = False
                st.rerun()
        
        # 🔹 설문 안내 카드
        st.markdown(
            """
            <div style="
                background: #ffffff;
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 20px;
                color: #333;
                font-size: 17px;
                line-height: 1.6;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                border: 1px solid #ddd;
            ">
                <h3 style="text-align:center; color:#0077b6; margin-bottom:10px;">📋 설문 안내</h3>
                <p><strong>🎯 목적</strong><br>블루푸드 선호도 조사</p>
                <p><strong>⏱️ 소요시간</strong><br>약 3-5분</p>
                <p><strong>📝 설문 단계</strong><br>1️⃣ 참여자 정보 입력<br>2️⃣ 선호 수산물 선택 (3-9개)<br>3️⃣ 선호 블루푸드 메뉴 선택<br>4️⃣ 결과 다운로드</p>
                <p><strong>🔒 개인정보 보호</strong><br>수집된 정보는 연구 목적으로만 사용되며,<br>개인정보는 안전하게 보호됩니다.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 🔹 진행 상황
        st.markdown("### 📊 진행 상황")
        if 'step' in st.session_state:
            if st.session_state.step == 'info':
                st.progress(0.25, "1단계: 정보 입력")
            elif st.session_state.step == 'ingredients':
                st.progress(0.5, "2단계: 수산물 선택")
            elif st.session_state.step == 'menus':
                st.progress(0.75, "3단계: 메뉴 선택")
            elif st.session_state.step == 'complete':
                st.progress(1.0, "✅ 설문 완료!")

    # ✅ 메인 콘텐츠 영역 - 이 부분이 누락되어 있었습니다!
    # 메인 타이틀
    st.title("🐟 블루푸드 선호도 조사")
    
    # 단계별 진행
    if st.session_state.step == 'info':
        show_info_form()
    elif st.session_state.step == 'ingredients':
        show_ingredient_selection()
    elif st.session_state.step == 'menus':
        show_menu_selection()
    elif st.session_state.step == 'complete':
        show_completion()


# show_completion 함수 수정 (오류 정보 표시 추가)
def show_completion():
    # 스크롤 상단 이동
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
        with st.expander("🔍 상세 오류 정보 (디버깅용)", expanded=True):
            for i, error in enumerate(st.session_state.google_sheets_error, 1):
                st.write(f"{i}. {error}")
        
        st.warning("⚠️ 데이터는 임시 백업 파일에 저장되었습니다")
    
    # ✅ secrets.toml 설정 정보 표시 (디버깅용)
    with st.expander("⚙️ 현재 설정 정보", expanded=False):
        try:
            if "gcp_service_account" in st.secrets:
                st.write("✅ secrets.toml 파일 로드됨")
                if "google_sheet_name" in st.secrets:
                    st.write(f"📋 시트 이름: '{secrets["google_sheets"]["google_sheet_name"]}'")
                if "google_sheet_id" in st.secrets:
                    st.write(f"🆔 시트 ID: {secrets["google_sheets"]['google_sheet_id'][:20]}...")
                
                # 서비스 계정 정보
                gcp_account = st.secrets["gcp_service_account"]
                if "client_email" in gcp_account:
                    st.write(f"📧 서비스 계정: {gcp_account['client_email']}")
                if "project_id" in gcp_account:
                    st.write(f"🏗️ 프로젝트 ID: {gcp_account['project_id']}")
            else:
                st.error("❌ secrets.toml 파일을 찾을 수 없습니다")
        except Exception as e:
            st.error(f"설정 정보 표시 오류: {str(e)}")
    
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
    
    # 관리자만 다운로드 버튼 표시
    if st.session_state.is_admin:
        st.markdown("---")
        st.markdown("### 🔐 관리자 전용")
        
        if 'filename' in st.session_state and st.session_state.filename and os.path.exists(st.session_state.filename):
            with open(st.session_state.filename, 'rb') as file:
                st.download_button(
                    label="📥 백업 파일 다운로드",
                    data=file.read(),
                    file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary",
                    use_container_width=True
                )
    
    # 새 설문 시작 버튼
    if st.button("🔄 새 설문 시작하기", use_container_width=True):
        # 세션 상태 초기화 (관리자 상태는 유지)
        admin_status = st.session_state.is_admin
        for key in list(st.session_state.keys()):
            if key not in ['is_admin', 'show_admin_login']:
                del st.session_state[key]
        st.session_state.is_admin = admin_status
        st.markdown(
            """
            <script>
            setTimeout(function() {
                window.scrollTo({top: 0, behavior: 'smooth'});
            }, 200);
            </script>
            """,
            unsafe_allow_html=True
        )
        st.rerun()

# 5. 추가 보안을 위한 관리자 전용 페이지 함수 (선택사항)
def show_admin_dashboard():
    """관리자 전용 대시보드"""
    if not st.session_state.is_admin:
        st.error("관리자 권한이 필요합니다.")
        return
    
    st.title("🔐 관리자 대시보드")
    
    if os.path.exists("bluefood_survey.xlsx"):
        try:
            df = pd.read_excel("bluefood_survey.xlsx")
            
            # 기본 통계
            st.subheader("📊 설문 통계")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("총 응답자 수", len(df))
            
            with col2:
                if '설문일시' in df.columns:
                    today_str = get_korean_time().strftime('%Y-%m-%d')
                    today_responses = len(df[df['설문일시'].str.contains(today_str, na=False)])
                    st.metric("오늘 응답자", today_responses)
                else:
                    st.metric("오늘 응답자", "N/A")
            
            with col3:
                if '선택한_수산물' in df.columns:
                    avg_ingredients = df['선택한_수산물'].str.split(', ').str.len().mean()
                    st.metric("평균 선택 수산물", f"{avg_ingredients:.1f}개")
            
            # 데이터 미리보기
            st.subheader("📋 최근 응답 데이터")
            st.dataframe(df.tail(10), use_container_width=True)
            
            # 전체 데이터 다운로드
            st.subheader("📥 데이터 다운로드")
            with open("bluefood_survey.xlsx", 'rb') as file:
                st.download_button(
                    label="전체 설문 데이터 다운로드",
                    data=file.read(),
                    file_name=f"bluefood_survey_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary"
                )
        
        except Exception as e:
            st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
    else:
        st.info("아직 설문 데이터가 없습니다.")
        
# 이미지 로드 함수
# ✅ 고정 크기 이미지 렌더링 함수
def render_image_fixed_size(img_path, width=180, height=120, placeholder="🐟"):
    """이미지를 고정 크기로 출력, 없으면 플레이스홀더"""
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        return f"""
        <div style="
            width:{width}px; 
            height:{height}px; 
            overflow:hidden; 
            border-radius:8px; 
            border:1px solid #ddd; 
            display:flex; 
            align-items:center; 
            justify-content:center; 
            background:#fff;">
            <img src="data:image/png;base64,{img_data}" 
                 style="width:100%; height:100%; object-fit:cover;">
        </div>
        """
    else:
        return f"""
        <div style="
            width:{width}px; 
            height:{height}px; 
            background:#f8f9fa; 
            border:2px dashed #dee2e6; 
            border-radius:8px; 
            display:flex; 
            flex-direction:column;
            align-items:center; 
            justify-content:center; 
            color:#6c757d;">
            <div style="font-size:1.5em;">{placeholder}</div>
            <div style="font-size:0.8em;">이미지 준비중</div>
        </div>
        """

def display_ingredient_with_image(ingredient, is_selected, key):
    jpg_path = os.path.join(INGREDIENT_IMAGE_PATH, f"{ingredient}.jpg")
    png_path = os.path.join(INGREDIENT_IMAGE_PATH, f"{ingredient}.png")

    # ✅ 이미지 크기 확대
    html_img = render_image_fixed_size(
        jpg_path, width=240, height=180
    ) if os.path.exists(jpg_path) else render_image_fixed_size(
        png_path, width=240, height=180, placeholder="🍽️"
    )

    # ✅ CSS (버튼형 체크박스)
    st.markdown("""
    <style>
    /* ✅ 체크박스 컨테이너를 버튼처럼 중앙 배치 */
    div.stCheckbox {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 5px;
    }
    /* ✅ 버튼 스타일 */
    div.stCheckbox > label {
        background: #f8f9fa;
        border: 2px solid #ccc;
        border-radius: 10px;
        padding: 8px 20px;
        cursor: pointer;
        font-size: 18px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    /* ✅ 체크된 상태 스타일 */
    div.stCheckbox > label:has(input:checked) {
        background: linear-gradient(135deg, #4facfe, #00f2fe);
        border-color: #0096c7;
        color: white;
    }
    /* ✅ 체크박스 자체 확대 */
    div.stCheckbox input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        # ✅ 식재료 이름 (가운데)
        st.markdown(
            f"<div style='text-align:center; margin-bottom:5px;'><strong style='font-size:20px;'>{ingredient}</strong></div>",
            unsafe_allow_html=True
        )

        # ✅ 이미지 가운데 정렬
        st.markdown(f"<div style='display:flex; justify-content:center;'>{html_img}</div>", unsafe_allow_html=True)

        # ✅ 체크박스도 중앙
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            checkbox_result = st.checkbox("선택", value=is_selected, key=key)

        return checkbox_result

        
def display_menu_with_image(menu, ingredient, is_selected, key):
    png_path = os.path.join(MENU_IMAGE_PATH, f"{menu}.png")
    jpg_path = os.path.join(MENU_IMAGE_PATH, f"{menu}.jpg")

    # ✅ 이미지 크기 확대
    html_img = render_image_fixed_size(
        png_path, width=240, height=180, placeholder="🍽️"
    ) if os.path.exists(png_path) else render_image_fixed_size(
        jpg_path, width=240, height=180, placeholder="🍽️"
    )

    # ✅ 버튼형 체크박스 CSS 적용
    st.markdown("""
    <style>
    /* ✅ 메뉴 체크박스 버튼 스타일 */
    div.stCheckbox {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 6px;
    }
    div.stCheckbox > label {
        background: #f8f9fa;
        border: 2px solid #ccc;
        border-radius: 10px;
        padding: 8px 20px;
        cursor: pointer;
        font-size: 18px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div.stCheckbox > label:has(input:checked) {
        background: linear-gradient(135deg, #4facfe, #00f2fe);
        border-color: #0096c7;
        color: white;
    }
    div.stCheckbox input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        # ✅ 메뉴명 중앙 정렬
        st.markdown(
            f"<div style='text-align:center; margin-bottom:5px;'><strong style='font-size:18px;'>{menu}</strong></div>",
            unsafe_allow_html=True
        )

        # ✅ 이미지 중앙
        st.markdown(f"<div style='display:flex; justify-content:center;'>{html_img}</div>", unsafe_allow_html=True)

        # ✅ 체크박스도 중앙
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            checkbox_result = st.checkbox("선택", value=is_selected, key=key)

        return checkbox_result

    


# save_to_excel 함수 수정 (구글 시트 우선, 실패 시 백업)
def save_to_excel(name, id_number, selected_ingredients, selected_menus):
    """데이터 저장 - Google Sheets 우선, 실패 시 로컬 엑셀 백업"""
    
    # 세션 상태 초기화
    st.session_state.google_sheets_success = False
    st.session_state.google_sheets_error = []
    
    # 1순위: Google Sheets에 저장 시도
    if save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
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
        return filename, final_df
        
    except Exception as e:
        # 백업 저장도 실패한 경우
        if 'google_sheets_error' not in st.session_state:
            st.session_state.google_sheets_error = []
        st.session_state.google_sheets_error.append(f"❌ 백업 파일 저장도 실패: {str(e)}")
        return None, None


# 수산물별 메뉴 데이터
MENU_DATA = {
    '맛살': {
        '밥/죽': ['게맛살볶음밥'],
        '무침': ['게맛살콩나물무침'],
        '볶음': ['맛살볶음'],
        '부침': ['맛살전']
    },
    '어란': {
        '밥/죽': ['날치알밥'],
        '면류': ['명란파스타'],
        '국/탕': ['알탕'],
        '찜': ['날치알달걀찜'],
        '무침': ['명란젓갈'],
        '볶음': ['날치알스크램블에그'],
        '부침': ['날치알계란말이'],
        '구이': ['명란구이']
    },
    '어묵': {
        '밥/죽': ['어묵볶음밥'],
        '면류': ['어묵우동'],
        '국/탕': ['어묵탕'],
        '조림': ['어묵조림'],
        '찜': ['콩나물어묵찜', '어묵찜'],
        '볶음': ['매콤어묵볶음', '간장어묵볶음'],
        '부침': ['어묵전'],
        '튀김': ['어묵고로케']
    },
    '쥐포': {
        '조림': ['쥐포조림'],
        '무침': ['쥐포무침'],
        '볶음': ['쥐포볶음'],
        '부침': ['쥐포전'],
        '튀김': ['쥐포튀김'],
        '구이': ['쥐포구이']
    },
    '김': {
        '밥/죽': ['김밥'],
        '무침': ['김무침'],
        '튀김': ['김부각'],
        '구이': ['김자반']
    },
    '다시마': {
        '무침': ['다시마채무침'],
        '볶음': ['다시마채볶음'],
        '튀김': ['다시마튀각']
    },
    '매생이': {
        '면류': ['매생이칼국수'],
        '국/탕': ['매생이굴국'],
        '부침': ['매생이전']
    },
    '미역': {
        '밥/죽': ['미역국밥'],
        '국/탕': ['미역국'],
        '무침': ['미역초무침'],
        '볶음': ['미역줄기볶음']
    },
    '파래': {
        '무침': ['파래무침'],
        '볶음': ['파래볶음'],
        '부침': ['물파래전']
    },
    '톳': {
        '밥/죽': ['톳밥'],
        '무침': ['톳무침']
    },
    '꼴뚜기': {
        '조림': ['꼴뚜기조림'],
        '찜': ['꼴뚜기찜'],
        '무침': ['꼴뚜기젓무침'],
        '볶음': ['꼴뚜기볶음']
    },
    '낙지': {
        '밥/죽': ['낙지비빔밥'],
        '면류': ['낙지수제비'],
        '국/탕': ['낙지연포탕'],
        '찜': ['낙지찜'],
        '무침': ['낙지초무침'],
        '볶음': ['낙지볶음'],
        '구이': ['낙지호롱구이'],
        '기타(생식)': ['낙지탕탕이']
    },
    '문어': {
        '밥/죽': ['문어볶음밥'],
        '면류': ['문어라면'],
        '국/탕': ['문어탕'],
        '조림': ['문어조림'],
        '찜': ['문어콩나물찜'],
        '무침': ['문어초무침'],
        '볶음': ['문어볶음'],
        '부침': ['문어전'],
        '튀김': ['문어튀김'],
        '기타(생식)': ['문어회']
    },
    '오징어': {
        '밥/죽': ['오징어덮밥'],
        '국/탕': ['오징어무국'],
        '조림': ['오징어조림'],
        '찜': ['오징어콩나물찜', '오징어숙회'],
        '무침': ['오징어초무침'],
        '볶음': ['오징어볶음'],
        '부침': ['오징어해물전'],
        '튀김': ['오징어튀김'],
        '구이': ['오징어버터구이'],
        '기타(생식)': ['오징어회']
    },
    '주꾸미': {
        '밥/죽': ['주꾸미볶음덮밥'],
        '면류': ['주꾸미감자수제비', '주꾸미짬뽕'],
        '국/탕': ['주꾸미연포탕'],
        '찜': ['주꾸미숙회', '주꾸미찜'],
        '무침': ['주꾸미무침'],
        '볶음': ['주꾸미볶음']
    },
    '가재': {
        '찜': ['가재찜'],
        '구이': ['가재구이']
    },
    '게': {
        '밥/죽': ['게살볶음밥'],
        '면류': ['게살파스타', '꽃게라면'],
        '국/탕': ['꽃게탕'],
        '조림': ['꽃게조림'],
        '찜': ['꽃게찜'],
        '무침': ['꽃게무침'],
        '볶음': ['꽃게볶음'],
        '튀김': ['꽃게강정'],
        '기타(생식)': ['간장게장', '양념게장']
    },
    '새우': {
        '밥/죽': ['새우볶음밥'],
        '면류': ['새우크림파스타'],
        '국/탕': ['새우달걀국', '얼큰새우매운탕'],
        '조림': ['새우조림'],
        '찜': ['새우달걀찜'],
        '무침': ['새우젓'],
        '볶음': ['건새우볶음'],
        '부침': ['새우전'],
        '튀김': ['새우튀김'],
        '구이': ['새우버터구이'],
        '기타(생식)': ['간장새우장', '양념새우장']
    },
    '다슬기': {
        '면류': ['다슬기수제비'],
        '국/탕': ['다슬기된장국'],
        '무침': ['다슬기무침'],
        '부침': ['다슬기파전']
    },
    '꼬막': {
        '밥/죽': ['꼬막비빔밥'],
        '면류': ['꼬막칼국수'],
        '국/탕': ['꼬막된장찌개'],
        '찜': ['꼬막찜'],
        '무침': ['꼬막무침'],
        '부침': ['꼬막전'],
        '구이': ['꼬막떡꼬치구이']
    },
    '가리비': {
        '밥/죽': ['가리비초밥'],
        '면류': ['가리비칼국수'],
        '국/탕': ['가리비탕'],
        '찜': ['가리비찜'],
        '무침': ['가리비초무침'],
        '볶음': ['가리비볶음'],
        '구이': ['가리비버터구이']
    },
    '골뱅이': {
        '밥/죽': ['골뱅이죽'],
        '면류': ['골뱅이비빔면'],
        '국/탕': ['골뱅이탕'],
        '무침': ['골뱅이무침'],
        '볶음': ['골뱅이볶음'],
        '튀김': ['골뱅이튀김'],
        '구이': ['골뱅이꼬치구이'],
        '기타(생식)': ['골뱅이물회']
    },
    '굴': {
        '밥/죽': ['굴국밥'],
        '면류': ['굴칼국수', '굴짬뽕'],
        '국/탕': ['매생이굴국', '굴순두부찌개'],
        '조림': ['굴조림'],
        '찜': ['굴찜'],
        '무침': ['굴무침'],
        '볶음': ['굴볶음'],
        '부침': ['굴전'],
        '튀김': ['굴튀김'],
        '구이': ['굴구이'],
        '기타(생식)': ['생굴']
    },
    '미더덕': {
        '밥/죽': ['미더덕밥'],
        '국/탕': ['미더덕된장찌개', '미더덕순두부찌개'],
        '찜': ['미더덕콩나물찜']
    },
    '바지락': {
        '밥/죽': ['바지락비빔밥'],
        '면류': ['바지락칼국수'],
        '국/탕': ['바지락미역국', '바지락순두부찌개'],
        '찜': ['바지락찜'],
        '무침': ['바지락무침'],
        '볶음': ['바지락볶음', '매콤바지락볶음'],
        '부침': ['바지락부추전']
    },
    '백합': {
        '밥/죽': ['백합볶음밥'],
        '면류': ['백합칼국수'],
        '국/탕': ['백합탕'],
        '찜': ['백합찜'],
        '무침': ['백합무침'],
        '볶음': ['백합볶음'],
        '구이': ['백합구이']
    },
    '소라': {
        '밥/죽': ['참소라야채죽'],
        '면류': ['소라비빔면'],
        '국/탕': ['소라된장찌개'],
        '조림': ['참소라장조림'],
        '찜': ['소라숙회'],
        '무침': ['소라무침'],
        '볶음': ['소라버터볶음'],
        '튀김': ['소라튀김'],
        '구이': ['소라구이'],
        '기타(생식)': ['소라회']
    },
    '재첩': {
        '국/탕': ['재첩국'],
        '무침': ['재첩무침'],
        '부침': ['재첩부추전']
    },
    '전복': {
        '밥/죽': ['전복죽'],
        '면류': ['전복파스타'],
        '국/탕': ['전복미역국'],
        '조림': ['전복장조림'],
        '찜': ['전복찜'],
        '무침': ['전복무침'],
        '볶음': ['전복볶음'],
        '구이': ['전복구이'],
        '기타(생식)': ['전복회']
    },
    '홍합': {
        '밥/죽': ['홍합죽'],
        '면류': ['홍합칼국수', '홍합짬뽕'],
        '국/탕': ['홍합탕', '홍합된장찌개'],
        '조림': ['홍합조림'],
        '찜': ['홍합찜'],
        '무침': ['홍합무침'],
        '볶음': ['홍합볶음'],
        '부침': ['홍합전'],
        '구이': ['홍합구이']
    },
    '가자미': {
        '국/탕': ['가자미미역국'],
        '조림': ['가자미조림'],
        '찜': ['가자미찜'],
        '부침': ['가자미전'],
        '튀김': ['가자미튀김'],
        '구이': ['가자미구이']
    },
    '다랑어': {
        '밥/죽': ['참치김밥'],
        '국/탕': ['참치김치찌개'],
        '볶음': ['참치양배추볶음'],
        '부침': ['참치달걀말이'],
        '구이': ['참치스테이크'],
        '생식류/절임류/장류': ['참치회']
    },
    '고등어': {
        '조림': ['고등어조림'],
        '구이': ['고등어구이']
    },
    '갈치': {
        '조림': ['갈치조림'],
        '구이': ['갈치구이']
    },
    '꽁치': {
        '국/탕': ['꽁치김치찌개'],
        '조림': ['꽁치조림'],
        '구이': ['꽁치구이']
    },
    '대구': {
        '국/탕': ['맑은대구탕', '대구매운탕'],
        '조림': ['대구조림'],
        '부침': ['대구전']
    },
    '멸치': {
        '밥/죽': ['멸치김밥'],
        '볶음': ['멸치볶음']
    },
    '명태': {
        '국/탕': ['황태미역국'],
        '조림': ['코다리조림'],
        '찜': ['명태찜'],
        '무침': ['북어채무침'],
        '구이': ['코다리구이']
    },
    '박대': {
        '조림': ['박대조림'],
        '구이': ['박대구이']
    },
    '뱅어': {
        '무침': ['뱅어포무침'],
        '튀김': ['뱅어포튀김']
    },
    '병어': {
        '조림': ['병어조림'],
        '구이': ['병어구이']
    },
    '삼치': {
        '조림': ['삼치조림'],
        '튀김': ['삼치튀김'],
        '구이': ['삼치구이']
    },
    '아귀': {
        '국/탕': ['아귀탕'],
        '찜': ['아귀찜']
    },
    '연어': {
        '밥/죽': ['연어덮밥'],
        '구이': ['연어구이'],
        '생식류/절임류/장류': ['연어회']
    },
    '임연수': {
        '조림': ['임연수조림'],
        '구이': ['임연수구이']
    },
    '장어': {
        '밥/죽': ['장어덮밥'],
        '조림': ['장어조림'],
        '찜': ['장어찜'],
        '튀김': ['장어튀김'],
        '구이': ['장어구이']
    },
    '조기': {
        '조림': ['조기조림'],
        '찜': ['조기찜'],
        '구이': ['조기구이']
    }
}

# 수산물 카테고리별 분류
INGREDIENT_CATEGORIES = {
    '🍤 가공수산물': ['맛살', '어란', '어묵', '쥐포'],
    '🌿 해조류': ['김', '다시마', '매생이', '미역', '파래', '톳'],
    '🦑 연체류': ['꼴뚜기', '낙지', '문어', '오징어', '주꾸미'],
    '🦀 갑각류': ['가재', '게', '새우'],
    '🐚 패류': ['다슬기', '꼬막', '가리비', '골뱅이', '굴', '미더덕', '바지락', '백합', '소라', '재첩', '전복', '홍합'],
    '🐟 어류': ['가자미', '다랑어', '고등어', '갈치', '꽁치', '대구', '멸치', '명태', '박대', '뱅어', '병어', '삼치', '아귀', '연어', '임연수', '장어', '조기']
}

# 세션 상태 초기화
if 'step' not in st.session_state:
    st.session_state.step = 'info'
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}

def show_info_form():
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
    st.subheader("📝 참여자 정보 입력")

    # ✅ CSS 강제 적용
    st.markdown(
        """
        <style>
        /* ✅ 레이블(성함, 식별번호) 스타일 */
        div.row-widget.stTextInput label {
            font-size: 26px !important;
            font-weight: bold !important;
            color: #222 !important;
        }

        /* ✅ 입력창 폰트 크기 */
        div.row-widget.stTextInput input {
            font-size: 24px !important;
            height: 50px !important;
        }

        /* ✅ 버튼 스타일 */
        div.stButton > button {
            font-size: 26px !important;
            font-weight: bold !important;
            height: 55px !important;
            border-radius: 10px !important;
            background: linear-gradient(135deg, #4facfe, #00f2fe);
            color: white !important;
        }
        div.stButton > button:hover {
            background: linear-gradient(135deg, #00b4d8, #0096c7);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ✅ 입력 폼
    with st.form("info_form"):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("성함", placeholder="홍길동", max_chars=20)

        with col2:
            id_number = st.text_input("식별번호", placeholder="예: HG001", max_chars=20)

        st.markdown("<br>", unsafe_allow_html=True)

        submitted = st.form_submit_button("설문 시작하기", use_container_width=True)

        if submitted:
            if name and id_number:
                st.session_state.name = name
                st.session_state.id_number = id_number
                st.session_state.step = 'ingredients'
                st.markdown(
                    """
                    <script>
                    setTimeout(function() {
                        window.scrollTo({top: 0, behavior: 'smooth'});
                    }, 200);
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                st.rerun()
            else:
                st.error("성함과 식별번호를 모두 입력해주세요.")



def show_ingredient_selection():
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
    
    st.subheader("🐟 수산물 원재료 선호도")
    
    # 안내 메시지
    st.info("**🔸 다음 수산물 중 선호하는 원재료를 선택해주세요**\n\n✓ 최소 3개 이상, 최대 9개까지 선택 가능합니다")
    
    # 선택 개수 표시
    selected_count = len(st.session_state.selected_ingredients)
    
    if 3 <= selected_count <= 9:
        st.success(f"✅ 선택된 품목: {selected_count}개")
    elif selected_count < 3:
        st.warning(f"⚠️ 선택된 품목: {selected_count}개 ({3-selected_count}개 더 선택 필요)")
    else:
        st.error(f"❌ 선택된 품목: {selected_count}개 (최대 9개까지만 선택 가능)")
    
    # 카테고리별 수산물 선택
    for category, ingredients in INGREDIENT_CATEGORIES.items():
        st.markdown(f"### {category}")
        
        # 수산물을 4열 그리드로 배치
        cols = st.columns(4)
        for i, ingredient in enumerate(ingredients):
            with cols[i % 4]:
                is_selected = ingredient in st.session_state.selected_ingredients
                
                # 이미지와 함께 식재료 표시
                selected = display_ingredient_with_image(
                    ingredient, 
                    is_selected, 
                    f"ingredient_{ingredient}"
                )
                
                if selected:
                    if ingredient not in st.session_state.selected_ingredients:
                        if len(st.session_state.selected_ingredients) < 9:
                            st.session_state.selected_ingredients.append(ingredient)
                            st.rerun()
                        else:
                            st.error("최대 9개까지만 선택할 수 있습니다.")
                            st.rerun()
                else:
                    if ingredient in st.session_state.selected_ingredients:
                        st.session_state.selected_ingredients.remove(ingredient)
                        st.rerun()
        
        st.markdown("---")
    
    # 다음 단계 버튼
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if 3 <= len(st.session_state.selected_ingredients) <= 9:
            if st.button("다음 단계로 →", type="primary", use_container_width=True):
                # 선택된 수산물에 대한 메뉴 딕셔너리 초기화
                st.session_state.selected_menus = {ingredient: [] for ingredient in st.session_state.selected_ingredients}
                st.session_state.step = 'menus'
                st.markdown(
                    """
                    <script>
                    setTimeout(function() {
                        window.scrollTo({top: 0, behavior: 'smooth'});
                    }, 200);
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                st.rerun()
        else:
            st.button("다음 단계로 →", disabled=True, use_container_width=True)

def show_menu_selection():
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
    st.subheader("🍽️ 선호 메뉴 선택")

    st.info("**🔸 선택하신 수산물로 만든 요리 중 선호하는 메뉴를 선택해주세요**\n\n✓ 각 수산물마다 최소 1개 이상의 메뉴를 선택해주세요")

    with st.expander("선택하신 수산물", expanded=True):
        ingredients_text = " | ".join([f"**{ingredient}**" for ingredient in st.session_state.selected_ingredients])
        st.markdown(f"🏷️ {ingredients_text}")

    all_valid = True

    for ingredient in st.session_state.selected_ingredients:
        st.markdown(f"### 🐟 {ingredient} 요리")

        if ingredient in MENU_DATA:
            # ✅ 카테고리 무시하고 메뉴만 리스트로 합치기
            all_menus = []
            for menu_list in MENU_DATA[ingredient].values():
                all_menus.extend(menu_list)

            # ✅ 4개씩 가로 배치
            for row_start in range(0, len(all_menus), 4):
                cols = st.columns(4)
                for col_idx, menu in enumerate(all_menus[row_start:row_start+4]):
                    with cols[col_idx]:
                        is_selected = menu in st.session_state.selected_menus.get(ingredient, [])
                        selected = display_menu_with_image(
                            menu,
                            ingredient,
                            is_selected,
                            f"menu_{ingredient}_{menu}"
                        )

                        if selected:
                            if menu not in st.session_state.selected_menus[ingredient]:
                                st.session_state.selected_menus[ingredient].append(menu)
                                st.rerun()
                        else:
                            if menu in st.session_state.selected_menus[ingredient]:
                                st.session_state.selected_menus[ingredient].remove(menu)
                                st.rerun()

        # ✅ 선택 여부 확인
        menu_count = len(st.session_state.selected_menus.get(ingredient, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"⚠️ {ingredient}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"✅ {ingredient}: {menu_count}개 메뉴 선택됨")

        st.markdown("---")

    # ✅ 버튼
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'ingredients'
            st.markdown(
                """
                <script>
                setTimeout(function() {
                    window.scrollTo({top: 0, behavior: 'smooth'});
                }, 200);
                </script>
                """,
                unsafe_allow_html=True
            )
            st.rerun()

    with col3:
        if all_valid:
            if st.button("설문 완료하기", type="primary", use_container_width=True):
                filename, df = save_to_excel(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
                st.session_state.filename = filename
                st.session_state.survey_data = df
                st.session_state.step = 'complete'
                st.markdown(
                    """
                    <script>
                    setTimeout(function() {
                        window.scrollTo({top: 0, behavior: 'smooth'});
                    }, 200);
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                st.rerun()
        else:
            st.button("설문 완료하기", disabled=True, use_container_width=True)



if __name__ == "__main__":
    main()
