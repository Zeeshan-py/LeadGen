from __future__ import annotations

import unittest

from lead_automation.apify_maps import ApifyMapsClient
from lead_automation.confidence import DiscoveryIdentity, HIGH_CONFIDENCE_THRESHOLD
from lead_automation.contact_discovery import ContactDiscovery
from lead_automation.models import PlaceLead
from lead_automation.social_links import (
    extract_social_links_with_sources,
    select_social_links,
    social_network_for_url,
)
from lead_automation.website_scraper import WebsiteScraper


class FakeRenderedCrawler:
    def crawl(self, url: str) -> dict[str, object]:
        return {
            "text": "Rendered contact content",
            "pages_scraped": 1,
            "html_pages": [
                {
                    "url": url,
                    "html": """
                        <html>
                          <head>
                            <meta property="og:see_also"
                                  content="https://instagram.com/rendered-business">
                            <script type="application/ld+json">
                              {"sameAs": ["https://linkedin.com/company/rendered-business"]}
                            </script>
                          </head>
                          <body>
                            <a href="mailto:hello@rendered.example">Email</a>
                            <footer>
                              <a href="https://facebook.com/rendered-business">Facebook</a>
                            </footer>
                          </body>
                        </html>
                    """,
                }
            ],
        }


class FailedStaticWebsiteScraper(WebsiteScraper):
    def _fetch(self, url: str) -> str | None:
        return None


class CapturingMapsClient(ApifyMapsClient):
    def __init__(self, items: list[dict[str, object]]) -> None:
        super().__init__("test-token", "test/actor")
        self.items = items
        self.run_input: dict[str, object] = {}

    def _run_actor(self, run_input: dict[str, object]) -> list[dict[str, object]]:
        self.run_input = run_input
        return self.items


class EnrichmentTests(unittest.TestCase):
    def test_social_extraction_records_dom_and_structured_sources(self) -> None:
        html = """
            <header><a href="https://facebook.com/acme">Facebook</a></header>
            <meta name="social" content="https://instagram.com/acme">
            <script type="application/ld+json">
              {"sameAs": ["https://linkedin.com/company/acme"]}
            </script>
        """

        result = extract_social_links_with_sources(
            html,
            "https://acme.example/",
            "homepage",
        )

        self.assertEqual(result.links["facebook"], ["https://facebook.com/acme"])
        self.assertIn("homepage:header:href", result.sources["facebook"]["https://facebook.com/acme"])
        self.assertEqual(result.links["instagram"], ["https://instagram.com/acme"])
        self.assertEqual(result.links["linkedin"], ["https://linkedin.com/company/acme"])

    def test_rendered_html_uses_the_same_contact_and_social_parser(self) -> None:
        scraper = FailedStaticWebsiteScraper(js_fallback=FakeRenderedCrawler())

        result = scraper.crawl("https://rendered.example")

        self.assertEqual(result["emails"], ["hello@rendered.example"])
        self.assertEqual(
            result["social_links"]["facebook"],
            ["https://facebook.com/rendered-business"],
        )
        self.assertEqual(
            result["social_links"]["instagram"],
            ["https://instagram.com/rendered-business"],
        )
        self.assertEqual(
            result["social_links"]["linkedin"],
            ["https://linkedin.com/company/rendered-business"],
        )

    def test_social_selection_rejects_generic_and_share_urls(self) -> None:
        selected = select_social_links(
            {
                "facebook": [
                    "https://facebook.com/sharer/sharer.php?u=https://example.com",
                    "https://facebook.com/acme",
                ],
                "instagram": ["https://instagram.com/"],
            }
        )

        self.assertEqual(selected, {"facebook": "https://facebook.com/acme"})

    def test_social_selection_uses_highest_confidence_candidate(self) -> None:
        candidates = {
            "instagram": [
                "https://instagram.com/acme-fan-page",
                "https://instagram.com/acme-dental-dallas",
            ]
        }
        confidence = {
            "instagram": {
                "https://instagram.com/acme-fan-page": 0.66,
                "https://instagram.com/acme-dental-dallas": 0.94,
            }
        }

        selected = select_social_links(
            candidates,
            confidence=confidence,
            min_confidence=HIGH_CONFIDENCE_THRESHOLD,
        )

        self.assertEqual(
            selected,
            {"instagram": "https://instagram.com/acme-dental-dallas"},
        )

    def test_whatsapp_requires_a_real_phone_or_channel_link(self) -> None:
        self.assertEqual(
            social_network_for_url("https://wa.me/12145550199"),
            "whatsapp",
        )
        self.assertEqual(
            social_network_for_url(
                "https://api.whatsapp.com/send?phone=12145550199"
            ),
            "whatsapp",
        )
        self.assertIsNone(social_network_for_url("https://wa.me/"))
        self.assertIsNone(
            social_network_for_url("https://api.whatsapp.com/send")
        )

    def test_search_results_rank_matching_business_and_reject_unrelated_profiles(self) -> None:
        html = """
            <div class="result">
              <a class="result__a" href="https://acmedental.com/contact">Acme Dental contact</a>
              <div class="result__snippet">
                Acme Dental Dallas TX, call (214) 555-0199 or info@acmedental.com
              </div>
            </div>
            <div class="result">
              <a class="result__a" href="https://facebook.com/acme-dental-dallas">Facebook</a>
              <div class="result__snippet">Acme Dental Dallas TX (214) 555-0199</div>
            </div>
            <div class="result">
              <a class="result__a" href="https://facebook.com/other-dental-boston">Facebook</a>
              <div class="result__snippet">Other Dental Boston Massachusetts</div>
            </div>
            <div class="result">
              <a class="result__a" href="https://wa.me/12145550199">WhatsApp</a>
              <div class="result__snippet">Acme Dental Dallas TX WhatsApp (214) 555-0199</div>
            </div>
            <div class="result">
              <a class="result__a" href="https://www.google.com/maps/place/Acme+Dental+Dallas">Maps</a>
              <div class="result__snippet">Acme Dental Dallas TX (214) 555-0199</div>
            </div>
        """
        identity = DiscoveryIdentity(
            business_name="Acme Dental",
            address="100 Main Street",
            city="Dallas",
            state="TX",
            country="United States",
            phone="+12145550199",
        )

        result = ContactDiscovery(max_results=10).parse_search_html(
            html,
            identity=identity,
            query_label="qa",
        )

        self.assertEqual(result.emails, ["info@acmedental.com"])
        self.assertGreaterEqual(
            result.email_confidence["info@acmedental.com"],
            HIGH_CONFIDENCE_THRESHOLD,
        )
        self.assertEqual(
            result.social_links["facebook"],
            ["https://facebook.com/acme-dental-dallas"],
        )
        self.assertEqual(
            result.social_links["whatsapp"],
            ["https://wa.me/12145550199"],
        )
        self.assertEqual(
            result.google_business_links,
            ["https://www.google.com/maps/place/Acme+Dental+Dallas"],
        )

    def test_primary_email_prefers_highest_confidence(self) -> None:
        lead = PlaceLead(
            business_name="Acme Dental",
            raw_emails=["first@example.org", "contact@acmedental.com"],
        )
        lead.record_email_confidence("first@example.org", 0.66)
        lead.record_email_confidence("contact@acmedental.com", 0.97)

        self.assertEqual(lead.primary_email(), "contact@acmedental.com")

    def test_no_website_maps_search_requests_and_parses_web_results(self) -> None:
        client = CapturingMapsClient(
            [
                {
                    "title": "Beehive Salon",
                    "placeId": "beehive-emporia",
                    "address": "1013 W 12th Ave, Emporia, KS 66801",
                    "city": "Emporia",
                    "state": "Kansas",
                    "country": "United States",
                    "phone": "6203421952",
                    "url": "https://www.google.com/maps/place/Beehive+Salon",
                    "website": "",
                    "webResults": [
                        {
                            "title": "Beehive Salon | Emporia KS - Facebook",
                            "url": "https://www.facebook.com/emporiabeehivesalon/",
                            "displayedUrl": "facebook.com/emporiabeehivesalon",
                            "description": (
                                "Beehive Salon in Emporia, Kansas. "
                                "Email hello@emporiabeehive.example."
                            ),
                        }
                    ],
                }
            ]
        )

        leads = client.search_one(
            "Beehive Salon",
            "Emporia, Kansas",
            max_results=1,
            website_filter="withoutWebsite",
        )

        self.assertTrue(client.run_input["scrapePlaceDetailPage"])
        self.assertTrue(client.run_input["includeWebResults"])
        self.assertEqual(leads[0].primary_email(), "hello@emporiabeehive.example")
        self.assertEqual(
            leads[0].social_links["facebook"],
            "https://www.facebook.com/emporiabeehivesalon/",
        )
        self.assertGreaterEqual(
            leads[0].email_confidence["hello@emporiabeehive.example"],
            HIGH_CONFIDENCE_THRESHOLD,
        )
        self.assertGreaterEqual(
            leads[0].social_confidence["facebook"][
                "https://www.facebook.com/emporiabeehivesalon/"
            ],
            HIGH_CONFIDENCE_THRESHOLD,
        )

    def test_maps_parser_reads_plural_social_contact_fields(self) -> None:
        client = CapturingMapsClient(
            [
                {
                    "title": "Acme Dental",
                    "placeId": "acme-dental",
                    "website": "https://acmedental.example",
                    "facebooks": ["https://facebook.com/acme-dental"],
                    "instagrams": ["https://instagram.com/acme-dental"],
                    "linkedIns": ["https://linkedin.com/company/acme-dental"],
                }
            ]
        )

        lead = client.search_one(
            "Acme Dental",
            "Dallas",
            max_results=1,
            website_filter="withWebsite",
        )[0]

        self.assertEqual(
            lead.social_links,
            {
                "facebook": "https://facebook.com/acme-dental",
                "instagram": "https://instagram.com/acme-dental",
                "linkedin": "https://linkedin.com/company/acme-dental",
            },
        )


if __name__ == "__main__":
    unittest.main()
