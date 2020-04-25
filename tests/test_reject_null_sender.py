from libs import SMTP_ACTIONS
from tests import utils
from tests import tdata


def test_null_sender():
    d = {
        'sender': '',
        'sasl_username': tdata.user,
        'recipient': 'test' + tdata.user,
    }
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_null_sender']
