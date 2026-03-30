import unittest

from trustme_api.browser.surveys.questionnaire import (
    FIXED_SURVEY_TEMPLATE_ID,
    load_fixed_survey_template,
)


class FixedSurveyQuestionnaireTest(unittest.TestCase):
    def test_load_fixed_survey_template_returns_stable_ids(self):
        manifest = load_fixed_survey_template()

        self.assertEqual(manifest["survey_template_id"], FIXED_SURVEY_TEMPLATE_ID)
        self.assertEqual(len(manifest["global_questions"]), 1)
        self.assertEqual(len(manifest["video_questions"]), 9)
        self.assertEqual(len(manifest["questions"]), 9)

        first_global_question = manifest["global_questions"][0]
        self.assertEqual(first_global_question["id"], "gq1")
        self.assertEqual(first_global_question["options"][0]["id"], "gq1_o1")

        first_question = manifest["video_questions"][0]
        self.assertEqual(first_question["id"], "q1")
        self.assertEqual(first_question["type"], "single_choice")
        self.assertTrue(first_question["required"])
        self.assertEqual(first_question["options"][0]["id"], "q1_o1")
        self.assertEqual(first_question["options"][-1]["id"], "q1_o7")

    def test_question_orders_and_option_orders_are_sequential(self):
        manifest = load_fixed_survey_template()

        for question_index, question in enumerate(manifest["global_questions"], start=1):
            self.assertEqual(question["order"], question_index)
            self.assertGreater(len(question["options"]), 0)
            for option_index, option in enumerate(question["options"], start=1):
                self.assertEqual(option["order"], option_index)

        for question_index, question in enumerate(manifest["video_questions"], start=1):
            self.assertEqual(question["order"], question_index)
            self.assertGreater(len(question["options"]), 0)
            for option_index, option in enumerate(question["options"], start=1):
                self.assertEqual(option["order"], option_index)


if __name__ == "__main__":
    unittest.main()
