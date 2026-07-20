"""최신 유효 사업보고서 선택 규칙."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime

from .api_client import DartClient
from .models import Company, Filing


def parse_report_period(report_name: str) -> str:
    match = re.search(r"\((\d{4})[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?\)", report_name)
    if not match:
        return ""
    year, month = int(match.group(1)), int(match.group(2))
    day = int(match.group(3)) if match.group(3) else calendar.monthrange(year, month)[1]
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return ""


def _parse_receipt_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except (TypeError, ValueError):
        return ""


def _to_filing(row: dict[str, object]) -> Filing:
    rcept_no = str(row.get("rcept_no", "")).strip()
    report_name = str(row.get("report_nm", "")).strip()
    return Filing(
        rcept_no=rcept_no,
        report_name=report_name,
        report_period_end=parse_report_period(report_name),
        rcept_date=_parse_receipt_date(str(row.get("rcept_dt", ""))),
        is_amended="정정" in report_name,
        source_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}",
    )


def _is_annual_report(row: dict[str, object]) -> bool:
    report_name = re.sub(r"\s+", "", str(row.get("report_nm", "")))
    return "사업보고서" in report_name and "분기보고서" not in report_name and "반기보고서" not in report_name


def find_latest_annual_report(client: DartClient, company: Company, *, today: date | None = None) -> Filing | None:
    current = today or date.today()
    rows = client.list_annual_reports(company.corp_code, f"{current.year - 3}0101", current.strftime("%Y%m%d"))
    if not rows:
        rows = client.list_annual_reports(company.corp_code, f"{current.year - 10}0101", current.strftime("%Y%m%d"))
    filings = [
        _to_filing(row)
        for row in rows
        if str(row.get("rcept_no", "")).strip() and _is_annual_report(row)
    ]
    if not filings:
        return None
    return max(filings, key=lambda item: (item.report_period_end or item.rcept_date, item.rcept_date, item.rcept_no))
