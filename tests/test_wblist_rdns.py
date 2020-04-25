from libs import SMTP_ACTIONS
from tests import utils
from tests import tdata


def test_whitelist_exact_match():
    utils.add_domain()
    utils.add_user()

    rdns = tdata.rdns_exact_name
    utils.add_wblist_rdns_whitelist(rdns=rdns)

    d = {
        'sender': tdata.ext_user,
        'recipient': tdata.user,
        'reverse_client_name': rdns,
    }

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['default']

    utils.remove_wblist_rdns_whitelist(rdns=rdns)


def test_whitelist_subdomain_match():
    utils.add_domain()
    utils.add_user()

    rdns = tdata.rdns_subdomain_name
    utils.add_wblist_rdns_whitelist(rdns=rdns)

    d = {
        'sender': tdata.ext_user,
        'recipient': tdata.user,
        'reverse_client_name': rdns,
    }
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['default']

    utils.remove_wblist_rdns_whitelist(rdns=rdns)


def test_blacklist_exact_match():
    utils.add_domain()
    utils.add_user()

    rdns = tdata.rdns_exact_name
    utils.add_wblist_rdns_blacklist(rdns=rdns)

    d = {
        'sender': tdata.ext_user,
        'recipient': tdata.user,
        'reverse_client_name': rdns,
    }

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_blacklisted_rdns'] + ' (' + rdns + ')'

    utils.remove_wblist_rdns_blacklist(rdns=rdns)


def test_blacklist_subdomain_match():
    utils.add_domain()
    utils.add_user()

    rdns = tdata.rdns_subdomain_name
    utils.add_wblist_rdns_blacklist(rdns=rdns)

    d = {
        'sender': tdata.ext_user,
        'recipient': tdata.user,
        'reverse_client_name': rdns,
    }

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_blacklisted_rdns'] + ' (' + rdns + ')'

    utils.remove_wblist_rdns_blacklist(rdns=rdns)
