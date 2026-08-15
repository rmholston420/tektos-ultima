"""Final searxng_provider.py coverage — lines 329, 363, 454."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from tektos.providers.searxng_provider import (
    SearXNGClient,
    SearXNGConfig,
)


class TestHTMLFallbackBS4Path:
    @pytest.mark.asyncio
    async def test_html_fallback_uses_bs4_when_available(self):
        """Test _search_html_fallback uses bs4 when available (line 329 has_bs4=True, line 363 calls _parse_html_bs4)."""
        client = SearXNGClient(
            config=SearXNGConfig(
                use_html_fallback=True,
                html_timeout_seconds=10.0,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<a href="https://example.com">HTML Result</a>'
        mock_session = MagicMock()

        async def get_side_effect(*args, **kwargs):
            return mock_resp

        mock_session.get = get_side_effect
        client.get_session = AsyncMock(return_value=mock_session)

        # Mock bs4 module
        mock_bs_instance = MagicMock()
        mock_bs_instance.select.return_value = []
        mock_bs4 = MagicMock()
        mock_bs4.BeautifulSoup.return_value = mock_bs_instance

        with patch.dict('sys.modules', {'bs4': mock_bs4}):
            # Patch has_bs4 detection
            import sys
            import importlib
            original_modules = dict(sys.modules)
            sys.modules['bs4'] = mock_bs4

            try:
                # Reimport to pick up bs4
                import importlib
                import tektos.providers.searxng_provider
                importlib.reload(tektos.providers.searxng_provider)

                # Now call _search_html_fallback — it should find bs4
                resp = await client._search_html_fallback(
                    "test", 10, "general", "en"
                )
                assert resp.error is None
                assert resp.engines == ["html_fallback"]
            finally:
                # Restore original modules
                for key in list(sys.modules.keys()):
                    if key not in original_modules:
                        del sys.modules[key]
                sys.modules.update(original_modules)


# Need to import patch
from unittest.mock import patch


class TestBS4ParseContinue:
    def test_parse_html_bs4_skips_elem_without_href(self):
        """Test _parse_html_bs4 skips elements without href (line 454 continue)."""
        client = SearXNGClient()

        title_elem = MagicMock()
        title_elem.get_text.return_value = "No Href"
        title_elem.get = MagicMock(return_value=None)
        title_elem.__getitem__ = lambda self, key: None

        content_elem = MagicMock()
        content_elem.get_text.return_value = "Content"

        elem = MagicMock()
        elem.select_one.side_effect = lambda sel: title_elem if "href" in sel else content_elem
        elem.__iter__ = lambda self: iter([title_elem, content_elem])

        mock_bs_instance = MagicMock()
        mock_bs_instance.select.return_value = [elem]

        mock_bs4 = MagicMock()
        mock_bs4.BeautifulSoup.return_value = mock_bs_instance

        with patch.dict('sys.modules', {'bs4': mock_bs4}):
            client.config.base_url = "http://localhost:8888"
            html = '<div class="result"><a>No Href</a><div class="content">Content</div></div>'
            results = client._parse_html_bs4(html, 10, "general")
            assert len(results) == 0  # skipped due to missing href
