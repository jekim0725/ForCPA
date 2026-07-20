"""DART 회사 고유번호 캐시와 상장기업 검색."""

from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .api_client import DartClient
from .models import Company


class CompanyDirectory:
    def __init__(self, client: DartClient, cache_path: Path, *, ttl_days: int = 7) -> None:
        self.client = client
        self.cache_path = cache_path
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self._companies: list[Company] | None = None

    def _cache_is_fresh(self) -> bool:
        return self.cache_path.exists() and time.time() - self.cache_path.stat().st_mtime < self.ttl_seconds

    @staticmethod
    def _extract_xml(archive: bytes) -> bytes:
        if not archive.startswith(b"PK"):
            raise ValueError("corpCode.xml 응답이 ZIP 파일이 아닙니다.")
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = [info for info in bundle.infolist() if info.filename.lower().endswith(".xml")]
            if not members:
                raise ValueError("회사 고유번호 XML을 찾지 못했습니다.")
            info = members[0]
            if info.file_size > 100 * 1024 * 1024:
                raise ValueError("회사 고유번호 파일이 허용 크기를 초과했습니다.")
            return bundle.read(info)

    def _load_xml(self, *, force_refresh: bool = False) -> bytes:
        if not force_refresh and self._cache_is_fresh():
            return self.cache_path.read_bytes()
        xml_bytes = self._extract_xml(self.client.download_corp_codes())
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_bytes(xml_bytes)
        temporary.replace(self.cache_path)
        return xml_bytes

    def load(self, *, force_refresh: bool = False) -> list[Company]:
        if self._companies is not None and not force_refresh:
            return self._companies
        root = ElementTree.fromstring(self._load_xml(force_refresh=force_refresh))
        companies: list[Company] = []
        for node in root.findall("list"):
            stock_code = (node.findtext("stock_code") or "").strip()
            if not re.fullmatch(r"\d{6}", stock_code):
                continue
            companies.append(
                Company(
                    corp_code=(node.findtext("corp_code") or "").strip(),
                    corp_name=(node.findtext("corp_name") or "").strip(),
                    stock_code=stock_code,
                    modify_date=(node.findtext("modify_date") or "").strip(),
                )
            )
        self._companies = companies
        return companies

    @staticmethod
    def _normalize_name(value: str) -> str:
        normalized = value.casefold().strip()
        for token in ("주식회사", "(주)", "㈜"):
            normalized = normalized.replace(token, "")
        return re.sub(r"\s+", "", normalized)

    def search(self, query: str, *, limit: int = 30, force_refresh: bool = False) -> list[Company]:
        value = query.strip()
        if not value:
            return []
        companies = self.load(force_refresh=force_refresh)
        if re.fullmatch(r"\d{6}", value):
            return [company for company in companies if company.stock_code == value]

        normalized_query = self._normalize_name(value)
        exact: list[Company] = []
        partial: list[Company] = []
        for company in companies:
            normalized_name = self._normalize_name(company.corp_name)
            if normalized_name == normalized_query:
                exact.append(company)
            elif normalized_query in normalized_name:
                partial.append(company)
        return (exact + sorted(partial, key=lambda item: (len(item.corp_name), item.corp_name)))[:limit]
