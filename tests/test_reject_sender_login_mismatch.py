from libs import SMTP_ACTIONS
import settings
from tests import utils
from tests import tdata

def test_forged_sender():
    # Test forged sender
    utils.add_domain()
    utils.add_user()

    d = {}
    d['sender'] = tdata.user
    d['recipient'] = 'test' + tdata.user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_forged_sender']

def test_not_local_sender():
    # Test not local sender. Greylisting should be applied.
    utils.add_domain()
    utils.add_user()

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['greylisting'] + ' ' + settings.GREYLISTING_MESSAGE

def test_sender_same_as_sasl_username():
    # Test outbound: sender == sasl_username
    utils.add_domain()
    utils.add_user()

    d = {}
    d['sender'] = tdata.user
    d['sasl_username'] = tdata.user
    d['recipient'] = tdata.ext_user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == 'DUNNO'

def test_sender_not_same_as_sasl_username_1():
    # Test outbound: sender != sasl_username
    utils.add_domain()
    utils.add_user()

    d = {}
    d['sender'] = tdata.user_alias
    d['sasl_username'] = tdata.user
    d['recipient'] = tdata.ext_user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_sender_login_mismatch']

def test_sender_not_same_as_sasl_username_2():
    # Test outbound: (sender != sasl_username) & (sender is alias address of sasl username)
    utils.add_domain()
    utils.add_user()
    utils.add_per_user_alias_address()

    d = {}
    d['sender'] = tdata.user_alias
    d['sasl_username'] = tdata.user
    d['recipient'] = tdata.ext_user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == 'DUNNO'

def test_send_as_user_alias():
    # Test outbound:
    #   - sender != sasl_username
    #   - sender is alias address of sasl username
    utils.add_domain()
    utils.add_alias_domain()
    utils.add_user()
    utils.add_per_user_alias_address()

    d = {}
    d['sender'] = tdata.user_alias
    d['sasl_username'] = tdata.user
    d['recipient'] = tdata.ext_user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == 'DUNNO'

def test_send_as_user_under_alias_domain():
    # Test outbound:
    #   - sender != sasl_username
    #   - sender is alias address of sasl username
    utils.add_domain()
    utils.add_alias_domain()
    utils.add_user()

    d = {}
    d['sender'] = tdata.user_in_alias_domain
    d['sasl_username'] = tdata.user
    d['recipient'] = tdata.ext_user
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == 'DUNNO'

if settings.backend != 'ldap':
    def test_send_as_alias_member():
        # Test outbound:
        # - sender != sasl_username
        # - sender is member of mail alias account
        utils.add_domain()
        utils.add_alias_domain()
        utils.add_user()
        utils.add_alias()
        utils.assign_user_as_alias_member()

        d = {}
        d['sender'] = tdata.alias
        d['sasl_username'] = tdata.user
        d['recipient'] = tdata.ext_user
        s = utils.set_smtp_session(**d)
        action = utils.send_policy(s)

        assert action == 'DUNNO'
