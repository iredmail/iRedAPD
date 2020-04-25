from tests import utils


def test_cleanup():
    # Remove all sql records generated during testing.
    utils.delete_alias_domain()
    utils.delete_domain()
    utils.delete_user()
    utils.delete_alias()
