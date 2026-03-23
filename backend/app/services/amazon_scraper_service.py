"""
Amazon Product Scraper Service

Scrapes product pages from Amazon (amazon.com only) to extract product info
for HTS classification. Used when NECO needs supplemental evidence per line item.

Note: Amazon may block scrapers. Use sparingly. For production, consider
Amazon Product Advertising API or a proxy service.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Allowed Amazon domains (amazon.com only for now)
ALLOWED_DOMAINS = {"www.amazon.com", "amazon.com", "smile.amazon.com"}

# Browser-like headers to reduce block risk
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def is_valid_amazon_url(url: str) -> bool:
    """Check if URL is a valid Amazon product URL we allow."""
    if not url or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
        domain = parsed.netloc.lower().replace("www.", "") if parsed.netloc else ""
        if domain not in ("amazon.com",):
            return False
        # Must have /dp/ or /gp/product/ for product pages
        path = (parsed.path or "").lower()
        return "/dp/" in path or "/gp/product/" in path
    except Exception:
        return False


def scrape_amazon_product(url: str, timeout: int = 15) -> dict:
    """
    Scrape an Amazon product page and return structured product data.

    Args:
        url: Full Amazon product URL (e.g. https://www.amazon.com/dp/B08N5WRWNW)
        timeout: Request timeout in seconds

    Returns:
        Dict with keys: title, description, features, product_details, full_text, error
        On success: full_text is a single string suitable for classification context.
        On error: error is set, other fields may be partial.
    """
    result = {
        "title": None,
        "description": None,
        "features": [],
        "product_details": {},
        "full_text": "",
        "error": None,
    }

    if not is_valid_amazon_url(url):
        result["error"] = "Invalid or unsupported URL. Only Amazon.com product pages are allowed (e.g. https://www.amazon.com/dp/...)."
        return result

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()

        # Check for captcha/block
        if "captcha" in resp.text.lower() or "robot" in resp.text.lower():
            if "enter the characters you see below" in resp.text.lower():
                result["error"] = "Amazon is requesting verification. Please try again later or provide a PDF data sheet instead."
                return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Product title
        title_el = soup.find("span", id="productTitle")
        if title_el:
            result["title"] = title_el.get_text(strip=True)

        # Feature bullets
        feat_ul = soup.find("div", id="feature-bullets")
        if feat_ul:
            for li in feat_ul.find_all("li", class_=lambda c: c and "a-spacing-none" not in (c or "")):
                text = li.get_text(strip=True)
                if text and len(text) > 2:
                    result["features"].append(text)

        # Product description (from various possible locations)
        desc_div = soup.find("div", id="productDescription")
        if desc_div:
            result["description"] = desc_div.get_text(strip=True)

        if not result["description"]:
            # Try a-expander-content
            for div in soup.find_all("div", class_=lambda c: c and "a-expander-content" in (c or "")):
                text = div.get_text(strip=True)
                if text and len(text) > 50:
                    result["description"] = text
                    break

        # Product details table (e.g. ASIN, Item Weight)
        table = soup.find("table", id="productDetails_techSpec_section_1")
        if not table:
            table = soup.find("table", id="productDetails_detailBullets_sections1")
        if table:
            for row in table.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    key = th.get_text(strip=True).rstrip(":")
                    val = td.get_text(strip=True)
                    if key and val:
                        result["product_details"][key] = val

        # Build full_text for classification
        parts = []
        if result["title"]:
            parts.append(f"Product: {result['title']}")
        if result["features"]:
            parts.append("Features: " + "; ".join(result["features"]))
        if result["description"]:
            parts.append("Description: " + result["description"])
        if result["product_details"]:
            details_str = "; ".join(f"{k}: {v}" for k, v in result["product_details"].items())
            parts.append("Specifications: " + details_str)

        result["full_text"] = "\n\n".join(parts) if parts else ""

        if not result["full_text"]:
            result["error"] = "Could not extract product information from this page. The page structure may have changed or the product may be unavailable."

    except requests.exceptions.Timeout:
        result["error"] = "Request timed out. Amazon may be slow or blocking the request."
    except requests.exceptions.RequestException as e:
        result["error"] = f"Could not fetch page: {str(e)[:200]}"
    except Exception as e:
        logger.exception("Amazon scrape failed")
        result["error"] = f"Scraping failed: {str(e)[:200]}"

    return result
