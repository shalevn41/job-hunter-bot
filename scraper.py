"""
scraper.py — Job board scrapers for Job Hunter Bot
Each scraper returns a list of job dicts:
  {title, company, location, description, url, date, site}

Note: Sites that use React/Next.js SPAs may return empty results
with requests+BS4. If needed, replace those scrapers with Playwright.
"""

import logging
import random
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Browser-like headers ────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Broad search terms to maximize coverage — keyword filtering happens in bot.py
SEARCH_TERMS = ["AI", "אוטומציה", "automation", "python", "n8n", "בינה מלאכותית"]


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _delay():
    time.sleep(random.uniform(2, 3))


def _get(url: str, extra_headers: Optional[dict] = None, timeout: int = 15) -> Optional[requests.Response]:
    try:
        headers = {**HEADERS, **(extra_headers or {})}
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code} fetching {url}")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error fetching {url}")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching {url}")
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
    return None


def _job(title: str, company: str, location: str,
         description: str, url: str, date: str, site: str) -> dict:
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "description": (description or "").strip(),
        "url": (url or "").strip(),
        "date": (date or "").strip(),
        "site": site,
    }


def _abs_url(href: str, base: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


# ── AllJobs.co.il ───────────────────────────────────────────────────────────────

def scrape_alljobs() -> list:
    """
    AllJobs uses ASPX server-side rendering — most reliable of the bunch.
    Tries first 2 pages per search term.
    """
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:4]:
        for page in range(1, 3):
            url = (
                f"https://www.alljobs.co.il/SearchResultsGuest.aspx?"
                f"frm={page}&isSalary=0&position={quote_plus(term)}"
                f"&salary=0&SalaryType=1&isLight=0&fromAge=0&toAge=0"
                f"&SeniorityType=0&jobType=0&fieldType=0&edu=0&city=0"
                f"&company=&companyId=0"
            )
            resp = _get(url)
            if not resp:
                _delay()
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # AllJobs wraps each listing in a div with class containing "single-job"
            containers = (
                soup.find_all("div", class_=lambda c: c and "single-job" in " ".join(c))
                or soup.find_all("div", class_=lambda c: c and "job-item" in " ".join(c))
                or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c))
            )

            for item in containers:
                try:
                    title_el = (
                        item.find("h2")
                        or item.find("h3")
                        or item.find(attrs={"class": lambda c: c and "title" in " ".join(c).lower()})
                    )
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if len(title) < 3:
                        continue

                    company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                    location_el = item.find(attrs={"class": lambda c: c and any(
                        w in " ".join(c).lower() for w in ("city", "location", "area")
                    )})
                    desc_el = item.find(attrs={"class": lambda c: c and "desc" in " ".join(c).lower()}) or item.find("p")
                    link_el = title_el.find("a", href=True) or item.find("a", href=True)

                    company = company_el.get_text(strip=True) if company_el else ""
                    location = location_el.get_text(strip=True) if location_el else ""
                    description = desc_el.get_text(strip=True) if desc_el else ""
                    link = _abs_url(link_el["href"] if link_el else "", "https://www.alljobs.co.il")

                    if link and link in seen_urls:
                        continue
                    seen_urls.add(link)

                    jobs.append(_job(title, company, location, description, link, "", "AllJobs"))
                except Exception as e:
                    logger.debug(f"AllJobs parse error: {e}")

            _delay()

    logger.info(f"AllJobs: {len(jobs)} jobs found")
    return jobs


# ── JobMaster.co.il ─────────────────────────────────────────────────────────────

def scrape_jobmaster() -> list:
    """JobMaster — modern React site; may return partial results."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:3]:
        url = f"https://www.jobmaster.co.il/jobs/?currPage=1&q={quote_plus(term)}"
        resp = _get(url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("div", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("article")
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = item.find("h2") or item.find("h3") or item.find("h1")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and any(
                    w in " ".join(c).lower() for w in ("location", "city", "area")
                )})
                desc_el = item.find("p") or item.find(attrs={"class": lambda c: c and "desc" in " ".join(c).lower()})
                link_el = item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""
                link = _abs_url(link_el["href"] if link_el else "", "https://www.jobmaster.co.il")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, "", "JobMaster"))
            except Exception as e:
                logger.debug(f"JobMaster parse error: {e}")

        _delay()

    logger.info(f"JobMaster: {len(jobs)} jobs found")
    return jobs


# ── Drushim.co.il ───────────────────────────────────────────────────────────────

def scrape_drushim() -> list:
    """Drushim — tries JSON API first, falls back to HTML."""
    jobs = []
    seen_ids: set = set()

    for term in SEARCH_TERMS[:4]:
        # Attempt JSON API endpoint
        api_url = (
            f"https://www.drushim.co.il/api/jobs/fullTextSearch?"
            f"searchQuery={quote_plus(term)}&count=20&start=0"
        )
        resp = _get(api_url, extra_headers={"Accept": "application/json, text/plain, */*",
                                             "X-Requested-With": "XMLHttpRequest"})

        if resp and resp.headers.get("Content-Type", "").startswith("application/json"):
            try:
                data = resp.json()
                items = data.get("jobs") or data.get("results") or data.get("data") or []
                for item in items:
                    job_id = str(item.get("id") or item.get("jobId") or "")
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = item.get("title") or item.get("jobTitle") or ""
                    company = item.get("company") or item.get("companyName") or ""
                    location = item.get("city") or item.get("location") or item.get("area") or ""
                    description = item.get("description") or item.get("jobDescription") or ""
                    link = item.get("url") or item.get("applyUrl") or (
                        f"https://www.drushim.co.il/job/{job_id}" if job_id else ""
                    )
                    date = item.get("publishDate") or item.get("date") or ""

                    jobs.append(_job(title, company, location, description, link, date, "Drushim"))
                _delay()
                continue
            except Exception as e:
                logger.debug(f"Drushim API parse error: {e}")

        # Fallback: HTML scraping
        html_url = f"https://www.drushim.co.il/jobs/search/?q={quote_plus(term)}"
        resp = _get(html_url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        containers = (
            soup.find_all("div", class_=lambda c: c and "job-item" in " ".join(c))
            or soup.find_all("article")
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = item.find("h2") or item.find("h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                link_el = item.find("a", href=True)
                link = _abs_url(link_el["href"] if link_el else "", "https://www.drushim.co.il")

                if link in seen_ids:
                    continue
                seen_ids.add(link)

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and "city" in " ".join(c).lower()})
                desc_el = item.find("p")

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""

                jobs.append(_job(title, company, location, description, link, "", "Drushim"))
            except Exception as e:
                logger.debug(f"Drushim HTML parse error: {e}")

        _delay()

    logger.info(f"Drushim: {len(jobs)} jobs found")
    return jobs


# ── GotFriends.co.il ────────────────────────────────────────────────────────────

def scrape_gotfriends() -> list:
    """GotFriends — tech-focused Israeli job board."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:3]:
        url = f"https://www.gotfriends.co.il/jobs/?q={quote_plus(term)}"
        resp = _get(url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("div", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("article", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = item.find("h2") or item.find("h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and any(
                    w in " ".join(c).lower() for w in ("city", "location", "area")
                )})
                desc_el = item.find("p")
                link_el = item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""
                link = _abs_url(link_el["href"] if link_el else "", "https://www.gotfriends.co.il")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, "", "GotFriends"))
            except Exception as e:
                logger.debug(f"GotFriends parse error: {e}")

        _delay()

    logger.info(f"GotFriends: {len(jobs)} jobs found")
    return jobs


# ── Dialog.co.il ────────────────────────────────────────────────────────────────

def scrape_dialog() -> list:
    """Dialog — recruitment agency site."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:3]:
        url = f"https://www.dialog.co.il/jobs/?q={quote_plus(term)}"
        resp = _get(url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("div", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("article")
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = item.find("h2") or item.find("h3") or item.find("h4")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and any(
                    w in " ".join(c).lower() for w in ("city", "location", "area")
                )})
                desc_el = item.find("p")
                link_el = item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""
                link = _abs_url(link_el["href"] if link_el else "", "https://www.dialog.co.il")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, "", "Dialog"))
            except Exception as e:
                logger.debug(f"Dialog parse error: {e}")

        _delay()

    logger.info(f"Dialog: {len(jobs)} jobs found")
    return jobs


# ── Jobs.il ─────────────────────────────────────────────────────────────────────

def scrape_jobsil() -> list:
    """Jobs.il — job aggregator."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:3]:
        url = f"https://www.jobs.il/jobs/?q={quote_plus(term)}"
        resp = _get(url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("div", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("article")
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = item.find("h2") or item.find("h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and any(
                    w in " ".join(c).lower() for w in ("city", "location", "area")
                )})
                desc_el = item.find("p")
                link_el = item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""
                link = _abs_url(link_el["href"] if link_el else "", "https://www.jobs.il")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, "", "Jobs.il"))
            except Exception as e:
                logger.debug(f"Jobs.il parse error: {e}")

        _delay()

    logger.info(f"Jobs.il: {len(jobs)} jobs found")
    return jobs


# ── Jobnet.co.il ────────────────────────────────────────────────────────────────

def scrape_jobnet() -> list:
    """Jobnet — Israeli Employment Service (government), server-rendered."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:4]:
        url = f"https://www.jobnet.co.il/jobs/search/?q={quote_plus(term)}&jobtype=1"
        resp = _get(url)
        if not resp:
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("div", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("li", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("tr", class_=lambda c: c and "job" in " ".join(c).lower())
        )

        for item in containers:
            try:
                title_el = (
                    item.find("h2") or item.find("h3") or item.find("h4")
                    or item.find(attrs={"class": lambda c: c and "title" in " ".join(c).lower()})
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"class": lambda c: c and "company" in " ".join(c).lower()})
                location_el = item.find(attrs={"class": lambda c: c and any(
                    w in " ".join(c).lower() for w in ("city", "location", "area", "yishuv")
                )})
                desc_el = item.find("p") or item.find(attrs={"class": lambda c: c and "desc" in " ".join(c).lower()})
                link_el = item.find("a", href=True)
                date_el = item.find(attrs={"class": lambda c: c and "date" in " ".join(c).lower()})

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""
                link = _abs_url(link_el["href"] if link_el else "", "https://www.jobnet.co.il")
                date = date_el.get_text(strip=True) if date_el else ""

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, date, "Jobnet"))
            except Exception as e:
                logger.debug(f"Jobnet parse error: {e}")

        _delay()

    logger.info(f"Jobnet: {len(jobs)} jobs found")
    return jobs


# ── Indeed Israel ───────────────────────────────────────────────────────────────

def scrape_indeed() -> list:
    """Indeed Israel — may block scrapers; handled gracefully."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:3]:
        url = f"https://il.indeed.com/jobs?q={quote_plus(term)}&l=Israel&sort=date"
        resp = _get(url, extra_headers={"Referer": "https://il.indeed.com/"})
        if not resp:
            logger.warning("Indeed: blocked or unavailable, skipping")
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Indeed uses data-jk attribute for job cards
        containers = (
            soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in " ".join(c))
            or soup.find_all("div", attrs={"data-jk": True})
            or soup.find_all("div", class_="cardOutline")
        )

        for item in containers:
            try:
                title_el = (
                    item.find("h2", class_=lambda c: c and "jobTitle" in " ".join(c))
                    or item.find("h2") or item.find("h3")
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = item.find(attrs={"data-testid": "company-name"}) or item.find(class_="companyName")
                location_el = item.find(attrs={"data-testid": "text-location"}) or item.find(class_="companyLocation")
                desc_el = item.find(class_="job-snippet") or item.find("ul")
                link_el = item.find("a", href=True, attrs={"data-jk": True}) or item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                description = desc_el.get_text(strip=True) if desc_el else ""

                href = link_el["href"] if link_el else ""
                link = _abs_url(href, "https://il.indeed.com")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, description, link, "", "Indeed"))
            except Exception as e:
                logger.debug(f"Indeed parse error: {e}")

        _delay()

    logger.info(f"Indeed: {len(jobs)} jobs found")
    return jobs


# ── Glassdoor ───────────────────────────────────────────────────────────────────

def scrape_glassdoor() -> list:
    """Glassdoor Israel — may block scrapers; handled gracefully."""
    jobs = []
    seen_urls: set = set()

    for term in SEARCH_TERMS[:2]:
        url = (
            f"https://www.glassdoor.co.il/Job/israel-"
            f"{quote_plus(term.lower())}-jobs-SRCH_IL.0,6_IN119_KO7,"
            f"{7 + len(term)}.htm?sortBy=date_desc"
        )
        resp = _get(url, extra_headers={"Referer": "https://www.glassdoor.co.il/"})
        if not resp:
            logger.warning("Glassdoor: blocked or unavailable, skipping")
            _delay()
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        containers = (
            soup.find_all("li", class_=lambda c: c and "JobsList_jobListItem" in " ".join(c))
            or soup.find_all("article", class_=lambda c: c and "job" in " ".join(c).lower())
            or soup.find_all("div", attrs={"data-test": "jobListing"})
        )

        for item in containers:
            try:
                title_el = (
                    item.find(attrs={"data-test": "job-title"})
                    or item.find("a", class_=lambda c: c and "jobTitle" in " ".join(c))
                    or item.find("h3")
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 3:
                    continue

                company_el = (
                    item.find(attrs={"data-test": "employer-name"})
                    or item.find(class_=lambda c: c and "employer" in " ".join(c).lower())
                )
                location_el = (
                    item.find(attrs={"data-test": "emp-location"})
                    or item.find(class_=lambda c: c and "location" in " ".join(c).lower())
                )
                link_el = item.find("a", href=True)

                company = company_el.get_text(strip=True) if company_el else ""
                location = location_el.get_text(strip=True) if location_el else ""
                href = link_el["href"] if link_el else ""
                link = _abs_url(href, "https://www.glassdoor.co.il")

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                jobs.append(_job(title, company, location, "", link, "", "Glassdoor"))
            except Exception as e:
                logger.debug(f"Glassdoor parse error: {e}")

        _delay()

    logger.info(f"Glassdoor: {len(jobs)} jobs found")
    return jobs


# ── Entry Point ─────────────────────────────────────────────────────────────────

SCRAPERS = [
    ("AllJobs", scrape_alljobs),
    ("JobMaster", scrape_jobmaster),
    ("Drushim", scrape_drushim),
    ("GotFriends", scrape_gotfriends),
    ("Dialog", scrape_dialog),
    ("Jobs.il", scrape_jobsil),
    ("Jobnet", scrape_jobnet),
    ("Indeed", scrape_indeed),
    ("Glassdoor", scrape_glassdoor),
]


def scrape_all_sites() -> tuple:
    """
    Run all scrapers. Returns (all_jobs: list[dict], error_sites: list[str]).
    Errors are caught per-site so one failure never stops the others.
    """
    all_jobs: list = []
    error_sites: list = []

    for site_name, scraper_fn in SCRAPERS:
        try:
            site_jobs = scraper_fn()
            all_jobs.extend(site_jobs)
        except Exception as e:
            logger.error(f"{site_name} scraper raised: {e}")
            error_sites.append(site_name)

    logger.info(f"Total scraped: {len(all_jobs)} jobs across {len(SCRAPERS) - len(error_sites)} sites")
    return all_jobs, error_sites
