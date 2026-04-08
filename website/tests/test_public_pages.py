from django.test import TestCase


class LandingPageTests(TestCase):
    def test_root_landing_page_renders_key_sections(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI-Powered Football Training &amp; Performance Platform")
        self.assertContains(response, "Get Started")
        self.assertContains(response, "Request Demo")
        self.assertContains(response, "Who it&rsquo;s for")
        self.assertContains(response, "How it works")
        self.assertContains(response, "Admin Coach Requests Panel")
