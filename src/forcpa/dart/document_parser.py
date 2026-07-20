"""DART 원본 ZIP에서 감사보고서와 KAM 원문을 찾는 결정론적 파서."""

from __future__ import annotations

import html as html_stdlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from lxml import html as lxml_html

from .models import Company, Filing, KamItem, KamResult, ResultStatus


PARSER_VERSION = "1.1.0"
MAX_MEMBER_SIZE = 50 * 1024 * 1024
MAX_TOTAL_SIZE = 150 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class TextDocument:
    name: str
    media_type: str
    text: str


@dataclass(frozen=True, slots=True)
class AuditCandidate:
    document: TextDocument
    text: str
    report_scope: str
    score: int
    locator: str


def _normalize_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        clean = re.sub(r"[ \t\u00a0]+", " ", line).strip()
        if clean and (not lines or clean != lines[-1]):
            lines.append(clean)
    return "\n".join(lines)


def _decode(data: bytes) -> str:
    declared = re.search(br"encoding=[\"']([A-Za-z0-9._-]+)", data[:500], re.IGNORECASE)
    encodings = [declared.group(1).decode("ascii", "ignore")] if declared else []
    encodings.extend(["utf-8-sig", "cp949", "euc-kr"])
    for encoding in dict.fromkeys(encodings):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def _markup_to_text(markup: str) -> str:
    prepared = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    prepared = re.sub(r"(?i)</(?:p|div|tr|table|h[1-6]|section|li)\s*>", "\n", prepared)
    prepared = re.sub(r"(?i)</(?:td|th)\s*>", "\t", prepared)
    try:
        root = lxml_html.fromstring(prepared)
        for bad in root.xpath("//script|//style|//noscript"):
            bad.drop_tree()
        text = root.text_content()
    except (ValueError, TypeError):
        text = re.sub(r"<[^>]+>", " ", prepared)
    return _normalize_lines(html_stdlib.unescape(text))


class DartDocumentParser:
    def __init__(self, *, parser_version: str = PARSER_VERSION) -> None:
        self.parser_version = parser_version

    @staticmethod
    def _read_documents(archive: bytes) -> list[TextDocument]:
        if not archive.startswith(b"PK"):
            raise ValueError("공시서류 원본 응답이 ZIP 파일이 아닙니다.")
        documents: list[TextDocument] = []
        total_size = 0
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for info in bundle.infolist():
                path = PurePosixPath(info.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    continue
                suffix = path.suffix.casefold()
                if suffix not in {".xml", ".html", ".htm", ".txt"}:
                    continue
                if info.file_size > MAX_MEMBER_SIZE:
                    raise ValueError("원본 문서 한 개가 허용 크기를 초과했습니다.")
                total_size += info.file_size
                if total_size > MAX_TOTAL_SIZE:
                    raise ValueError("압축 해제할 원본 문서의 전체 크기가 허용치를 초과했습니다.")
                markup = _decode(bundle.read(info))
                documents.append(
                    TextDocument(
                        name=info.filename,
                        media_type="text/html" if suffix in {".html", ".htm"} else "application/xml",
                        text=_markup_to_text(markup),
                    )
                )
        if not documents:
            raise ValueError("ZIP 안에서 읽을 수 있는 XML/HTML 문서를 찾지 못했습니다.")
        return documents

    @staticmethod
    def _audit_candidates(documents: list[TextDocument]) -> list[AuditCandidate]:
        header_pattern = re.compile(r"독립된\s*감사인의\s*감사보고서")
        candidates: list[AuditCandidate] = []
        for document in documents:
            matches = list(header_pattern.finditer(document.text))
            if not matches and "핵심감사사항" in document.text:
                scope = "consolidated" if "연결재무제표" in document.text[:2000] else "separate"
                candidates.append(
                    AuditCandidate(document, document.text, scope, 30 if scope == "consolidated" else 10, document.name)
                )
                continue
            for index, match in enumerate(matches):
                start = max(0, match.start() - 200)
                end = max(start, matches[index + 1].start() - 200) if index + 1 < len(matches) else len(document.text)
                segment = document.text[start:end]
                title_area = document.text[max(0, match.start() - 250) : match.start() + 350]
                scope = "consolidated" if "연결재무제표" in title_area else "separate"
                score = 100 if scope == "consolidated" else 40
                if "핵심감사사항" in segment:
                    score += 25
                if "내부회계관리제도" in title_area:
                    score -= 80
                candidates.append(
                    AuditCandidate(
                        document=document,
                        text=segment,
                        report_scope=scope,
                        score=score,
                        locator=f"{document.name} / 감사보고서 {index + 1}",
                    )
                )
        return sorted(candidates, key=lambda item: (item.score, len(item.text)), reverse=True)

    @staticmethod
    def _find_auditor(text: str) -> str:
        candidates: list[str] = []
        for line in text.splitlines():
            compact_line = re.sub(r"\s+", "", line)
            for match in re.findall(r"[가-힣A-Za-z0-9㈜()ㆍ·]+회계법인", compact_line):
                if 4 <= len(match) <= 24:
                    candidates.append(match)
        return candidates[-1] if candidates else ""

    @staticmethod
    def _kam_section(text: str) -> str:
        match = re.search(r"핵심감사사항", text)
        if not match:
            return ""
        start = match.end()
        end_pattern = re.compile(
            r"\n(?:기타사항|계속기업과 관련된 중요한 불확실성|"
            r"(?:연결)?재무제표에 대한 경영진과 지배기구의 책임|"
            r"(?:연결)?재무제표감사에 대한 감사인의 책임)\s*\n"
        )
        end_match = end_pattern.search(text, start)
        return text[start : end_match.start() if end_match else len(text)].strip()

    @staticmethod
    def _find_marker(lines: list[str], start: int, stop: int, patterns: tuple[str, ...]) -> int | None:
        for index in range(start, stop):
            compact = re.sub(r"\s+", "", lines[index])
            if any(pattern in compact for pattern in patterns):
                return index
        return None

    @classmethod
    def _extract_items(cls, section: str, locator: str) -> tuple[list[KamItem], str]:
        lines = [line for line in section.splitlines() if line.strip()]
        reason_patterns = (
            "핵심감사사항으로결정한이유",
            "핵심감사사항으로선정한이유",
            "핵심감사사항으로결정된이유",
            "핵심감사사항으로선정된이유",
            "핵심감사사항으로결정한근거",
        )
        response_patterns = (
            "핵심감사사항이감사에서다루어진방법",
            "핵심감사사항에대응하기위한감사절차",
            "감사인의대응",
        )
        reason_indexes = [
            index
            for index, line in enumerate(lines)
            if any(pattern in re.sub(r"\s+", "", line) for pattern in reason_patterns)
        ]
        if not reason_indexes:
            prose_response_patterns = (
                "이와관련하여우리가수행한주요감사절차는다음과같습니다",
                "이에대하여우리가수행한주요감사절차는다음과같습니다",
                "이와관련하여수행한주요감사절차는다음과같습니다",
            )
            response_indexes = [
                index
                for index, line in enumerate(lines)
                if any(pattern in re.sub(r"\s+", "", line) for pattern in prose_response_patterns)
            ]
            if response_indexes:
                title_indexes: list[int] = []
                for number, response_index in enumerate(response_indexes):
                    lower_bound = response_indexes[number - 1] + 1 if number else 0
                    title_index = next(
                        (
                            index
                            for index in range(response_index - 1, lower_bound - 1, -1)
                            if cls._looks_like_title(lines[index])
                        ),
                        -1,
                    )
                    if title_index < 0:
                        return [KamItem(1, "핵심감사사항", "", "", section, locator)], "raw_only"
                    title_indexes.append(title_index)

                items: list[KamItem] = []
                for number, response_index in enumerate(response_indexes, start=1):
                    title_index = title_indexes[number - 1]
                    next_title = title_indexes[number] if number < len(title_indexes) else len(lines)
                    items.append(
                        KamItem(
                            kam_no=number,
                            kam_title=lines[title_index],
                            why_kam="\n".join(lines[title_index + 1 : response_index]).strip(),
                            audit_response="\n".join(lines[response_index + 1 : next_title]).strip(),
                            raw_text="\n".join(lines[title_index:next_title]).strip(),
                            source_locator=locator,
                        )
                    )
                return items, "complete"

            if len(section) < 80:
                return [], "failed"
            title = next((line for line in lines if cls._looks_like_title(line)), "핵심감사사항")
            return [KamItem(1, title, "", "", section, locator)], "raw_only"

        title_indexes: list[int] = []
        previous_title = -1
        for reason_index in reason_indexes:
            title_index = reason_index - 1
            while title_index > previous_title and len(lines[title_index]) > 140:
                title_index -= 1
            title_indexes.append(max(previous_title + 1, title_index))
            previous_title = title_indexes[-1]

        items: list[KamItem] = []
        complete = True
        for number, reason_index in enumerate(reason_indexes, start=1):
            title_index = title_indexes[number - 1]
            next_title = title_indexes[number] if number < len(title_indexes) else len(lines)
            response_index = cls._find_marker(lines, reason_index + 1, next_title, response_patterns)
            if response_index is None:
                complete = False
                response_index = next_title
            title = re.sub(r"^\s*(?:\d+|[가-힣])[.)]\s*", "", lines[title_index]).strip()
            why = "\n".join(lines[reason_index + 1 : response_index]).strip()
            audit_response = "\n".join(lines[response_index + 1 : next_title]).strip() if response_index < next_title else ""
            raw_text = "\n".join(lines[title_index:next_title]).strip()
            items.append(KamItem(number, title or f"핵심감사사항 {number}", why, audit_response, raw_text, locator))
        return items, "complete" if complete else "partial"

    @staticmethod
    def _looks_like_title(line: str) -> bool:
        compact = re.sub(r"\s+", "", line)
        if not 2 <= len(compact) <= 120:
            return False
        if compact.startswith(("ㆍ", "-", "※")) or "별도의의견을제공" in compact:
            return False
        if "핵심감사사항은우리" in compact or "전문가적판단" in compact:
            return False
        sentence_endings = ("습니다.", "입니다.", "됩니다.", "않습니다.", "있습니다.", "하였습니다.")
        return not compact.endswith(sentence_endings)

    def _result_from_candidate(
        self,
        selected: AuditCandidate,
        company: Company,
        filing: Filing,
        *,
        source_url: str | None = None,
    ) -> KamResult:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        base = {
            "corp_code": company.corp_code,
            "stock_code": company.stock_code,
            "corp_name": company.corp_name,
            "rcept_no": filing.rcept_no,
            "report_name": filing.report_name,
            "report_period_end": filing.report_period_end,
            "rcept_date": filing.rcept_date,
            "is_amended": filing.is_amended,
            "source_url": source_url or filing.source_url,
            "parser_version": self.parser_version,
            "extracted_at": now,
        }
        auditor_name = self._find_auditor(selected.text)
        section = self._kam_section(selected.text)
        warnings: list[str] = []
        if not auditor_name:
            warnings.append("auditor_not_identified: 회계법인명을 자동으로 확인하지 못했습니다.")
        if not section:
            return KamResult(
                **base,
                report_scope=selected.report_scope,
                auditor_name=auditor_name,
                status=ResultStatus.KAM_NOT_PRESENT,
                confidence="medium" if auditor_name else "low",
                source_locator=selected.locator,
                warnings=warnings,
            )

        items, quality = self._extract_items(section, selected.locator)
        if quality == "failed" or not items:
            status = ResultStatus.PARSE_FAILED
            confidence = "low"
        elif quality == "raw_only":
            status = ResultStatus.MANUAL_REVIEW_REQUIRED
            confidence = "low"
            warnings.append("KAM 섹션은 찾았지만 선정 이유와 감사인의 대응을 분리하지 못했습니다.")
        else:
            status = ResultStatus.SUCCESS if quality == "complete" else ResultStatus.MANUAL_REVIEW_REQUIRED
            confidence = "high" if quality == "complete" and auditor_name else "medium"
            if quality == "partial":
                warnings.append("일부 KAM에서 감사인의 대응 경계를 확정하지 못했습니다.")
        return KamResult(
            **base,
            report_scope=selected.report_scope,
            auditor_name=auditor_name,
            status=status,
            confidence=confidence,
            source_locator=selected.locator,
            kam_items=items,
            warnings=warnings,
        )

    def parse_audit_report_html(
        self,
        report_html: bytes,
        company: Company,
        filing: Filing,
        *,
        report_scope: str,
        source_locator: str,
        source_url: str,
    ) -> KamResult:
        document = TextDocument("dart-viewer.html", "text/html", _markup_to_text(_decode(report_html)))
        selected = AuditCandidate(document, document.text, report_scope, 100, source_locator)
        return self._result_from_candidate(selected, company, filing, source_url=source_url)

    def parse(self, archive: bytes, company: Company, filing: Filing) -> KamResult:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        base = {
            "corp_code": company.corp_code,
            "stock_code": company.stock_code,
            "corp_name": company.corp_name,
            "rcept_no": filing.rcept_no,
            "report_name": filing.report_name,
            "report_period_end": filing.report_period_end,
            "rcept_date": filing.rcept_date,
            "is_amended": filing.is_amended,
            "source_url": filing.source_url,
            "parser_version": self.parser_version,
            "extracted_at": now,
        }
        documents = self._read_documents(archive)
        candidates = self._audit_candidates(documents)
        if not candidates:
            return KamResult(
                **base,
                report_scope="",
                auditor_name="",
                status=ResultStatus.AUDIT_REPORT_NOT_IDENTIFIED,
                confidence="low",
                source_locator="",
                warnings=["감사보고서를 자동으로 식별하지 못했습니다."],
            )

        return self._result_from_candidate(candidates[0], company, filing)
