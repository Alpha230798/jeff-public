from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


class BrowserError(Exception):
    """Raised when Jeff cannot use the dedicated Firefox browser session."""


DEFAULT_PROFILE_PATH = Path.home() / ".jeff" / "firefox_jeff_profile"
FIREFOX_DEVELOPER_EDITION = Path(
    "/Applications/Firefox Developer Edition.app/Contents/MacOS/firefox"
)
MAX_PAGE_TEXT = 12000


@dataclass(frozen=True)
class BrowserPage:
    url: str
    title: str
    text: str


def normalize_web_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise BrowserError("Enter a website address first.")
    if candidate.lower().startswith(("javascript:", "data:", "file:")):
        raise BrowserError("Use a website address that begins with http:// or https://.")
    if "://" not in candidate:
        has_scheme = re.match(r"^[a-z][a-z0-9+.-]*:", candidate, re.IGNORECASE)
        is_host_port = re.match(r"^(?:\[[^]]+\]|[^/:]+):\d+(?:/|$)", candidate)
        if has_scheme and not is_host_port:
            raise BrowserError("Use a website address that begins with http:// or https://.")
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise BrowserError("Use a website address that begins with http:// or https://.")
    try:
        parsed.port
    except ValueError as exc:
        raise BrowserError("Check the port number in that website address.") from exc
    if parsed.username or parsed.password:
        raise BrowserError("Remove any username or password from the website address.")
    return candidate


def find_firefox_binary() -> Path:
    configured = os.environ.get("JEFF_FIREFOX_BINARY")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate
        raise BrowserError("The Firefox path in JEFF_FIREFOX_BINARY does not exist.")
    if FIREFOX_DEVELOPER_EDITION.is_file():
        return FIREFOX_DEVELOPER_EDITION
    executable = shutil.which("firefox")
    if executable:
        return Path(executable)
    raise BrowserError(
        "Firefox was not found. Install Firefox Developer Edition or set JEFF_FIREFOX_BINARY."
    )


class FirefoxBrowser:
    """Controls Jeff's separate Firefox profile; it never opens the daily profile."""

    def __init__(
        self,
        profile_path: str | Path = DEFAULT_PROFILE_PATH,
        *,
        binary_path: str | Path | None = None,
        headless: bool = False,
    ) -> None:
        self.profile_path = Path(profile_path).expanduser()
        self.binary_path = Path(binary_path).expanduser() if binary_path else find_firefox_binary()
        self.headless = headless
        self._driver: webdriver.Firefox | None = None

    @property
    def running(self) -> bool:
        return self._driver is not None

    def start(self) -> None:
        if self.running:
            return
        try:
            self.profile_path.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.profile_path.chmod(0o700)
            options = Options()
            options.binary_location = str(self.binary_path)
            options.add_argument("-profile")
            options.add_argument(str(self.profile_path))
            if self.headless:
                options.add_argument("-headless")
            self._driver = webdriver.Firefox(options=options, service=Service())
        except (OSError, WebDriverException) as exc:
            self._driver = None
            raise BrowserError(
                "Jeff could not start Firefox. Check the installation and try again. "
                "On first use, Selenium may need to download GeckoDriver."
            ) from exc

    def navigate(self, address: str) -> str:
        url = normalize_web_url(address)
        driver = self._require_driver()
        try:
            driver.get(url)
            return driver.current_url
        except WebDriverException as exc:
            raise BrowserError("Firefox could not open that page.") from exc

    def read_current_page(self) -> BrowserPage:
        driver = self._require_driver()
        try:
            body = driver.find_element(By.TAG_NAME, "body").text
            return BrowserPage(
                url=driver.current_url,
                title=driver.title,
                text=body[:MAX_PAGE_TEXT],
            )
        except WebDriverException as exc:
            raise BrowserError("Jeff could not read the current Firefox page.") from exc

    def stop(self) -> None:
        driver, self._driver = self._driver, None
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException as exc:
                raise BrowserError("Firefox did not close cleanly.") from exc

    def _require_driver(self) -> webdriver.Firefox:
        if self._driver is None:
            raise BrowserError("Start Jeff's Firefox browser before using it.")
        return self._driver
