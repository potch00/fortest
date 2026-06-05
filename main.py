import streamlit as st
import json
from datetime import datetime
from PIL import Image
from openai import OpenAI
import base64

# 1. 세션 상태 초기화 (st.session_state.item 단수형 사용)
if "item" not in st.session_state or st.session_state.item is None:
    st.session_state.item = []

# AI가 추출한 최종 임시 결과를 보관할 세션
if "temp_extracted" not in st.session_state:
    st.session_state.temp_extracted = None

# 2. 사이드바에 API 키 입력창 추가
st.sidebar.title("🔐 설정 (Settings)")
user_openai_api_key = st.sidebar.text_input(
    "OpenAI API Key를 입력하세요", 
    type="password",
    help="OpenAI 홈페이지에서 발급받은 api 키(sk-...)를 입력해야 기능이 작동합니다."
)

# 3. 주요 함수 설계 (OCR 단계와 추론 단계를 분리)

def run_ocr_step(image_file, client):
    """
    [1단계: OCR] 영수증 이미지에서 눈에 보이는 텍스트를 왜곡 없이 그대로 추출합니다.
    """
    image_file.seek(0)
    bytes_data = image_file.read()
    base64_image = base64.b64encode(bytes_data).decode('utf-8')
    file_type = image_file.type if hasattr(image_file, 'type') else "image/jpeg"
    
    ocr_prompt = """
    당신은 아주 정밀한 OCR(광학 문자 인식) 시스템입니다.
    제공된 영수증 이미지에 포함된 모든 텍스트를 위에서부터 아래로, 보이는 그대로 받아적어 주세요.
    단어를 임의로 수정하거나, 요약하거나, 추론하지 말고 오직 눈에 보이는 글자만 텍스트로 반환해야 합니다.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ocr_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{file_type};base64,{base64_image}"}
                    }
                ]
            }
        ],
        max_tokens=1500
    )
    return response.choices[0].message.content


def run_inference_step(raw_text, client):
    """
    [2단계: 추론 및 정제] 1단계에서 얻은 텍스트를 가공하여 품목명을 추론하고 JSON 형태로 바꿉니다.
    """
    inference_prompt = f"""
    당신은 영수증 텍스트 데이터에서 구매일과 식재료를 정밀하게 정제하는 NLP(자연어 처리) 전문가입니다.
    아래의 [영수증 텍스트]를 분석하여 다음 규칙에 따라 정확한 JSON 데이터를 생성하세요.

    [영수증 텍스트]:
    {raw_text}

    **품목명 추론 및 정제 규칙**:
    1. 텍스트 중에서 '결제일', '승인일자', '거래일시' 등 구매 날짜를 찾아 'YYYY-MM-DD' 형식으로 추출하세요.
    2. 구매 품목 중 공산품이나 비식품(예: 봉투, 세제 등)을 제외한 '식재료'에 해당하는 품목명 리스트를 추출하세요.
    3. 영수증 특성상 글자가 잘리거나 축약된 경우(예: '친환경대파(특' -> '대파', '깐마늘500g' -> '마늘', '백오이(3입)' -> '오이')가 많습니다. 문맥을 보고 사람이 이해할 수 있는 온전한 '식재료명'으로 합리적으로 추론하여 정제된 단어로 작성해 주세요.
    4. 양념류, 가공식품이라도 식재료에 해당하면 포함하되, 규격이나 수량(g, 입, 개 등)은 제외하고 순수 재료명 위주로 추출하세요.
    5. 이름, 카드번호, 주소, 전화번호 등의 '개인 정보'는 절대 포함하지 마십시오.

    **반환 형식**:
    반드시 아래의 JSON 포맷을 엄격히 따라야 하며, 마크다운(```json 등)을 제외한 순수 JSON 문자열만 반환하세요.
    {{
        "purchase_date": "YYYY-MM-DD",
        "items": ["재료명1", "재료명2", ...]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": inference_prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


def extract_items_from_receipt(image_file, api_key):
    """
    Tech Spec 규격을 맞추기 위해 메인에서 호출하는 마스터 함수입니다.
    내부적으로 1단계(OCR)와 2단계(추론)를 순서대로 실행합니다.
    """
    client = OpenAI(api_key=api_key)
    
    # 1단계: 텍스트 날것 그대로 긁어오기 (OCR)
    with st.spinner("1단계: 영수증에서 글자를 읽어오는 중 (OCR)..."):
        raw_text = run_ocr_step(image_file, client)
        
    # 2단계: 긁어온 텍스트를 바탕으로 식재료 추론하기 (Inference)
    with st.spinner("2단계: 축약된 상품명을 온전한 재료명으로 추론하는 중..."):
        result_json = run_inference_step(raw_text, client)
        
    return result_json


def add_items(final_date, final_items_list):
    """
    사용자가 최종 수정한 데이터를 데이터 모델 형식에 맞추어 st.session_state.item에 저장합니다.
    """
    if "item" not in st.session_state or not isinstance(st.session_state.item, list):
        st.session_state.item = []
        
    for name in final_items_list:
        if name.strip():
            item_model = {
                "name": name.strip(),
                "purchase_date": final_date,
            }
            st.session_state.item.append(item_model)


# 4. UI 컴포넌트 구성
st.title("Keep And Cook 🍳")
st.subheader("영수증 재료 등록")

uploaded_file = st.file_uploader("영수증 이미지를 첨부해주세요.", type=["jpg", "png"])

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='업로드된 영수증', use_column_width=True)
    
    if st.button("영수증에서 재료 추출하기"):
        if not user_openai_api_key:
            st.warning("왼쪽 사이드바에 OpenAI API Key를 먼저 입력해주세요!")
        else:
            # 1단계 & 2단계가 차례대로 실행됨
            extracted_data = extract_items_from_receipt(uploaded_file, user_openai_api_key)
            if extracted_data:
                st.session_state.temp_extracted = extracted_data
                st.rerun()

# 사용자가 직접 수정할 수 있는 UI 영역
if st.session_state.temp_extracted is not None:
    st.markdown("---")
    st.markdown("### ✏️ AI 추출 결과 확인 및 수정")
    st.info("틀린 부분이 있다면 직접 수정하신 후 하단의 [최종 냉장고에 저장] 버튼을 눌러주세요.")
    
    # 1. 구매일 수정 입력창
    temp_date = st.session_state.temp_extracted.get("purchase_date", datetime.today().strftime('%Y-%m-%d'))
    edited_date = st.text_input("🗓️ 구매일 (YYYY-MM-DD)", value=temp_date)
    
    # 2. 재료 목록 수정 입력창
    temp_items = st.session_state.temp_extracted.get("items", [])
    temp_items_str = ", ".join(temp_items)
    edited_items_str = st.text_area("🛒 추출된 재료 (쉼표로 구분하여 수정 가능)", value=temp_items_str)
    
    # 3. 최종 저장 버튼
    if st.button("💾 최종 냉장고에 저장"):
        edited_items_list = [item.strip() for item in edited_items_str.split(",") if item.strip()]
        add_items(edited_date, edited_items_list)
        st.toast("선택하신 재료가 성공적으로 냉장고 저장소에 저장되었습니다!")
        st.session_state.temp_extracted = None
        st.rerun()

# 5. 저장 데이터 확인 (디버깅용)
st.markdown("---")
st.subheader("📦 현재 냉장고 저장소 상태 (st.session_state.item)")
if st.session_state.item:
    st.json(st.session_state.item)
else:
    st.info("아직 저장된 재료가 없습니다. 영수증을 업로드하여 재료를 추가해보세요.")
