from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from forcpa.dart.cache import ResultCache
from forcpa.dart.api_client import DartApiError, DartClient
from forcpa.dart.corp_codes import CompanyDirectory
from forcpa.dart.document_parser import DartDocumentParser
from forcpa.dart.filings import find_latest_annual_report
from forcpa.dart.models import Company, Filing, ResultStatus
from forcpa.dart.service import KamService
from forcpa.dart.viewer import DartViewer


FIXTURE = ROOT / "tests" / "fixtures" / "dart_kam" / "sample_connected_audit_report.xml"
PROSE_FIXTURE = ROOT / "tests" / "fixtures" / "dart_kam" / "sample_prose_audit_report.html"


def make_zip(name: str, content: bytes) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(name, content)
    return stream.getvalue()


class FakeClient:
    def __init__(self, document: bytes = b"") -> None:
        self.document = document
        self.download_count = 0

    def download_corp_codes(self) -> bytes:
        corp_xml = """<?xml version='1.0' encoding='UTF-8'?>
        <result>
          <list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><stock_code>005930</stock_code><modify_date>20260701</modify_date></list>
          <list><corp_code>00999999</corp_code><corp_name>삼성전자서비스</corp_name><stock_code>123456</stock_code><modify_date>20260701</modify_date></list>
          <list><corp_code>00888888</corp_code><corp_name>비상장회사</corp_name><stock_code> </stock_code><modify_date>20260701</modify_date></list>
        </result>""".encode("utf-8")
        return make_zip("CORPCODE.xml", corp_xml)

    def list_annual_reports(self, corp_code: str, begin_date: str, end_date: str):
        return [
            {
                "rcept_no": "20250311000123",
                "report_nm": "사업보고서 (2024.12)",
                "rcept_dt": "20250311",
            }
        ]

    def download_document(self, rcept_no: str) -> bytes:
        self.download_count += 1
        return self.document

    def get_filing_viewer(self, rcept_no: str, dcm_no: str = "") -> bytes:
        if not dcm_no:
            return b"""<html><body><select id='att'>
            <option value='rcpNo=20250311000123&amp;dcmNo=100'>2025.03.11 audit report</option>
            <option value='rcpNo=20250311000123&amp;dcmNo=200'>2025.03.11 connected audit report</option>
            </select></body></html>""".replace(b"audit report", "감사보고서".encode()).replace(
                b"connected ", "연결".encode()
            )
        return """<html><body><script>
        var node1 = {};
        node1['text'] = "독립된 감사인의 감사보고서";
        node1['id'] = "2";
        node1['rcpNo'] = "20250311000123";
        node1['dcmNo'] = "200";
        node1['eleId'] = "2";
        node1['offset'] = "100";
        node1['length'] = "5000";
        node1['dtd'] = "dart4.xsd";
        treeData.push(node1);
        </script></body></html>""".encode("utf-8")

    def get_report_viewer(self, params: dict[str, str]) -> bytes:
        self.download_count += 1
        return self.document


class ApiClientSecurityTests(unittest.TestCase):
    def test_network_error_does_not_expose_api_key(self) -> None:
        class FailingSession:
            headers: dict[str, str] = {}

            def get(self, *args, **kwargs):
                raise requests.ConnectionError("https://example.test?crtfc_key=top-secret")

        client = DartClient("top-secret", session=FailingSession(), max_retries=0)
        with self.assertRaises(DartApiError) as caught:
            client.list_annual_reports("00126380", "20250101", "20251231")

        self.assertNotIn("top-secret", str(caught.exception))
        self.assertIn("연결 실패", str(caught.exception))

    def test_http_error_reports_only_status_code(self) -> None:
        class ForbiddenSession:
            headers: dict[str, str] = {}

            def get(self, *args, **kwargs):
                response = requests.Response()
                response.status_code = 403
                response.url = "https://example.test?crtfc_key=top-secret"
                return response

        client = DartClient("top-secret", session=ForbiddenSession(), max_retries=0)
        with self.assertRaises(DartApiError) as caught:
            client.list_annual_reports("00126380", "20250101", "20251231")

        self.assertIn("HTTP 403", str(caught.exception))
        self.assertNotIn("top-secret", str(caught.exception))

    def test_proxy_receives_allowlisted_request_without_dart_api_key(self) -> None:
        class ProxySession:
            headers: dict[str, str] = {}
            captured: dict[str, object] = {}

            def post(self, url, **kwargs):
                self.captured = {"url": url, **kwargs}
                response = requests.Response()
                response.status_code = 200
                response._content = b'{"status":"000","list":[]}'
                response.headers["Content-Type"] = "application/json"
                return response

        session = ProxySession()
        client = DartClient(
            proxy_url="https://example.vercel.app/api/dart_proxy",
            proxy_token="proxy-secret",
            session=session,
            max_retries=0,
        )
        client.list_annual_reports("00126380", "20250101", "20251231")

        self.assertEqual(session.captured["url"], "https://example.vercel.app/api/dart_proxy")
        payload = session.captured["json"]
        assert isinstance(payload, dict)
        self.assertEqual(payload["target"], "opendart")
        self.assertEqual(payload["path"], "/api/list.json")
        self.assertNotIn("crtfc_key", payload["params"])
        self.assertEqual(
            session.captured["headers"],
            {"Authorization": "Bearer proxy-secret"},
        )

    def test_proxy_configuration_requires_url_and_token_together(self) -> None:
        with self.assertRaises(ValueError):
            DartClient(proxy_url="https://example.vercel.app/api/dart_proxy")


class ProxyAllowlistTests(unittest.TestCase):
    def test_injects_server_side_api_key_for_allowed_endpoint(self) -> None:
        from api.dart_proxy import prepare_upstream

        url, params = prepare_upstream(
            {
                "target": "opendart",
                "path": "/api/list.json",
                "params": {"corp_code": "00126380", "crtfc_key": "attacker-value"},
            },
            "server-side-key",
        )

        self.assertEqual(url, "https://opendart.fss.or.kr/api/list.json")
        self.assertEqual(params["crtfc_key"], "server-side-key")

    def test_rejects_arbitrary_proxy_destination(self) -> None:
        from api.dart_proxy import prepare_upstream

        with self.assertRaises(ValueError):
            prepare_upstream(
                {"target": "external", "path": "https://example.com", "params": {}},
                "server-side-key",
            )


class CompanyDirectoryTests(unittest.TestCase):
    def test_searches_listed_companies_and_preserves_leading_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = CompanyDirectory(FakeClient(), Path(temporary) / "corp_codes.xml")
            by_code = directory.search("005930")
            by_name = directory.search("삼성전자")

        self.assertEqual([company.corp_name for company in by_code], ["삼성전자"])
        self.assertEqual([company.corp_name for company in by_name], ["삼성전자", "삼성전자서비스"])
        self.assertTrue(all(company.stock_code for company in by_name))


class FilingSelectionTests(unittest.TestCase):
    def test_prefers_newer_report_period_over_later_receipt(self) -> None:
        class FilingClient(FakeClient):
            def list_annual_reports(self, corp_code: str, begin_date: str, end_date: str):
                return [
                    {
                        "rcept_no": "20260515000003",
                        "report_nm": "분기보고서 (2026.03)",
                        "rcept_dt": "20260515",
                    },
                    {
                        "rcept_no": "20250401000002",
                        "report_nm": "[기재정정]사업보고서 (2023.12)",
                        "rcept_dt": "20250401",
                    },
                    {
                        "rcept_no": "20250311000001",
                        "report_nm": "사업보고서 (2024.12)",
                        "rcept_dt": "20250311",
                    },
                ]

        company = Company("00126380", "삼성전자", "005930")
        filing = find_latest_annual_report(FilingClient(), company, today=date(2026, 7, 20))

        self.assertIsNotNone(filing)
        assert filing is not None
        self.assertEqual(filing.rcept_no, "20250311000001")
        self.assertEqual(filing.report_period_end, "2024-12-31")


class DocumentParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = Company("00123456", "ABC회사", "123456")
        self.filing = Filing(
            rcept_no="20250311000123",
            report_name="사업보고서 (2024.12)",
            report_period_end="2024-12-31",
            rcept_date="2025-03-11",
            is_amended=False,
            source_url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250311000123",
        )

    def test_extracts_auditor_scope_and_two_kam_items(self) -> None:
        archive = make_zip("report.xml", FIXTURE.read_bytes())
        result = DartDocumentParser().parse(archive, self.company, self.filing)

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.report_scope, "consolidated")
        self.assertEqual(result.auditor_name, "삼일회계법인")
        self.assertEqual([item.kam_title for item in result.kam_items], ["재고자산 평가", "수익 인식"])
        self.assertIn("중요한 판단", result.kam_items[0].why_kam)
        self.assertIn("내부통제를 테스트", result.kam_items[0].audit_response)
        self.assertNotIn("경영진과 지배기구의 책임", result.kam_items[1].audit_response)
        self.assertNotIn("삼일회계법인", result.kam_items[1].audit_response)
        self.assertEqual(len(result.to_rows()), 2)

    def test_distinguishes_missing_kam_from_parse_failure(self) -> None:
        markup = """<html><body>
        <h1>재무제표에 대한 독립된 감사인의 감사보고서</h1>
        <p>감사의견</p><p>한영회계법인</p>
        </body></html>""".encode()
        result = DartDocumentParser().parse(make_zip("report.xml", markup), self.company, self.filing)
        self.assertEqual(result.status, ResultStatus.KAM_NOT_PRESENT)

    def test_extracts_prose_style_kam_and_spaced_auditor_name(self) -> None:
        result = DartDocumentParser().parse_audit_report_html(
            PROSE_FIXTURE.read_bytes(),
            self.company,
            self.filing,
            report_scope="consolidated",
            source_locator="연결감사보고서 / 독립된 감사인의 감사보고서",
            source_url=self.filing.source_url + "&dcmNo=200",
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.auditor_name, "한영회계법인")
        self.assertEqual(len(result.kam_items), 1)
        self.assertEqual(result.kam_items[0].kam_title, "판매보증충당부채 인식의 완전성 및 측정의 정확성")
        self.assertIn("중요한 판단", result.kam_items[0].why_kam)
        self.assertIn("내부통제", result.kam_items[0].audit_response)


class ViewerSelectionTests(unittest.TestCase):
    def test_selects_connected_attachment_and_audit_section(self) -> None:
        client = FakeClient(PROSE_FIXTURE.read_bytes())
        source = DartViewer(client).load_audit_report("20250311000123")

        self.assertEqual(source.dcm_no, "200")
        self.assertEqual(source.report_scope, "consolidated")
        self.assertIn("dcmNo=200", source.source_url)
        self.assertIn("eleId=2", source.source_locator)


class CacheAndServiceTests(unittest.TestCase):
    def test_second_lookup_reuses_receipt_number_cache(self) -> None:
        client = FakeClient(FIXTURE.read_bytes())
        company = Company("00123456", "ABC회사", "123456")

        class FixedDirectory:
            def search(self, query: str, force_refresh: bool = False):
                return [company]

        with tempfile.TemporaryDirectory() as temporary:
            service = KamService(
                client=client,
                company_directory=FixedDirectory(),
                cache=ResultCache(Path(temporary)),
                parser=DartDocumentParser(),
            )
            first = service.get_latest_kam(company)
            second = service.get_latest_kam(company)

        self.assertEqual(first.status, ResultStatus.SUCCESS)
        self.assertFalse(first.from_cache)
        self.assertTrue(second.from_cache)
        self.assertEqual(client.download_count, 1)
        self.assertEqual(first.to_dict(), second.to_dict())


if __name__ == "__main__":
    unittest.main()
