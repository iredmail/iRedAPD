from tests import utils

def test_cleanup():
    # Test forged sender
    utils.delete_domain()
    utils.delete_user()
