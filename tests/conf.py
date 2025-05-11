from os import getenv

FAKTUROID_SLUG = getenv("FAKTUROID_SLUG")
FAKTUROID_CLIENT_ID = getenv("FAKTUROID_CLIENT_ID")
FAKTUROID_CLIENT_SECRET = getenv("FAKTUROID_CLIENT_SECRET")

TESTS_USER_AGENT = (
    "python-fakturoid-v3-tests (https://github.com/jarovo/python-fakturoid-v3)"
)
TESTS_OBJECTS_NAME_PREFIX = "python-fakturoid-v3-test"
