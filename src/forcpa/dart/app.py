"""DART 핵심감사사항(KAM) 조회 Streamlit 앱."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from dotenv import load_dotenv
except ImportError:  # requirements 설치 전에도 설정 오류 화면은 표시한다.
    def load_dotenv(dotenv_path: object, *_args: object, **_kwargs: object) -> bool:
        path = Path(dotenv_path)
        if not path.exists():
            return False
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)
        return True


from forcpa.dart.api_client import DartApiError, DartClient
from forcpa.dart.cache import ResultCache
from forcpa.dart.corp_codes import CompanyDirectory
from forcpa.dart.document_parser import DartDocumentParser
from forcpa.dart.models import KamResult, ResultStatus
from forcpa.dart.service import KamService


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_ROOT = PROJECT_ROOT / "data" / "cache" / "dart"


@st.cache_resource(show_spinner=False)
def build_service(api_key: str, proxy_url: str = "", proxy_token: str = "") -> KamService:
    client = DartClient(api_key, proxy_url=proxy_url, proxy_token=proxy_token)
    return KamService(
        client=client,
        company_directory=CompanyDirectory(client, CACHE_ROOT / "corp_codes.xml"),
        cache=ResultCache(CACHE_ROOT / "results"),
        parser=DartDocumentParser(),
    )


def _api_error_message(error: DartApiError) -> str:
    actions = {
        "010": "DART_API_KEY가 올바른지 확인해 주세요.",
        "011": "현재 사용할 수 없는 인증키입니다. OpenDART에서 키 상태를 확인해 주세요.",
        "013": "조건에 맞는 공시가 없습니다.",
        "020": "OpenDART 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
        "network_error": f"{error.message}. 잠시 후 다시 시도해 주세요.",
    }
    return actions.get(error.code, f"OpenDART 요청에 실패했습니다. 오류 코드: {error.code}")


def _render_result(result: KamResult) -> None:
    if result.status == ResultStatus.SUCCESS:
        st.success(f"핵심감사사항 {len(result.kam_items)}건을 찾았습니다.")
    elif result.status == ResultStatus.KAM_NOT_PRESENT:
        st.info("감사보고서는 확인했지만 핵심감사사항 섹션을 찾지 못했습니다.")
    elif result.status == ResultStatus.MANUAL_REVIEW_REQUIRED:
        st.warning("원문은 찾았지만 일부 구조를 확정하지 못했습니다. DART 원문과 대조해 주세요.")
    else:
        st.error("자동 조회를 완료하지 못했습니다. 아래 안내와 DART 원문을 확인해 주세요.")

    if result.from_cache:
        st.caption("저장된 결과를 사용했습니다. 최신 DART 접수번호는 다시 확인했습니다.")
    elif result.rcept_no:
        st.caption("DART 원문을 새로 처리하고 결과를 로컬 JSON 캐시에 저장했습니다.")

    left, middle, right = st.columns(3)
    left.metric("기업", result.corp_name or "-")
    middle.metric("보고기간", result.report_period_end or "확인 필요")
    right.metric("감사인", result.auditor_name or "확인 필요")

    details = [
        f"종목코드: `{result.stock_code or '-'}`",
        f"접수번호: `{result.rcept_no or '-'}`",
        f"감사보고서: `{'연결' if result.report_scope == 'consolidated' else '별도' if result.report_scope == 'separate' else '확인 필요'}`",
        f"정정공시: `{'예' if result.is_amended else '아니요'}`",
        f"추출 신뢰도: `{result.confidence}`",
    ]
    st.markdown(" · ".join(details))

    if result.source_url:
        st.link_button("선택된 DART 감사보고서 열기", result.source_url)
    for warning in result.warnings:
        st.warning(warning)

    if result.kam_items:
        st.subheader("핵심감사사항")
        for item in result.kam_items:
            with st.expander(f"{item.kam_no}. {item.kam_title}", expanded=item.kam_no == 1):
                if item.why_kam:
                    st.markdown("#### 핵심감사사항으로 선정한 이유")
                    st.text(item.why_kam)
                if item.audit_response:
                    st.markdown("#### 감사인의 대응")
                    st.text(item.audit_response)
                with st.expander("추출된 전체 원문"):
                    st.text(item.raw_text)
                if item.source_locator:
                    st.caption(f"원문 위치: {item.source_locator}")

        with st.expander("KAM_RESULT 테이블 보기"):
            st.dataframe(result.to_rows(), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="DART KAM 조회", page_icon="🔎", layout="wide")
    load_dotenv(PROJECT_ROOT / ".env")

    st.title("DART 핵심감사사항 조회")
    st.caption("최신 사업보고서의 감사인과 핵심감사사항 원문을 확인합니다.")

    api_key = os.getenv("DART_API_KEY", "").strip()
    proxy_url = os.getenv("DART_PROXY_URL", "").strip()
    proxy_token = os.getenv("DART_PROXY_TOKEN", "").strip()
    proxy_configured = bool(proxy_url and proxy_token)
    if bool(proxy_url) != bool(proxy_token):
        st.error("DART_PROXY_URL과 DART_PROXY_TOKEN을 함께 설정해 주세요.")
        st.stop()
    if not api_key and not proxy_configured:
        st.error("DART_API_KEY 또는 DART 중계 서버가 설정되지 않았습니다.")
        st.code(
            "# 로컬 직접 연결\nDART_API_KEY=발급받은_인증키\n\n"
            "# Streamlit Cloud 중계 연결\n"
            "DART_PROXY_URL=https://내프로젝트.vercel.app/api/dart_proxy\n"
            "DART_PROXY_TOKEN=임의의_긴_비밀문자열"
        )
        st.stop()

    service = build_service(api_key, proxy_url, proxy_token)
    query = st.text_input(
        "기업명 또는 종목코드",
        placeholder="예: 삼성전자 또는 005930",
        help="MVP에서는 종목코드가 있는 상장기업을 조회합니다.",
    )

    search_col, refresh_col = st.columns([3, 1])
    with search_col:
        search_clicked = st.button("기업 찾기", type="primary", use_container_width=True)
    with refresh_col:
        refresh_company_list = st.checkbox("기업목록 새로 받기")

    if search_clicked:
        st.session_state.pop("kam_result", None)
        st.session_state["company_candidates"] = []
        if not query.strip():
            st.warning("기업명 또는 종목코드를 입력해 주세요.")
        else:
            try:
                with st.spinner("상장기업 목록을 확인하고 있습니다..."):
                    st.session_state["company_candidates"] = service.search_companies(
                        query,
                        force_refresh=refresh_company_list,
                    )
            except DartApiError as error:
                st.error(_api_error_message(error))
            except (OSError, ValueError) as error:
                st.error(f"기업목록을 처리하지 못했습니다: {error}")

    candidates = st.session_state.get("company_candidates", [])
    if search_clicked and not candidates:
        st.info("해당 상장기업을 찾지 못했습니다.")

    if candidates:
        selected = st.selectbox(
            "조회할 기업",
            candidates,
            format_func=lambda company: f"{company.corp_name} ({company.stock_code})",
        )
        force_reparse = st.checkbox("저장된 결과를 무시하고 원문 다시 처리")
        if st.button("최신 KAM 조회", type="primary"):
            try:
                with st.spinner("최신 공시 확인 및 핵심감사사항 추출 중..."):
                    st.session_state["kam_result"] = service.get_latest_kam(
                        selected,
                        force_reparse=force_reparse,
                    )
            except DartApiError as error:
                st.error(_api_error_message(error))

    result = st.session_state.get("kam_result")
    if result is not None:
        st.divider()
        _render_result(result)


if __name__ == "__main__":
    main()
