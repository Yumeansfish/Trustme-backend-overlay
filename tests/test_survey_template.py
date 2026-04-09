import unittest

from trustme_api.browser.surveys.questionnaire import (
    FIXED_SURVEY_TEMPLATE_ID as legacy_template_id,
    load_fixed_survey_template as legacy_load_fixed_survey_template,
)
from trustme_api.browser.surveys.survey_template import (
    FIXED_SURVEY_TEMPLATE_ID,
    load_fixed_survey_template,
)


class SurveyTemplateShimTest(unittest.TestCase):
    def test_questionnaire_shim_reexports_survey_template(self):
        self.assertEqual(legacy_template_id, FIXED_SURVEY_TEMPLATE_ID)
        self.assertIs(legacy_load_fixed_survey_template, load_fixed_survey_template)


if __name__ == "__main__":
    unittest.main()
