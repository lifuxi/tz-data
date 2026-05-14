"""
CFMMC (China Futures Market Monitoring Center) bill scraper.
Uses Playwright to automate login and download daily settlement statements.

Requires: pip install playwright && playwright install chromium
"""
import logging
import os
import time
from datetime import date, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

CFMMC_LOGIN_URL = "https://investors.cfmmc.com/"
CFMMC_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cfmmc_downloads")


class CFMMCScraper:
    """
    Automates CFMMC login and bill download using Playwright.

    Usage:
        scraper = CFMMCScraper()
        scraper.login(username="xxx", password="xxx")
        files = scraper.download_bills(start_date, end_date)
        scraper.close()
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.download_dir = Path(CFMMC_DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_playwright(self):
        """Ensure Playwright is installed and importable."""
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

    def login(self, username: str, password: str) -> bool:
        """
        Login to CFMMC.

        Args:
            username: CFMMC account username
            password: CFMMC account password

        Returns:
            True if login successful
        """
        playwright = self._ensure_playwright()
        pw = playwright()

        try:
            browser = pw.chromium.launch(headless=self.headless)
            self.context = browser.new_context(
                accept_downloads=True,
                viewport={"width": 1280, "height": 800}
            )
            self.page = self.context.new_page()

            # Navigate to login page
            self.page.goto(CFMMC_LOGIN_URL, wait_until="networkidle", timeout=30000)

            # Wait for login form
            self.page.wait_for_selector('input[name="username"]', timeout=10000)

            # Fill credentials
            self.page.fill('input[name="username"]', username)
            self.page.fill('input[name="password"]', password)

            # Submit login form
            self.page.click('button[type="submit"]')
            self.page.wait_for_load_state("networkidle", timeout=30000)

            # Check if login succeeded
            current_url = self.page.url
            if "error" in current_url.lower() or self.page.query_selector(".error"):
                logger.error("CFMMC login failed: invalid credentials")
                self.close()
                return False

            logger.info("CFMMC login successful")
            return True

        except Exception as e:
            logger.error(f"CFMMC login error: {e}")
            self.close()
            return False

    def download_bills(self, start_date: date, end_date: date,
                       output_dir: str = None) -> list[str]:
        """
        Download daily settlement statements for a date range.

        Args:
            start_date: Start date
            end_date: End date
            output_dir: Custom output directory

        Returns:
            List of downloaded file paths
        """
        if not self.page:
            logger.error("Not logged in. Call login() first.")
            return []

        out_dir = Path(output_dir) if output_dir else self.download_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        downloaded = []
        current = start_date

        while current <= end_date:
            if current.weekday() >= 5:  # Skip weekends
                current += timedelta(days=1)
                continue

            try:
                file_path = self._download_single_bill(current, out_dir)
                if file_path:
                    downloaded.append(file_path)
            except Exception as e:
                logger.warning(f"Failed to download bill for {current}: {e}")

            current += timedelta(days=1)

        logger.info(f"Downloaded {len(downloaded)} bills from {start_date} to {end_date}")
        return downloaded

    def _download_single_bill(self, trade_date: date, output_dir: Path) -> Optional[str]:
        """Download a single day's bill statement."""
        date_str = trade_date.strftime('%Y-%m-%d')

        try:
            # Navigate to settlement query page
            self.page.goto(
                f"{CFMMC_LOGIN_URL}/settlement/query",
                wait_until="networkidle",
                timeout=30000
            )

            # Set date filter
            self.page.fill('input[name="settlementDate"]', date_str)

            # Click query button
            self.page.click('button#queryBtn')
            self.page.wait_for_load_state("networkidle", timeout=30000)

            # Check if results exist
            no_data = self.page.query_selector('.no-data')
            if no_data:
                logger.info(f"No settlement data for {date_str}")
                return None

            # Click download button
            with self.page.expect_download(timeout=60000) as download_info:
                self.page.click('button#downloadBtn')

            download = download_info.value
            file_name = f"cfmmc_{date_str}_{download.suggested_filename}"
            file_path = output_dir / file_name
            download.save_as(str(file_path))

            logger.info(f"Downloaded bill for {date_str}: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.warning(f"Download failed for {date_str}: {e}")
            return None

    def close(self):
        """Close browser and clean up resources."""
        if self.context:
            self.context.close()
            self.context = None
        if self.browser:
            self.browser.close()
            self.browser = None

    def __del__(self):
        self.close()


# Task-level wrapper for Celery integration
def scrape_bills_task(username: str, password: str,
                      start_date: date, end_date: date,
                      account_id: int = None) -> dict:
    """
    Wrapper function for Celery task execution.

    Returns:
        Dict with download results
    """
    scraper = CFMMCScraper(headless=True)

    try:
        login_ok = scraper.login(username, password)
        if not login_ok:
            return {
                'success': False,
                'error': 'CFMMC login failed'
            }

        files = scraper.download_bills(start_date, end_date)

        return {
            'success': True,
            'files_downloaded': len(files),
            'files': files,
            'account_id': account_id
        }
    except Exception as e:
        logger.error(f"CFMMC scrape failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        scraper.close()
