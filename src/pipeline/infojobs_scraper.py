"""Scraper propio de InfoJobs con curl_cffi + BeautifulSoup."""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)


# ── Contratos ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SearchStub:
    """Resultado de una card en la página de búsqueda."""

    title: str
    company: str
    city: str
    province: str | None
    url: str
    offer_id: str
    published_at: str | None
    salary_text: str | None
    is_promoted: bool = False


@dataclass(frozen=True)
class RawOfferDetail:
    """Oferta completa extraída del HTML de detalle."""

    offer_id: str
    title: str
    company: str
    url: str | None = None
    city: str | None = None
    province: str | None = None
    contract_type: str | None = None
    workday: str | None = None
    work_mode: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    experience_min_years: int | None = None
    education_min: str | None = None
    languages: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    sector: str | None = None
    description_html: str = ""
    description_text: str = ""
    published_at: str | None = None
    source: str = "scraper"
    scraped_at: str = ""
    employer_id: str | None = None


# ── Parser ─────────────────────────────────────────────────────────────


class InfoJobsParser:
    """Parser de HTML de InfoJobs. Sin HTTP, testeable con snapshots."""

    # Mapeo de labels del <dl> de Requisitos a nombres de campo
    _REQUISITO_LABELS: dict[str, str] = {
        "estudios": "education_min",
        "experiencia": "experience_min",
        "sector": "sector",
        "idiomas": "languages",
        "conocimientos": "skills",
    }

    @staticmethod
    def parse_search_html(html: str) -> list[SearchStub]:
        """Parsea la página de resultados de búsqueda.

        Excluye anuncios (aria-label="Publicidad").
        Devuelve solo ofertas reales.
        """
        soup = BeautifulSoup(html, "lxml")
        stubs: list[SearchStub] = []

        cards = soup.select("li.ij-OfferList-offerCardItem")
        if not cards:
            log.warning("No se encontraron ofertas en el HTML de búsqueda")
            return stubs

        for card in cards:
            try:
                stub = InfoJobsParser._parse_search_card(card)
                if stub and not stub.is_promoted:
                    stubs.append(stub)
            except Exception as e:
                log.warning("Error parseando card de búsqueda: %s", e)
                continue

        return stubs

    @staticmethod
    def _parse_search_card(card: Tag) -> SearchStub | None:
        """Parsea una card individual de la lista de búsqueda."""
        # Título — está en un <a> dentro de la card con clase description-link
        title_el = card.select_one("a.ij-OfferCardContent-description-link")
        title = title_el.get_text(strip=True) if title_el else ""

        # Enlace de detalle
        link_el = card.select_one("a[href*='/of-']")
        if not link_el:
            return None
        href = link_el.get("href", "")
        full_url = f"https:{href}" if href.startswith("//") else href

        # offer_id
        offer_id = ""
        m = re.search(r"/of-([a-zA-Z0-9]+)", href)
        if m:
            offer_id = m.group(1)

        # Compañía
        company_el = card.select_one(".ij-OfferCardContent-description-subtitle-link")
        company = company_el.get_text(strip=True) if company_el else ""

        # Ciudad
        city_el = card.select_one(
            ".ij-OfferCardContent-description-city-text, "
            ".ij-OfferCardContent-description-city, "
            "[data-id='city']"
        )
        city = city_el.get_text(strip=True) if city_el else ""

        # Texto de salario visible en la card (crudo)
        salary_el = card.select_one(
            ".ij-OfferCardContent-description-salary, [class*='salary'], [class*='Salary']"
        )
        salary_text = salary_el.get_text(strip=True) if salary_el else None

        # Fecha de publicación
        published_el = card.select_one("time, [datetime], [class*='date'], [class*='Date']")
        published = (
            published_el.get("datetime") or published_el.get_text(strip=True)
            if published_el
            else None
        )

        return SearchStub(
            title=title,
            company=company,
            city=city,
            province=None,
            url=full_url,
            offer_id=offer_id,
            published_at=published,
            salary_text=salary_text,
            is_promoted=False,
        )

    @staticmethod
    def parse_detail_html(html: str, url: str | None = None) -> RawOfferDetail:
        """Parsea la página de detalle de una oferta."""
        soup = BeautifulSoup(html, "lxml")

        # Datos básicos del header
        title = InfoJobsParser._extract_title(soup)
        company = InfoJobsParser._extract_company(soup)
        offer_id = InfoJobsParser._extract_offer_id_from_url(
            url
        ) or InfoJobsParser._extract_offer_id(soup, html[:8192])

        # Bloques principales
        details = InfoJobsParser._parse_header_details(soup)
        if not details.get("work_mode"):
            for sel in [
                "[data-testid='condition-mode']",
                "[class*='condition'] span",
                ".ij-Chip",
                "[class*='tag']",
            ]:
                chip = soup.select_one(sel)
                if chip:
                    t = chip.get_text(strip=True).lower()
                    if t in ("remoto", "teletrabajo", "presencial", "híbrido", "hibrido"):
                        details["work_mode"] = t.capitalize()
                        break
            if not details.get("work_mode"):
                title_lower = title.lower()
                if "teletrabajo" in title_lower or "remoto" in title_lower:
                    details["work_mode"] = "Teletrabajo"
                    log.warning(
                        "work_mode fallback via title: offer_id=%s title=%s", offer_id, title[:60]
                    )
                elif "híbrido" in title_lower or "hibrido" in title_lower:
                    details["work_mode"] = "Híbrido"
                    log.warning(
                        "work_mode fallback via title: offer_id=%s title=%s", offer_id, title[:60]
                    )
        requisitos = InfoJobsParser._parse_requisitos(soup)
        desc_html, desc_text = InfoJobsParser._parse_description(soup)
        salary = InfoJobsParser._extract_salary(details.get("salary", ""))

        published = InfoJobsParser._extract_published_at(soup)
        if not published:
            published = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        employer_id = InfoJobsParser._extract_employer_id(soup)

        now = datetime.now(timezone.utc).isoformat()

        return RawOfferDetail(
            offer_id=offer_id,
            title=title,
            company=company,
            url=url,
            city=details.get("city"),
            province=details.get("province"),
            contract_type=details.get("contract_type"),
            workday=details.get("workday"),
            work_mode=details.get("work_mode"),
            salary_min=salary[0],
            salary_max=salary[1],
            salary_period=salary[2],
            experience_min_years=requisitos.get("experience_min_years"),
            education_min=requisitos.get("education_min"),
            languages=requisitos.get("languages", []),
            skills=requisitos.get("skills", []),
            sector=requisitos.get("sector"),
            description_html=desc_html,
            description_text=desc_text,
            published_at=published,
            scraped_at=now,
            employer_id=employer_id,
        )

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        """Extrae el título de la oferta."""
        el = soup.select_one("h1.ij-BaseTypography.ij-Heading.ij-Heading-title1")
        if el:
            return el.get_text(strip=True)
        el = soup.select_one("h1")
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _extract_company(soup: BeautifulSoup) -> str:
        """Extrae el nombre de la empresa."""
        el = soup.select_one(".ij-OfferDetailHeader-companyLogo-companyName a")
        if el:
            return el.get_text(strip=True)
        el = soup.select_one("[class*='company'] a")
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _extract_employer_id(soup: BeautifulSoup) -> str | None:
        """Extrae employer_id desde el link de la empresa (em-i{HASH})."""
        for selector in [
            ".ij-OfferDetailHeader-companyLogo-companyName a",
            ".ij-OfferDetailHeader-companyLogo a",
            "[class*='companyLogo'] a",
        ]:
            el = soup.select_one(selector)
            if el:
                href = el.get("href") or ""
                m = re.search(r"/em-i([a-zA-Z0-9_]+)", href)
                if m:
                    return m.group(1)
        return None

    @staticmethod
    def _extract_offer_id_from_url(url: str | None) -> str | None:
        """Extrae el offer ID desde la URL de InfoJobs."""
        if not url:
            return None
        m = re.search(r"/of-([a-zA-Z0-9]+)", url)
        return m.group(1) if m else None

    @staticmethod
    def _extract_offer_id(soup: BeautifulSoup, raw_html: str) -> str:
        """Extrae el ID de la oferta desde la URL o datos embebidos."""
        # Buscar en meta/link canonical
        m = re.search(r"/of-([a-zA-Z0-9]+)", raw_html)
        if m:
            return m.group(1)
        # Fallback: buscar en cualquier href
        m = re.search(r'"ad_id":"([^"]+)"', raw_html)
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _parse_header_details(soup: BeautifulSoup) -> dict[str, Any]:
        """Parsea los items del header (ubicación, modalidad, salario, contrato).

        Usa heurística de texto porque los SVG no tienen atributos semánticos.
        Cada item que no matchea patrones conocidos se loggea como fallback.
        """
        result: dict[str, Any] = {}
        container = soup.select_one(".ij-OfferDetailHeader-detailsList")
        if not container:
            return result

        items = container.select(".ij-OfferDetailHeader-detailsList-item p.ij-BaseTypography")
        for p_tag in items:
            text = p_tag.get_text(strip=True)

            # 1) Ciudad: "Barcelona (Barcelona)" o "A Coruña (A Coruña)"
            city_m = re.match(
                r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñÀ-ÿ]*(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñÀ-ÿ]+)*)\s*\(([^)]+)\)$",
                text,
            )
            if city_m:
                result["city"] = city_m.group(1)
                result["province"] = city_m.group(2)
                continue

            # 2) Modalidad: Presencial, Híbrido, Remoto, Teletrabajo
            if text.lower() in (
                "presencial",
                "híbrido",
                "hibrido",
                "remoto",
                "teletrabajo",
            ):
                result["work_mode"] = text
                continue

            # 3) Salario: "30.000€ - 40.000€ Bruto/año" o "Salario no disponible"
            if re.search(r"(?:€|euro|sueldo|salario)", text, re.IGNORECASE):
                result["salary"] = text
                continue

            # 4) Experiencia: "Experiencia mínima: Al menos 4 años"
            exp_m = re.match(
                r"(?:Experiencia mínima[:\s]*)?(?:Al menos\s+)?(\d+)\s+(?:año|años)",
                text,
                re.IGNORECASE,
            )
            if exp_m:
                result["experience_min_years"] = int(exp_m.group(1))
                continue

            # 5) Contrato + jornada
            if any(
                w in text.lower()
                for w in (
                    "contrato",
                    "jornada",
                    "formativo",
                    "indefinido",
                    "temporal",
                    "completa",
                    "parcial",
                )
            ):
                parts = text.split(",")
                if len(parts) >= 2:
                    result["contract_type"] = parts[0].strip()
                    result["workday"] = parts[1].strip()
                else:
                    result["contract_type"] = text
                continue

            # 6) Educación en header
            if any(
                w in text.lower()
                for w in (
                    "grado",
                    "fp",
                    "ciclo",
                    "formación",
                    "bachiller",
                    "eso",
                    "máster",
                    "master",
                )
            ):
                result["education_min"] = text
                continue

            # Fallback: loggear el texto sin parsear
            log.debug("Header item sin match: '%s'", text[:60])

        return result

    @staticmethod
    def _parse_requisitos(soup: BeautifulSoup) -> dict[str, Any]:
        """Parsea el bloque <dl> dentro de la sección Requisitos.

        Itera por label del <dt> (no por posición).
        """
        result: dict[str, Any] = {}

        # Buscar la sección Requisitos
        req_heading = soup.find("h3", string=re.compile(r"Requisitos", re.IGNORECASE))
        if not req_heading:
            return result

        dl = req_heading.find_next_sibling("dl") or req_heading.find_next("dl")
        if not dl:
            return result

        current_dt = None
        for child in dl.children:
            if isinstance(child, Tag):
                if child.name == "dt":
                    current_dt = child.get_text(strip=True).lower()
                elif child.name == "dd" and current_dt:
                    value = child.get_text(separator=" ", strip=True)
                    InfoJobsParser._assign_requisito(result, current_dt, value, child)
                    current_dt = None

        return result

    @staticmethod
    def _assign_requisito(result: dict[str, Any], label: str, value: str, dd_tag: Tag) -> None:
        """Asigna el valor del <dd> al campo correcto según el label del <dt>."""
        if "estudio" in label:
            result["education_min"] = value
        elif "experiencia" in label:
            years = InfoJobsParser._parse_experience_years(value)
            if years is not None:
                result["experience_min_years"] = years
        elif "sector" in label:
            result["sector"] = value
        elif "idioma" in label:
            result["languages"] = InfoJobsParser._parse_languages(dd_tag)
        elif "conocimiento" in label:
            result["skills"] = InfoJobsParser._parse_skills(dd_tag)

    @staticmethod
    def _parse_experience_years(text: str) -> int | None:
        """Parsea años de experiencia desde texto como 'Al menos 3 años' o 'No Requerida'."""
        if re.search(r"\bno\b", text.lower()):
            return 0
        m = re.search(r"(\d+)\s*(?:año|años)", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _parse_languages(dd: Tag) -> list[dict]:
        """Parsea idiomas desde el <dd>.

        Formato esperado: lista de items con nombre e idioma.
        """
        langs: list[dict] = []
        # Buscar items de lista
        items = dd.select("li, span, p")
        for item in items:
            text = item.get_text(strip=True)
            if not text:
                continue
            # Formato: "Idioma - Nivel"
            m = re.match(
                r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)\s*[-–:]\s*(.+)",
                text,
            )
            if m:
                langs.append({"name": m.group(1).strip(), "level": m.group(2).strip()})
            else:
                langs.append({"name": text, "level": ""})
        return langs

    @staticmethod
    def _parse_skills(dd: Tag) -> list[str]:
        """Parsea conocimientos necesarios desde el <dd>."""
        skills: list[str] = []
        items = dd.select("li, span, p, a")
        for item in items:
            text = item.get_text(strip=True)
            if text and len(text) > 1:
                skills.append(text)
        if not skills:
            text = dd.get_text(separator=",", strip=True)
            skills = [s.strip() for s in text.split(",") if s.strip()]
        return list(dict.fromkeys(skills))

    @staticmethod
    def _parse_description(soup: BeautifulSoup) -> tuple[str, str]:
        """Extrae el HTML y texto plano de la descripción."""
        for selector in [
            ".ij-OfferDetailDescription",
            ".ij-EnrichedTextArea",
            "section.ij-OfferDetailPage-mainContent",
            "section.ij-OfferDetail-description",
            "[data-testid='offer-description']",
            "article .ij-BaseTypography",
        ]:
            desc_section = soup.select_one(selector)
            if desc_section:
                text = desc_section.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return str(desc_section), text
        return "", ""

    @staticmethod
    def _extract_salary(text: str) -> tuple[float | None, float | None, str | None]:
        """Parsea salario desde texto como '30.000€ - 40.000€ Bruto/año'.

        Returns: (min, max, period)
        """
        if not text or "no disponible" in text.lower():
            return None, None, None

        # Patrón: "30.000€ - 40.000€ Bruto/año"
        m = re.search(
            r"([\d.]+)\s*€?\s*[-–]\s*([\d.]+)\s*€?(?:\s*(.+))?",
            text,
        )
        if m:
            period = m.group(3).strip() if m.group(3) else None
            if period and "/" in period:
                period = period.split("/")[-1].strip().lower()
            return (
                float(m.group(1).replace(".", "")),
                float(m.group(2).replace(".", "")),
                period,
            )

        # Patrón: "Desde 30.000€"
        m = re.search(r"(?:Desde|de)\s+([\d.]+)\s*€", text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(".", "")), None, None

        return None, None, None

    @staticmethod
    def _extract_published_at(soup: BeautifulSoup) -> str | None:
        """Extrae y normaliza la fecha de publicación a ISO 8601 (YYYY-MM-DD)."""
        now = datetime.now(timezone.utc)

        # 1) Intentar time[datetime] por si algún día lo añaden
        for selector in [
            ".ij-OfferDetailHeader-publishedAt time[datetime]",
            ".ij-OfferDetailHeader time[datetime]",
            "time[datetime]",
        ]:
            el = soup.select_one(selector)
            if el and el.get("datetime"):
                dt = el["datetime"]
                if re.match(r"\d{4}-\d{2}-\d{2}", dt):
                    return dt[:10]

        # 2) Texto plano con formato relativo o literal
        for selector in [
            "[data-testid='sincedate-tag']",
            ".ij-FormatterSincedate",
            "[class*='publishedAt']",
            "[class*='published']",
        ]:
            el = soup.select_one(selector)
            if not el:
                continue
            text = el.get_text(strip=True).lower()

            # "hace Nd" o "hace N días"
            m = re.search(r"hace\s+(\d+)\s*d", text)
            if m:
                return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

            # "hace Nh"
            m = re.search(r"hace\s+(\d+)\s*h", text)
            if m:
                return now.strftime("%Y-%m-%d")

            # "hace N semanas" / "hace N sem"
            m = re.search(r"hace\s+(\d+)\s*sem", text)
            if m:
                return (now - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")

            # "hoy"
            if "hoy" in text:
                return now.strftime("%Y-%m-%d")

            # "ayer"
            if "ayer" in text:
                return (now - timedelta(days=1)).strftime("%Y-%m-%d")

            # "29 may", "3 jun", "15 ene" — fecha literal sin año
            MESES = {
                "ene": 1,
                "feb": 2,
                "mar": 3,
                "abr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "ago": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dic": 12,
            }
            m = re.search(r"(\d{1,2})\s+([a-záéíóú]{3})", text)
            if m:
                day = int(m.group(1))
                month = MESES.get(m.group(2)[:3])
                if month:
                    year = now.year
                    candidate = datetime(year, month, day, tzinfo=timezone.utc)
                    if candidate > now:
                        candidate = datetime(year - 1, month, day, tzinfo=timezone.utc)
                    return candidate.strftime("%Y-%m-%d")

        return None

    @staticmethod
    def extract_total_results(html: str) -> int:
        """Extrae el número total de resultados de la página de búsqueda."""
        soup = BeautifulSoup(html, "lxml")
        # Buscar en el elemento que contiene el total
        for selector in [
            "#main-heading",
            ".ij-ResultsOverview",
            "[data-testid='total-results']",
            "h1",
        ]:
            el = soup.select_one(selector)
            if el:
                m = re.search(r"(\d[\d.]*)\s*ofertas?", el.get_text())
                if m:
                    return int(m.group(1).replace(".", ""))
        return 0

    @staticmethod
    def to_db_dict(detail: RawOfferDetail) -> dict[str, Any]:
        """Convierte RawOfferDetail al schema de la tabla offers en DB.

        Esto permite que fetch.py convierta sin acoplamiento directo.
        """
        return {
            "source_id": detail.offer_id,
            "source": "infojobs",
            "url": detail.url,
            "title": detail.title,
            "company_name": detail.company,
            "city": detail.city,
            "province": detail.province,
            "salary_min": detail.salary_min,
            "salary_max": detail.salary_max,
            "salary_period": detail.salary_period,
            "contract_type": detail.contract_type,
            "work_mode": detail.work_mode,
            "experience_min": detail.experience_min_years,
            "education_level": detail.education_min,
            "skills_required": detail.skills,
            "description_clean": detail.description_text,
            "description_raw": detail.description_html,
            "published_at": detail.published_at,
        }


# ── Scraper HTTP ────────────────────────────────────────────────────────


class InfoJobsScraper:
    """Cliente HTTP para InfoJobs usando curl_cffi.

    Capa de transporte: fetch con TLS fingerprinting, rate limiting,
    paginación. Delega el parseo a InfoJobsParser.
    """

    BASE_URL = "https://www.infojobs.net"
    SEARCH_PATH = "/jobsearch/search-results/list.xhtml"

    _FINGERPRINTS = ["chrome131", "safari17", "chrome124"]

    def __init__(
        self,
        delay: float = 4.0,
        max_retries: int = 3,
        timeout: int = 30,
    ):
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError:
            raise ImportError("curl_cffi no está instalado. Ejecuta: pip install curl_cffi")

        fp = random.choice(self._FINGERPRINTS)
        self.session = cffi_requests.Session(impersonate=fp)
        self.delay = delay
        self.jitter = 2.0
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request = 0.0

    def _rate_limit(self) -> None:
        """Espera self.delay + jitter aleatorio desde la última petición."""
        elapsed = time.monotonic() - self._last_request
        wait = self.delay + random.uniform(0, self.jitter)
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_request = time.monotonic()

    def _fetch(self, url: str) -> str | None:
        """GET con reintentos y rate limiting."""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                log.warning(
                    "Intento %d/%d falló para %s: %s",
                    attempt + 1,
                    self.max_retries,
                    url,
                    e,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
        return None

    def search(
        self,
        query: str = "",
        location: str = "",
        page_limit: int = 1,
        max_items: int = 0,
        since_date: str | None = None,
    ) -> list[SearchStub]:
        """Busca ofertas y devuelve stubs de todas las páginas.

        Args:
            query: Término de búsqueda (keyword).
            location: Ubicación.
            page_limit: Máximo de páginas a recorrer.
            max_items: Máximo total de ofertas. 0 = sin límite.
            since_date: Filtro temporal. Valores: _24_HOURS, _7_DAYS, _15_DAYS, ANY.
        """
        all_stubs: list[SearchStub] = []

        for page in range(1, page_limit + 1):
            params = {"page": page, "sortBy": "PUBLICATION_DATE"}
            if since_date:
                params["sinceDate"] = since_date
            if query:
                params["keyword"] = query
            if location:
                params["location"] = location

            from urllib.parse import urlencode

            qs = urlencode(params)
            url = f"{self.BASE_URL}{self.SEARCH_PATH}?{qs}"
            html = self._fetch(url)
            if not html:
                log.warning("No se pudo obtener la página %d", page)
                break

            stubs = InfoJobsParser.parse_search_html(html)
            if not stubs:
                log.info("Sin más ofertas en página %d — fin", page)
                break

            all_stubs.extend(stubs)

            # Early stop si alcanzamos max_items
            if max_items > 0 and len(all_stubs) >= max_items:
                all_stubs = all_stubs[:max_items]
                log.info(
                    "Alcanzado max_items=%d en página %d — parando",
                    max_items,
                    page,
                )
                break

            log.info(
                "Página %d: %d ofertas (total acumulado: %d)",
                page,
                len(stubs),
                len(all_stubs),
            )

        return all_stubs

    def detail(self, url: str) -> RawOfferDetail | None:
        """Obtiene y parsea una oferta individual."""
        html = self._fetch(url)
        if not html:
            return None
        return InfoJobsParser.parse_detail_html(html, url=url)

    def close(self) -> None:
        """Cierra la sesión HTTP."""
        try:
            self.session.close()
        except Exception:
            pass
