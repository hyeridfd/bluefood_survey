import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
import gspread
import os
import traceback
from google.oauth2.service_account import Credentials
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib import rcParams
import urllib.request

# ===================== 기본 설정 =====================

# 라이트 모드 강제 (모바일에서 다크/라이트 전환 때문에 대비가 깨지는 문제 방지)
LIGHT_FORCE_CSS = """
<style>
/* 전체 라이트 모드 강제 */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], [data-testid="stApp"] {
    background-color: #ffffff !important;
    color: #000000 !important;
}

.block-container {
    color: #000000 !important;
}

hr {
    border-color: #cccccc !important;
}

/* 모바일/태블릿/데스크탑 반응형 그리드 */
.ingredient-grid {
    display: grid;
    grid-gap: 8px;
    margin-bottom: 12px;
    /* 모바일 기본: 4열 */
    grid-template-columns: repeat(4, 1fr);
}

/* 타블렛 이상에서는 4열 유지 */
@media (min-width: 600px) {
    .ingredient-grid {
        grid-template-columns: repeat(4, 1fr);
    }
}

/* 메뉴 선택 화면 그리드 (동일하게 4열) */
.menu-grid {
    display: grid;
    grid-gap: 8px;
    margin-bottom: 12px;
    grid-template-columns: repeat(4, 1fr);
}

/* 카드 하나 (식재료용) */
.card-box {
    border: 2px solid #666666;
    background-color: #ffffff;
    color: #000000;
    border-radius:10px;
    padding:12px 6px;
    min-height:64px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    font-size:15px;
    font-weight:600;
    line-height:1.3;
    word-break: keep-all;
}
.card-box.selected {
    background-color: #00b4d8;
    border-color: #0096c7;
    color: #ffffff;
}

/* 체크박스는 화면에서 숨김 (state만 유지) */
.hidden-check {
    display:none;
}

/* 메뉴 카드 (2단계 화면) */
.menu-card-box {
    border: 2px solid #666666;
    background-color: #ffffff;
    color: #000000;
    border-radius:10px;
    padding:16px 10px;
    min-height:80px;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    font-size:18px;
    font-weight:600;
    line-height:1.3;
    word-break: keep-all;
}
.menu-card-box.selected {
    background-color: #00b4d8;
    border-color: #0096c7;
    color: #ffffff;
}

/* 체크박스 래퍼 숨기기 */
.hidden-check-wrapper {
    display:none;
}
</style>
"""
st.set_page_config(
    page_title="블루푸드 선호도 조사",
    page_icon="🐟",
    layout="wide"
)
st.markdown(LIGHT_FORCE_CSS, unsafe_allow_html=True)

# ===================== 폰트(한글 깨짐 방지) =====================
# NanumGothic 폰트 설정
FONT_PATH = "/tmp/NanumGothic.ttf"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"

if not os.path.exists(FONT_PATH):
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
    except Exception as e:
        print(f"⚠️ 폰트 다운로드 실패: {e}")

try:
    fontprop = fm.FontProperties(fname=FONT_PATH)
    rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['font.family'] = fontprop.get_name()
    mpl.rcParams['axes.unicode_minus'] = False
except Exception as e:
    print(f"⚠️ 폰트 로드 실패, 기본 폰트 사용: {e}")
    fontprop = None

# ===================== 시간/환경 =====================

KST = timezone(timedelta(hours=9))
ADMIN_PASSWORD = "bluefood2025"

def get_korean_time():
    return datetime.now(KST)

def format_korean_time():
    return get_korean_time().strftime('%Y-%m-%d %H:%M:%S')


# ===================== Google Sheets 연결 =====================

def get_google_sheet_cached():
    """Google Sheets 연결 (간단/안정화 버전)"""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ gcp_service_account 누락")
            return None
        
        if "google_sheets" not in st.secrets:
            st.error("❌ google_sheets 설정 누락")
            return None
        
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"]
            if "\\n" in pk:
                creds_dict["private_key"] = pk.replace("\\n", "\n")

        cfg = st.secrets["google_sheets"]
        sheet_name = cfg.get("google_sheet_name")
        sheet_id = cfg.get("google_sheet_id")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets"
        ]

        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)

        sheet = None
        if sheet_id:
            try:
                workbook = client.open_by_key(sheet_id)
                sheet = workbook.sheet1
            except Exception:
                pass
        if sheet is None and sheet_name:
            try:
                workbook = client.open(sheet_name)
                sheet = workbook.sheet1
            except Exception as e:
                st.error(f"❌ 시트 열기 실패: {e}")
                return None

        if sheet is None:
            st.error("❌ 시트를 찾을 수 없습니다.")
            return None

        # 헤더 확인
        first_row = sheet.row_values(1)
        if not first_row or all(cell == '' for cell in first_row):
            headers = ['이름', '식별번호', '설문일시', '선택한_수산물', '선택한_메뉴']
            sheet.append_row(headers)

        return sheet
    except Exception as e:
        st.error(f"❌ Google Sheets 연결 오류: {e}")
        st.code(traceback.format_exc())
        return None


def save_to_google_sheets(name, id_number, selected_ingredients, selected_menus):
    """Google Sheets 저장 (에러 나도 앱은 계속 진행)"""
    if st.session_state.get("already_saved", False):
        return True

    try:
        sheet = get_google_sheet_cached()
        if sheet is None:
            return False

        import json
        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = json.dumps(selected_ingredients, ensure_ascii=False)
        now_str = format_korean_time()

        new_row = [name, id_number, now_str, ingredients_text, menus_text]
        sheet.append_row(new_row)

        st.session_state.google_sheets_success = True
        return True
    except Exception as e:
        print(f"⚠️ Google Sheets 저장 오류: {e}")
        st.session_state.google_sheets_success = False
        return False


def save_to_excel(name, id_number, selected_ingredients, selected_menus):
    """Excel 로컬 백업"""
    try:
        filename = "bluefood_survey.xlsx"

        if os.path.exists(filename):
            df = pd.read_excel(filename)
        else:
            df = pd.DataFrame(columns=['이름', '식별번호', '설문일시', '선택한_수산물', '선택한_메뉴'])

        import json
        menus_text = json.dumps(selected_menus, ensure_ascii=False)
        ingredients_text = json.dumps(selected_ingredients, ensure_ascii=False)
        now_str = format_korean_time()

        new_row = {
            '이름': name,
            '식별번호': id_number,
            '설문일시': now_str,
            '선택한_수산물': ingredients_text,
            '선택한_메뉴': menus_text
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        df.to_excel(filename, index=False)
        
        return filename, df
    except Exception as e:
        print(f"❌ Excel 저장 오류: {e}")
        return None, None


# ===================== Session State 초기화 =====================

if 'step' not in st.session_state:
    st.session_state.step = 'info'
if 'name' not in st.session_state:
    st.session_state.name = ""
if 'id_number' not in st.session_state:
    st.session_state.id_number = ""
if 'selected_ingredients' not in st.session_state:
    st.session_state.selected_ingredients = []
if 'selected_menus' not in st.session_state:
    st.session_state.selected_menus = {}
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_login' not in st.session_state:
    st.session_state.show_admin_login = False
if 'google_sheets_success' not in st.session_state:
    st.session_state.google_sheets_success = False
if 'already_saved' not in st.session_state:
    st.session_state.already_saved = False


# ===================== 관리자 대시보드 =====================

def show_admin_dashboard(df):
    """관리자용 데이터 분석 대시보드"""
    st.markdown("---")
    st.markdown("### 📊 설문 데이터 분석")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("총 응답자", len(df))
    with col2:
        if '설문일시' in df.columns:
            st.metric("최근 응답", df['설문일시'].max())

    if '선택한_수산물' in df.columns:
        st.markdown("#### 수산물 선택 현황")
        ingredient_counts = {}
        for ingredients_json in df['선택한_수산물'].dropna():
            try:
                import json
                ingredients = json.loads(ingredients_json)
                for ing in ingredients:
                    ingredient_counts[ing] = ingredient_counts.get(ing, 0) + 1
            except:
                pass

        if ingredient_counts:
            ing_df = pd.DataFrame(list(ingredient_counts.items()), columns=['수산물', '선택 횟수'])
            ing_df = ing_df.sort_values('선택 횟수', ascending=False)
            st.bar_chart(ing_df.set_index('수산물'))
        else:
            st.info("아직 수산물 선택 데이터가 없습니다.")

    st.markdown("#### 응답 데이터")
    st.dataframe(df, use_container_width=True)


# ===================== 1단계: 참여자 정보 입력 =====================

def show_info_form():
    st.markdown("# 🐟 블루푸드 선호도 조사")
    st.markdown("---")
    st.markdown("## 1단계: 참여자 정보 입력")

    with st.form("info_form"):
        st.markdown("### 개인정보")
        name = st.text_input("성명", value=st.session_state.name, placeholder="예: 김영희")
        id_number = st.text_input("식별번호", value=st.session_state.id_number, placeholder="예: 001")

        submit = st.form_submit_button("다음 단계 →", use_container_width=True)

        if submit:
            if not name or not id_number:
                st.error("성명과 식별번호를 모두 입력해주세요.")
            else:
                st.session_state.name = name
                st.session_state.id_number = id_number
                st.session_state.step = 'ingredients'
                st.rerun()


# ===================== 2단계: 식재료 선택 (그리드 레이아웃) =====================

def show_ingredient_selection():
    st.markdown("# 🐟 블루푸드 선호도 조사")
    st.markdown("---")
    st.markdown("## 2단계: 선호하시는 수산물을 선택해주세요")
    st.markdown("**(3개 이상 9개 이하 선택 필수)**")

    ingredients = [
        "김밥", "김무침", "김부각", "김자반"
    ]

    # 먼저 체크박스 상태 업데이트 (숨겨진 컨테이너에서)
    st.markdown('<div class="hidden-check-wrapper">', unsafe_allow_html=True)
    
    checkbox_states = {}
    cols = st.columns(len(ingredients))
    for idx, ingredient in enumerate(ingredients):
        checkbox_key = f"ingredient_{idx}_{ingredient}"
        is_selected = ingredient in st.session_state.selected_ingredients
        
        with cols[idx]:
            new_state = st.checkbox(
                ingredient,
                value=is_selected,
                key=checkbox_key,
                label_visibility="collapsed"
            )
            checkbox_states[ingredient] = new_state
            
            # 상태 변경 감지
            if new_state and ingredient not in st.session_state.selected_ingredients:
                st.session_state.selected_ingredients.append(ingredient)
            elif not new_state and ingredient in st.session_state.selected_ingredients:
                st.session_state.selected_ingredients.remove(ingredient)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # 그리드 HTML 생성 - 4열
    grid_html = '<div class="ingredient-grid">'
    
    for idx, ingredient in enumerate(ingredients):
        # 현재 체크박스 상태
        is_selected = ingredient in st.session_state.selected_ingredients
        
        # 클래스 결정
        card_class = "card-box selected" if is_selected else "card-box"
        
        # 체크박스를 위한 고유 키
        checkbox_key = f"ingredient_{idx}_{ingredient}"
        
        # HTML에 카드 추가 (클릭 가능하도록)
        grid_html += f'<div class="{card_class}" onclick="document.getElementById(\'{checkbox_key}\').click();" style="cursor:pointer;">{ingredient}</div>'
    
    grid_html += '</div>'
    
    # HTML 렌더링
    st.markdown(grid_html, unsafe_allow_html=True)

    # 선택 현황
    selected_count = len(st.session_state.selected_ingredients)
    if selected_count == 0:
        st.warning("선택된 수산물이 없습니다.")
    else:
        st.success(f"✅ {selected_count}개 선택됨: {', '.join(st.session_state.selected_ingredients)}")

    # 하단 버튼
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'info'
            st.rerun()
    with col3:
        is_valid = 3 <= selected_count <= 9
        if st.button("다음 단계 →", use_container_width=True, disabled=not is_valid):
            if is_valid:
                st.session_state.step = 'menus'
                st.rerun()


# ===================== 3단계: 메뉴 선택 (각 수산물별 메뉴) =====================

def show_menu_selection():
    st.markdown("# 🐟 블루푸드 선호도 조사")
    st.markdown("---")
    st.markdown("## 3단계: 선호하시는 메뉴를 선택해주세요")

    # 메뉴 데이터
    menu_data = {
        "김밥": ["김밥 1", "김밥 2", "김밥 3", "김밥 4"],
        "김무침": ["김무침 1", "김무침 2", "김무침 3", "김무침 4"],
        "김부각": ["김부각 1", "김부각 2", "김부각 3", "김부각 4"],
        "김자반": ["김자반 1", "김자반 2", "김자반 3", "김자반 4"],
    }

    all_valid = True

    for ing_idx, ing_name in enumerate(st.session_state.selected_ingredients):
        st.markdown(f"### {ing_name}")

        menus = menu_data.get(ing_name, [])

        # 먼저 체크박스 상태 업데이트 (숨겨진 컨테이너에서)
        st.markdown('<div class="hidden-check-wrapper">', unsafe_allow_html=True)
        
        cols = st.columns(len(menus))
        local_updates = {}
        
        for menu_idx, menu_name in enumerate(menus):
            checkbox_key = f"menu_{ing_idx}_{menu_idx}_{ing_name}_{menu_name}"
            is_selected = menu_name in st.session_state.selected_menus.get(ing_name, [])
            
            with cols[menu_idx]:
                new_val = st.checkbox(
                    menu_name,
                    value=is_selected,
                    key=checkbox_key,
                    label_visibility="collapsed"
                )
                local_updates[menu_name] = new_val
        
        st.markdown('</div>', unsafe_allow_html=True)

        # 메뉴 그리드 HTML 생성 - 4열
        grid_html = '<div class="menu-grid">'
        
        for menu_idx, menu_name in enumerate(menus):
            is_selected = menu_name in st.session_state.selected_menus.get(ing_name, [])
            card_class = "menu-card-box selected" if is_selected else "menu-card-box"
            checkbox_key = f"menu_{ing_idx}_{menu_idx}_{ing_name}_{menu_name}"
            
            grid_html += f'<div class="{card_class}" onclick="document.getElementById(\'{checkbox_key}\').click();" style="cursor:pointer;">{menu_name}</div>'
        
        grid_html += '</div>'
        
        # 그리드 렌더링
        st.markdown(grid_html, unsafe_allow_html=True)

        # 초기화
        if ing_name not in st.session_state.selected_menus:
            st.session_state.selected_menus[ing_name] = []

        # 상태 업데이트
        for menu_name, new_val in local_updates.items():
            already = menu_name in st.session_state.selected_menus.get(ing_name, [])
            if new_val and not already:
                st.session_state.selected_menus[ing_name].append(menu_name)
            elif (not new_val) and already:
                st.session_state.selected_menus[ing_name].remove(menu_name)

        # 최소 1개 이상 선택 여부
        menu_count = len(st.session_state.selected_menus.get(ing_name, []))
        if menu_count == 0:
            all_valid = False
            st.warning(f"{ing_name}에 대해 최소 1개 이상의 메뉴를 선택해주세요.")
        else:
            st.success(f"{ing_name}: {menu_count}개 메뉴 선택됨")

        st.markdown("<hr>", unsafe_allow_html=True)

    # 하단 이동 버튼
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("← 이전 단계", use_container_width=True):
            st.session_state.step = 'ingredients'
            st.rerun()
    with col3:
        if st.button("설문 완료하기", use_container_width=True, disabled=not all_valid):
            if all_valid:
                filename, df = save_to_excel(
                    st.session_state.name,
                    st.session_state.id_number,
                    st.session_state.selected_ingredients,
                    st.session_state.selected_menus
                )
                if filename is not None or st.session_state.get("google_sheets_success", False):
                    st.session_state.already_saved = True
                    st.session_state.filename = filename
                    st.session_state.survey_data = df
                    st.session_state.step = 'complete'
                    st.rerun()
                else:
                    st.error("❌ 설문 데이터 저장에 실패했습니다. 다시 시도해주세요.")


def show_completion():
    st.balloons()
    st.success("🎉 설문이 완료되었습니다! 감사합니다.")

    if hasattr(st.session_state, 'google_sheets_success') and st.session_state.google_sheets_success:
        st.success("✅ 데이터가 Google Sheets에 저장되었습니다!")
    else:
        st.warning("⚠️ Google Sheets 연결에 문제가 있어 로컬 백업 파일에 저장되었습니다.")

    st.markdown(f"**참여자:** {st.session_state.name}")
    st.markdown(f"**식별번호:** {st.session_state.id_number}")
    st.markdown(f"**설문 완료 시간:** {format_korean_time()}")

    st.markdown("### 선택하신 수산물")
    st.markdown(" | ".join(st.session_state.selected_ingredients))

    st.markdown("### 선호하시는 메뉴")
    for ing_name, menus in st.session_state.selected_menus.items():
        if menus:
            st.markdown(f"**{ing_name}:** {', '.join(menus)}")

    # 관리자만 다운로드 버튼
    if st.session_state.is_admin and 'filename' in st.session_state and st.session_state.filename:
        if os.path.exists(st.session_state.filename):
            with open(st.session_state.filename, 'rb') as file:
                st.download_button(
                    label="📥 백업 파일 다운로드 (관리자 전용)",
                    data=file.read(),
                    file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary",
                    use_container_width=True
                )

    # 새 설문 시작
    if st.button("🔄 새 설문 시작하기", use_container_width=True):
        admin_status = st.session_state.is_admin
        admin_login_status = st.session_state.show_admin_login

        keys_to_keep = ['is_admin', 'show_admin_login']
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]

        st.session_state.is_admin = admin_status
        st.session_state.show_admin_login = admin_login_status
        st.session_state.step = 'info'
        st.session_state.selected_ingredients = []
        st.session_state.selected_menus = {}
        st.session_state.already_saved = False
        st.rerun()


def main():
    # 사이드바 (관리자 UI + 안내)
    with st.sidebar:
        # 연구 정보 카드
        st.markdown(
            """
            <div style="
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                padding: 16px;
                border-radius: 12px;
                margin-bottom: 16px;
                color: white;
                box-shadow: 0 4px 10px rgba(0,0,0,0.15);
                font-size:16px;
                line-height:1.4;
            ">
                <div style="font-size:18px;font-weight:700;text-align:center;margin-bottom:8px;">
                    📌 연구 정보
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px; margin-bottom:8px;">
                    <strong>🔹 연구명</strong><br>
                    요양원 거주 고령자 대상 건강 상태 및<br>블루푸드 식이 데이터베이스 구축
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px; margin-bottom:8px;">
                    <strong>🔹 정부과제명</strong><br>
                    글로벌 블루푸드 미래리더 양성 프로젝트
                </div>
                <div style="background: rgba(255,255,255,0.15); padding:8px; border-radius:8px;">
                    <strong>🔹 연구 담당자</strong><br>
                    류혜리, 유정연<br>(서울대학교 농생명공학부 박사과정)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 관리자 로그인
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
            st.success("🔐 관리자 모드")
            backup_files = ["bluefood_survey.xlsx", "bluefood_survey_backup.xlsx"]
            available_file = None
            for file in backup_files:
                if os.path.exists(file):
                    available_file = file
                    break

            if available_file:
                with open(available_file, 'rb') as file:
                    st.download_button(
                        label="📥 전체 설문 데이터 다운로드",
                        data=file.read(),
                        file_name=f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        use_container_width=True
                    )

                try:
                    df = pd.read_excel(available_file)
                    st.markdown(f"**📊 총 응답자: {len(df)}명**")
                    if '설문일시' in df.columns:
                        st.markdown(f"**📅 최근 응답: {df['설문일시'].max()}**")
                    show_admin_dashboard(df)
                except Exception:
                    st.markdown("**📊 데이터 로드 오류**")
            else:
                st.info("아직 설문 데이터가 없습니다.")

            if st.button("🚪 로그아웃", use_container_width=True):
                st.session_state.is_admin = False
                st.session_state.show_admin_login = False
                st.rerun()

        # 설문 안내
        st.markdown(
            """
            <div style="
                background:#ffffff;
                padding:16px;
                border-radius:12px;
                margin-bottom:16px;
                color:#333;
                font-size:16px;
                line-height:1.5;
                box-shadow:0 4px 10px rgba(0,0,0,0.1);
                border:1px solid #ddd;
            ">
                <div style="font-size:18px;font-weight:700;color:#0077b6;text-align:center;margin-bottom:8px;">
                    📋 설문 안내
                </div>
                <p><strong>🎯 목적</strong><br>블루푸드 선호도 조사</p>
                <p><strong>⏱️ 소요시간</strong><br>약 3-5분</p>
                <p><strong>📝 설문 단계</strong><br>
                    1️⃣ 참여자 정보 입력<br>
                    2️⃣ 선호 수산물 선택 (3-9개)<br>
                    3️⃣ 선호 메뉴 선택<br>
                    4️⃣ 완료
                </p>
                <p><strong>🔒 개인정보 보호</strong><br>
                    수집된 정보는 연구 목적으로만 사용되며,<br>
                    개인정보는 안전하게 보호됩니다.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 진행 상황
        st.markdown("### 📊 진행 상황")
        if st.session_state.step == 'info':
            st.progress(0.25, "1단계: 정보 입력")
        elif st.session_state.step == 'ingredients':
            st.progress(0.5, "2단계: 수산물 선택")
        elif st.session_state.step == 'menus':
            st.progress(0.75, "3단계: 메뉴 선택")
        elif st.session_state.step == 'complete':
            st.progress(1.0, "✅ 설문 완료!")

    # 메인 화면 단계 전환
    if st.session_state.step == 'info':
        show_info_form()
    elif st.session_state.step == 'ingredients':
        show_ingredient_selection()
    elif st.session_state.step == 'menus':
        show_menu_selection()
    elif st.session_state.step == 'complete':
        show_completion()


if __name__ == "__main__":
    main()
