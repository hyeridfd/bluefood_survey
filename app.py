import streamlit as st
from datetime import datetime
import pandas as pd
import os

# 페이지 설정
st.set_page_config(page_title="블루푸드 선호도 조사", page_icon="🌊", layout="wide")

# ✅ HTML에서 CSS 로드
def load_custom_css():
    with open("bluefood_survey.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    css_start = html_content.find("<style>")
    css_end = html_content.find("</style>")
    css_code = html_content[css_start+7:css_end]
    st.markdown(f"<style>{css_code}</style>", unsafe_allow_html=True)

load_custom_css()

# ✅ 세션 상태 초기화
if "step" not in st.session_state:
    st.session_state.step = "info"
if "selected_ingredients" not in st.session_state:
    st.session_state.selected_ingredients = []
if "selected_menus" not in st.session_state:
    st.session_state.selected_menus = {}
if "name" not in st.session_state:
    st.session_state.name = ""
if "id_number" not in st.session_state:
    st.session_state.id_number = ""

# ✅ 데이터 (MENU_DATA, INGREDIENT_CATEGORIES) - 기존 코드 그대로 사용
MENU_DATA = {
    "맛살": {"밥/죽": ["게맛살볶음밥"], "무침": ["게맛살콩나물무침"], "볶음": ["맛살볶음"], "부침": ["맛살전"]}
    # (나머지 MENU_DATA는 기존 코드 그대로 복사)
}

INGREDIENT_CATEGORIES = {
    "🍤 가공수산물": ["맛살", "어란", "어묵", "쥐포"],
    # (나머지 카테고리도 기존 코드 그대로 복사)
}

# ✅ HTML 카드 UI로 재료 표시
def ingredient_card(ingredient, selected):
    selected_class = "selected" if selected else ""
    return f"""
    <div class="ingredient-item {selected_class}" onclick="window.parent.postMessage({{'select_ingredient':'{ingredient}'}}, '*')">
        <img src="images/ingredients/{ingredient}.jpg" class="ingredient-image" alt="{ingredient}">
        <div class="ingredient-name">{ingredient}</div>
    </div>
    """

# ✅ HTML 카드 UI로 메뉴 표시
def menu_card(ingredient, menu, selected):
    selected_class = "selected" if selected else ""
    return f"""
    <div class="menu-item {selected_class}" onclick="window.parent.postMessage({{'select_menu':'{ingredient}|{menu}'}}, '*')">
        <img src="images/menus/{menu}.jpg" class="menu-image" alt="{menu}">
        <div class="menu-text">{menu}</div>
    </div>
    """

# ✅ 단계별 화면
def show_info_form():
    st.markdown("""
    <div class="container">
        <div class="header"><h1>🌊 블루푸드 선호도 조사</h1><p>수산물에 대한 여러분의 선호도를 알려주세요</p></div>
        <div class="content"><h2 class="section-title">📝 참여자 정보 입력</h2></div>
    </div>
    """, unsafe_allow_html=True)

    name = st.text_input("성함", value=st.session_state.name, max_chars=20)
    id_number = st.text_input("식별번호", value=st.session_state.id_number, max_chars=20)

    if st.button("다음 단계로 →"):
        if name and id_number:
            st.session_state.name = name
            st.session_state.id_number = id_number
            st.session_state.step = "ingredients"
            st.experimental_rerun()
        else:
            st.error("성함과 식별번호를 모두 입력해주세요.")

def show_ingredient_selection():
    st.markdown("""
    <div class="container">
        <div class="content">
            <h2 class="section-title">🐟 수산물 원재료 선호도</h2>
            <div class="instruction"><strong>최소 3개, 최대 9개까지 선택</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 선택 수 표시
    count = len(st.session_state.selected_ingredients)
    if count < 3:
        st.warning(f"⚠️ {count}개 선택됨 (3개 이상 필요)")
    elif count > 9:
        st.error(f"❌ {count}개 선택됨 (최대 9개)")
    else:
        st.success(f"✅ {count}개 선택됨")

    # 카드 UI 출력
    for category, ingredients in INGREDIENT_CATEGORIES.items():
        st.markdown(f"### {category}")
        html_grid = '<div class="ingredient-grid">'
        for ing in ingredients:
            html_grid += ingredient_card(ing, ing in st.session_state.selected_ingredients)
        html_grid += "</div>"
        st.markdown(html_grid, unsafe_allow_html=True)

    # 버튼
    if 3 <= count <= 9:
        if st.button("다음 단계로 →", type="primary"):
            st.session_state.step = "menus"
            st.experimental_rerun()
    if st.button("← 이전 단계"):
        st.session_state.step = "info"
        st.experimental_rerun()

def show_menu_selection():
    st.markdown("""
    <div class="container">
        <div class="content">
            <h2 class="section-title">🍽️ 선호 메뉴 선택</h2>
            <div class="instruction"><strong>각 수산물마다 1개 이상 메뉴 선택</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    all_valid = True
    for ing in st.session_state.selected_ingredients:
        st.markdown(f"## 🐟 {ing} 요리")
        menus = MENU_DATA.get(ing, {})
        for cat, menu_list in menus.items():
            st.markdown(f"#### {cat}")
            html_menu = '<div class="menu-items">'
            for m in menu_list:
                html_menu += menu_card(ing, m, m in st.session_state.selected_menus.get(ing, []))
            html_menu += "</div>"
            st.markdown(html_menu, unsafe_allow_html=True)

        if len(st.session_state.selected_menus.get(ing, [])) == 0:
            all_valid = False
            st.warning(f"{ing} 메뉴를 선택해주세요.")

    # 버튼
    if st.button("← 이전 단계"):
        st.session_state.step = "ingredients"
        st.experimental_rerun()
    if all_valid and st.button("설문 완료하기", type="primary"):
        st.session_state.step = "complete"
        st.experimental_rerun()

def show_completion():
    st.success("🎉 설문이 완료되었습니다! 감사합니다.")
    st.balloons()
    st.markdown(f"**참여자:** {st.session_state.name}  \n**식별번호:** {st.session_state.id_number}")

    # 결과 저장
    df = pd.DataFrame({
        "이름": [st.session_state.name],
        "식별번호": [st.session_state.id_number],
        "설문일시": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "선호수산물": [", ".join(st.session_state.selected_ingredients)]
    })
    filename = f"bluefood_survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)

    with open(filename, "rb") as f:
        st.download_button("📥 결과 다운로드", f, file_name=filename)

    if st.button("🔄 새 설문 시작"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

# ✅ 단계 실행
if st.session_state.step == "info":
    show_info_form()
elif st.session_state.step == "ingredients":
    show_ingredient_selection()
elif st.session_state.step == "menus":
    show_menu_selection()
elif st.session_state.step == "complete":
    show_completion()
