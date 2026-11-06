"""Adult-only fixed-response tests; no real learners, voice or AI."""
import unittest

from prototype.lesson_engine import PolicyError
from prototype.synthetic_companion import SyntheticCompanionDemo, SyntheticFixtureCompanionProvider


class SyntheticCompanionTests(unittest.TestCase):
    def test_disabled_by_default_and_only_explicit_boolean_enables(self):
        with self.assertRaises(PolicyError):
            SyntheticCompanionDemo().reply('hello')
        for flag in (1, 'true', None):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                SyntheticCompanionDemo(flag)
        self.assertEqual(SyntheticCompanionDemo(True).reply('hello'), {
            'text': 'Hello! I am here with you for this activity.',
            'mode': 'scripted_synthetic_fixture',
        })

    def test_allowlisted_actions_are_static_and_never_echo_user_input(self):
        demo = SyntheticCompanionDemo(True)
        for action in ('hello', 'encourage', 'break'):
            self.assertEqual(demo.reply(action), demo.reply(action))
        for value in ('real personal information', '', 'HELLO', None, 1, [], {}):
            with self.subTest(value=value), self.assertRaises(PolicyError):
                demo.reply(value)

    def test_provider_exposes_no_mutable_scripts(self):
        provider = SyntheticFixtureCompanionProvider()
        self.assertEqual(provider.reply('break'),
                         'It is okay to take a break and come back when you are ready.')
        self.assertEqual(vars(provider), {})


if __name__ == '__main__':
    unittest.main()
