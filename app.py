import streamlit as st
import pandas as pd
import os
from datetime import datetime
from pathlib import Path
from PIL import Image
import base64

# 페이지 설정
st.set_page_config(page_title="블루푸드 선호도 조사", page_icon="🌊", layout="wide")

# 이미지 경로
INGREDIENT_IMAGE_PATH = "images/ingredients"
MENU_IMAGE_PATH = "images/menus"

# 이미지 로드 및 base64 변환
def load_image(image_path):
    try:
        if os.path.exists(image_path):
            return Image.open(image_path)
        return None
    except Exception:
        return None

def image_to_base64(image):
    if image is None:
        return ""
    from io import BytesIO
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

# 🔥 공통 버튼 스타일 (이미지 카드)
def render_image_button(label, image, is_selected, key):
    border = "#764ba2" if is_selected else "#ddd"
    bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" if is_selected else "white"
    text = "white" if is_selected else "#2c3e50"
    img64 = image_to_base64(image) if image else ""

    html = f"""
    <div style="border:3px solid {border}; border-radius:15px; padding:10px;
                background:{bg}; cursor:pointer; text-align:center;
                transition:transform 0.2s; box-shadow:0 4px 12px rgba(0,0,0,0.1);"
         onclick="window.location.href='?action={key}'">
        <img src="data:image/png;base64,{img64}" style="width:200px;height:150px;object-fit:cover;border-radius:10px;"/>
        <p style="color:{text};font-size:1.2em;font-weight:600;margin-top:10px;">{label}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# 세션 초기화
if "step" not in st.session_state:
    st.session_state.step = "info"
if "selected_ingredients" not in st.session_state:
    st.session_state.selected_ingredients = []
if "selected_menus" not in st.session_state:
    st.session_state.selected_menus = {}

# ✅ 재료 데이터 (예시)
INGREDIENTS = ["맛살", "어란", "어묵", "쥐포", "김", "다시마", "매생이", "미역", "파래", "톳"]

# ✅ 메뉴 데이터 (간단 예시)
MENU_DATA = {
    "맛살": ["게맛살볶음밥", "맛살전"],
    "어란": ["명란파스타", "알탕"],
    "김": ["김밥", "김무침"],
}

# ✅ 정보 입력 페이지
def show_info():
    st.title("🌊 블루푸드 선호도 조사")
    name = st.text_input("성함", placeholder="홍길동")
    id_number = st.text_input("식별번호", placeholder="예: 2024001")
    if st.button("설문 시작하기", type="primary"):
        if name and id_number:
            st.session_state.name = name
            st.session_state.id_number = id_number
            st.session_state.step = "ingredients"
            st.rerun()
        else:
            st.error("성함과 식별번호를 모두 입력해주세요.")

# ✅ 재료 선택 페이지
def show_ingredients():
    st.subheader("🐟 수산물 원재료 선택")
    st.info("최소 3개 이상, 최대 9개까지 선택 가능합니다.")

    # 🔥 Grid 레이아웃 적용
    st.markdown("<div class='grid'>", unsafe_allow_html=True)
    for ingredient in INGREDIENTS:
        jpg = os.path.join(INGREDIENT_IMAGE_PATH, f"{ingredient}.jpg")
        png = os.path.join(INGREDIENT_IMAGE_PATH, f"{ingredient}.png")
        img = load_image(jpg) or load_image(png)

        # 버튼 클릭 처리
        if st.button(f"✅ {ingredient}" if ingredient in st.session_state.selected_ingredients else ingredient,
                     key=f"btn_ing_{ingredient}"):
            if ingredient in st.session_state.selected_ingredients:
                st.session_state.selected_ingredients.remove(ingredient)
            else:
                if len(st.session_state.selected_ingredients) < 9:
                    st.session_state.selected_ingredients.append(ingredient)
            st.rerun()

        # 이미지 카드 렌더링
        render_image_button(ingredient, img, ingredient in st.session_state.selected_ingredients, f"ing_{ingredient}")
    st.markdown("</div>", unsafe_allow_html=True)

    # ✅ 다음 단계 버튼
    if 3 <= len(st.session_state.selected_ingredients) <= 9:
        if st.button("다음 단계로 →", type="primary"):
            st.session_state.selected_menus = {ing: [] for ing in st.session_state.selected_ingredients}
            st.session_state.step = "menus"
            st.rerun()
    else:
        st.button("다음 단계로 →", disabled=True)

# ✅ 메뉴 선택 페이지
def show_menus():
    st.subheader("🍽️ 선호 메뉴 선택")
    st.info("각 수산물마다 최소 1개 이상 메뉴를 선택해주세요.")

    for ing in st.session_state.selected_ingredients:
        st.markdown(f"### 🐟 {ing} 메뉴")
        menus = MENU_DATA.get(ing, [])
        for menu in menus:
            jpg = os.path.join(MENU_IMAGE_PATH, f"{menu}.jpg")
            png = os.path.join(MENU_IMAGE_PATH, f"{menu}.png")
            img = load_image(jpg) or load_image(png)

            if st.button(f"🍴 {menu}" if menu in st.session_state.selected_menus[ing] else menu,
                         key=f"btn_menu_{ing}_{menu}"):
                if menu in st.session_state.selected_menus[ing]:
                    st.session_state.selected_menus[ing].remove(menu)
                else:
                    st.session_state.selected_menus[ing].append(menu)
                st.rerun()
            render_image_button(menu, img, menu in st.session_state.selected_menus[ing], f"menu_{ing}_{menu}")

    # 완료 여부 확인
    all_valid = all(len(menus) > 0 for menus in st.session_state.selected_menus.values())

    # ✅ 버튼
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 이전 단계"):
            st.session_state.step = "ingredients"
            st.rerun()
    with col2:
        if all_valid:
            if st.button("설문 완료하기", type="primary"):
                st.session_state.step = "complete"
                st.rerun()
        else:
            st.button("설문 완료하기", disabled=True)

# ✅ 완료 페이지
def show_complete():
    st.balloons()
    st.success("🎉 설문이 완료되었습니다. 참여해주셔서 감사합니다!")

    if st.button("🔄 새 설문 시작하기"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ✅ 페이지 라우팅
if st.session_state.step == "info":
    show_info()
elif st.session_state.step == "ingredients":
    show_ingredients()
elif st.session_state.step == "menus":
    show_menus()
else:
    show_complete()
