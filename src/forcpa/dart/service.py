"""기업 검색부터 캐시·문서 파싱까지 연결하는 서비스."""

from __future__ import annotations

from datetime import datetime

from .api_client import DartApiError, DartClient
from .cache import ResultCache
from .corp_codes import CompanyDirectory
from .document_parser import DartDocumentParser
from .filings import find_latest_annual_report
from .models import Company, KamResult, ResultStatus
from .viewer import AuditAttachmentNotFound, DartViewer


class KamService:
    def __init__(
        self,
        client: DartClient,
        company_directory: CompanyDirectory,
        cache: ResultCache,
        parser: DartDocumentParser,
        viewer: DartViewer | None = None,
    ) -> None:
        self.client = client
        self.company_directory = company_directory
        self.cache = cache
        self.parser = parser
        self.viewer = viewer or DartViewer(client)

    def search_companies(self, query: str, *, force_refresh: bool = False) -> list[Company]:
        return self.company_directory.search(query, force_refresh=force_refresh)

    @staticmethod
    def _empty_result(company: Company, status: ResultStatus, warning: str) -> KamResult:
        return KamResult(
            corp_code=company.corp_code,
            stock_code=company.stock_code,
            corp_name=company.corp_name,
            rcept_no="",
            report_name="",
            report_period_end="",
            rcept_date="",
            is_amended=False,
            report_scope="",
            auditor_name="",
            status=status,
            confidence="low",
            source_url="",
            source_locator="",
            parser_version="",
            extracted_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            warnings=[warning],
        )

    def get_latest_kam(self, company: Company, *, force_reparse: bool = False) -> KamResult:
        filing = find_latest_annual_report(self.client, company)
        if filing is None:
            return self._empty_result(
                company,
                ResultStatus.ANNUAL_REPORT_NOT_FOUND,
                "최신 사업보고서를 찾지 못했습니다.",
            )
        if not force_reparse:
            cached = self.cache.load(filing.rcept_no, parser_version=self.parser.parser_version)
            if cached is not None:
                return cached
        try:
            source = self.viewer.load_audit_report(filing.rcept_no)
            result = self.parser.parse_audit_report_html(
                source.html,
                company,
                filing,
                report_scope=source.report_scope,
                source_locator=source.source_locator,
                source_url=source.source_url,
            )
        except DartApiError:
            raise
        except AuditAttachmentNotFound as exc:
            result = KamResult(
                corp_code=company.corp_code,
                stock_code=company.stock_code,
                corp_name=company.corp_name,
                rcept_no=filing.rcept_no,
                report_name=filing.report_name,
                report_period_end=filing.report_period_end,
                rcept_date=filing.rcept_date,
                is_amended=filing.is_amended,
                report_scope="",
                auditor_name="",
                status=ResultStatus.AUDIT_REPORT_NOT_IDENTIFIED,
                confidence="low",
                source_url=filing.source_url,
                source_locator="",
                parser_version=self.parser.parser_version,
                extracted_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                warnings=[str(exc)],
            )
        except (OSError, ValueError) as exc:
            result = KamResult(
                corp_code=company.corp_code,
                stock_code=company.stock_code,
                corp_name=company.corp_name,
                rcept_no=filing.rcept_no,
                report_name=filing.report_name,
                report_period_end=filing.report_period_end,
                rcept_date=filing.rcept_date,
                is_amended=filing.is_amended,
                report_scope="",
                auditor_name="",
                status=ResultStatus.PARSE_FAILED,
                confidence="low",
                source_url=filing.source_url,
                source_locator="",
                parser_version=self.parser.parser_version,
                extracted_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                warnings=[str(exc)],
            )
        self.cache.save(result)
        return result
