import unittest

from trustme_api.browser.settings.schema import normalize_settings_data


class SettingsSchemaTest(unittest.TestCase):
    def test_normalize_settings_data_drops_legacy_start_of_day(self):
        normalized, changed = normalize_settings_data(
            {
                "startOfDay": "09:00",
                "startOfWeek": "Sunday",
            }
        )

        self.assertTrue(changed)
        self.assertNotIn("startOfDay", normalized)
        self.assertEqual(normalized["startOfWeek"], "Sunday")


if __name__ == "__main__":
    unittest.main()
