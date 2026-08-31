import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
import time

# 페이지 기본 설정
st.set_page_config(page_title="팀 예산 관리 대시보드", page_icon="📊", layout="wide")

# 사이드바: Google Apps Script Web App URL 설정
st.sidebar.title("시스템 설정")
st.sidebar.write("최초 1회 Apps Script 웹앱 URL을 입력해주세요.")
# 사용자가 직접 URL을 입력하거나, 배포 시 환경 변수/Secrets로 관리할 수 있습니다.
GAS_URL = st.sidebar.text_input("Google Apps Script URL", placeholder="https://script.google.com/macros/s/.../exec")
st.sidebar.markdown("---")
st.sidebar.caption("데이터는 Google 스프레드시트와 실시간 연동됩니다. (인증 불필요)")
st.sidebar.info("Github 배포 시, 이 앱은 Apps Script URL을 통해 직접 DB와 통신합니다.")

@st.cache_data(ttl=3) # 3초 캐싱: 너무 잦은 API 호출은 방지하되, 빠른 업데이트 반영
def load_data(url):
    """Apps Script를 통해 스프레드시트에서 데이터를 읽어옵니다."""
    if not url: return pd.DataFrame()
    try:
        response = requests.get(f"{url}?action=read", timeout=10)
        
        # 응답이 비어있거나 에러 메시지가 있는지 확인
        if response.text == "" or "error" in response.text.lower():
             return pd.DataFrame()

        data = response.json()
        
        # 데이터가 리스트 형태가 아니면 빈 데이터프레임 반환
        if not isinstance(data, list):
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if not df.empty:
            # 숫자형 데이터 변환 보장
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['id'] = pd.to_numeric(df['id'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패. URL을 확인해주세요. 상세 에러: {e}")
        return pd.DataFrame()

def add_data(url, entry):
    """Apps Script를 통해 스프레드시트에 새 데이터를 추가합니다."""
    try:
        # POST 요청으로 데이터 전송 (CORS 이슈 회피 및 대용량 데이터 안정성)
        payload = {'action': 'create', 'data': json.dumps(entry)}
        response = requests.post(url, data=payload, timeout=10)
        return response.json().get('status') == 'success'
    except Exception as e:
        st.error(f"저장 중 오류 발생: {e}")
        return False

def delete_data(url, target_id):
    """Apps Script를 통해 특정 ID의 데이터를 삭제합니다."""
    try:
        response = requests.get(f"{url}?action=delete&id={target_id}", timeout=10)
        return response.json().get('status') == 'success'
    except Exception as e:
        st.error(f"삭제 중 오류 발생: {e}")
        return False

st.title("📊 팀 예산 관리 시스템")
st.write("부장님 보고용 월별 예산 취합 및 대시보드 (Streamlit & Apps Script 연동)")

if not GAS_URL:
    st.warning("👈 왼쪽 사이드바에서 Google Apps Script 배포 URL(웹앱 URL)을 입력해야 서비스가 작동합니다.")
    st.stop() # URL이 없으면 여기서 앱 실행을 멈춤

# 탭 구성
tab1, tab2 = st.tabs(["데이터 입력 및 관리", "전체 요약 대시보드"])

# --- 탭 1: 데이터 입력 ---
with tab1:
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.subheader("📝 내역 추가")
        # clear_on_submit=True로 제출 후 폼 초기화
        with st.form("budget_form", clear_on_submit=True):
            member = st.selectbox("팀원 선택", ["부장님", "팀원1", "팀원2", "팀원3", "팀원4"])
            month = st.date_input("해당 월").strftime("%Y-%m")
            category = st.selectbox("예산 항목", ["수선유지비", "비품", "개량공사", "기타"])
            amount = st.number_input("사용 금액 (원)", min_value=0, step=1000)
            
            submitted = st.form_submit_button("스프레드시트에 기록 저장", use_container_width=True)
            
            if submitted:
                if amount <= 0:
                    st.error("금액은 0원보다 커야 합니다.")
                else:
                    # 고유 ID 생성 (밀리초 단위 타임스탬프)
                    entry = {
                        "id": int(time.time() * 1000),
                        "member": member,
                        "month": month,
                        "category": category,
                        "amount": amount
                    }
                    with st.spinner("스프레드시트에 저장 중..."):
                        if add_data(GAS_URL, entry):
                            st.success("성공적으로 저장되었습니다!")
                            st.cache_data.clear() # 캐시를 비워 다음 로드 시 즉시 반영되게 함
                            time.sleep(1) # 사용자가 메시지를 볼 수 있도록 잠시 대기
                            st.rerun() # 앱 새로고침

    with col2:
        st.subheader("📂 최근 기록")
        df = load_data(GAS_URL)
        
        if not df.empty:
            # 삭제 폼
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                del_id = st.text_input("삭제할 행의 ID를 복사하여 붙여넣으세요.")
            with del_col2:
                st.write("") # 마진 맞추기용 빈 줄
                st.write("")
                if st.button("행 삭제", use_container_width=True, type="primary"):
                    if del_id.strip().isdigit(): # 입력값이 숫자인지 확인
                        with st.spinner("삭제 중..."):
                            if delete_data(GAS_URL, del_id.strip()):
                                st.success("삭제되었습니다.")
                                st.cache_data.clear() # 삭제 후 캐시 클리어
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("해당 ID를 찾을 수 없거나 삭제에 실패했습니다.")
                    else:
                        st.warning("유효한 숫자 ID를 입력해주세요.")
            
            # 최신 데이터가 위로 오도록 정렬하여 출력
            st.dataframe(
                df[['id', 'month', 'member', 'category', 'amount']].sort_values(by='id', ascending=False),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn(
                        "금액 (원)",
                        format="%d"
                    ),
                    "id": st.column_config.NumberColumn(
                        "ID (삭제용)",
                        format="%d"
                    )
                }
            )
        else:
            st.info("현재 등록된 예산 데이터가 없습니다. 좌측 폼을 이용해 추가해보세요.")

# --- 탭 2: 대시보드 ---
with tab2:
    df = load_data(GAS_URL)
    
    if df.empty:
        st.warning("분석할 데이터가 없습니다. [데이터 입력 및 관리] 탭에서 내역을 먼저 입력해주세요.")
    else:
        total_amount = df['amount'].sum()
        
        # 카테고리별 합계 중 최대값 항목 찾기
        cat_sum = df.groupby('category')['amount'].sum()
        top_cat = cat_sum.idxmax() if not cat_sum.empty else "없음"
        top_cat_amount = cat_sum.max() if not cat_sum.empty else 0
        
        # 핵심 지표 표시
        m1, m2, m3 = st.columns(3)
        m1.metric("전체 누적 사용액", f"{total_amount:,.0f} 원")
        m2.metric("최다 지출 항목", f"{top_cat}", f"{top_cat_amount:,.0f} 원 지출", delta_color="off")
        m3.metric("누적 데이터 수", f"{len(df)} 건")
        st.divider()
        
        # 차트 표시 영역
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏠 항목별 예산 분포")
            fig_pie = px.pie(
                df, 
                values='amount', 
                names='category', 
                hole=0.4, 
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.subheader("👥 팀원별 누적 사용액")
            member_sum = df.groupby('member', as_index=False)['amount'].sum().sort_values(by='amount', ascending=False)
            fig_bar = px.bar(
                member_sum, 
                x='member', 
                y='amount', 
                color='member', 
                text_auto='.2s', # 숫자 단위 포맷팅
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_bar.update_layout(showlegend=False, xaxis_title="팀원", yaxis_title="누적 사용액 (원)")
            st.plotly_chart(fig_bar, use_container_width=True)
            
        # 월별/항목별 요약 피벗 테이블
        st.subheader("📅 월별/항목별 요약 테이블")
        try:
            pivot_df = df.pivot_table(index='month', columns='category', values='amount', aggfunc='sum', fill_value=0)
            pivot_df['총계 (월)'] = pivot_df.sum(axis=1)
            
            # 인덱스(월) 기준 내림차순 정렬 (최신 월이 위로 오게)
            pivot_df = pivot_df.sort_index(ascending=False)
            
            st.dataframe(
                pivot_df.style.format("{:,.0f}"), 
                use_container_width=True
            )
        except Exception as e:
            st.error(f"테이블 생성 중 오류가 발생했습니다: {e}")
