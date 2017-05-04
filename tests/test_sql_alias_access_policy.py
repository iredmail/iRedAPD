from libs import SMTP_ACTIONS
from libs import MAILLIST_POLICY_PUBLIC
from libs import MAILLIST_POLICY_DOMAIN
from libs import MAILLIST_POLICY_SUBDOMAIN
from libs import MAILLIST_POLICY_MEMBERSONLY
from libs import MAILLIST_POLICY_MODERATORS
from libs import MAILLIST_POLICY_MEMBERSANDMODERATORSONLY

from tests import utils
from tests import tdata

def test_policy_public():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_PUBLIC)

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.alias
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['default']

def test_policy_domain():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_DOMAIN)

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.alias
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

def test_policy_subdomain():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_SUBDOMAIN)

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.alias
    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

def test_policy_membersonly_as_ext_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MEMBERSONLY)

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

    utils.assign_alias_member(member=tdata.ext_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

def test_policy_membersonly_as_internal_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MEMBERSONLY)

    d = {}
    d['sender'] = tdata.user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

    utils.assign_alias_member()
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

def test_policy_moderators_as_ext_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MODERATORS)

    d = {}
    d['sender'] = tdata.ext_user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

    utils.assign_alias_moderator(moderator=tdata.ext_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

def test_policy_moderators_as_internal_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MODERATORS)

    d = {}
    d['sender'] = tdata.user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    assert action == SMTP_ACTIONS['reject_not_authorized']

    utils.assign_alias_moderator(moderator=tdata.user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

def test_policy_membersandmoderators_as_ext_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MEMBERSANDMODERATORSONLY)

    _user = tdata.ext_user
    d = {}
    d['sender'] = _user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    # Not member or moderator
    assert action == SMTP_ACTIONS['reject_not_authorized']

    # is member
    utils.assign_alias_member(member=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

    # Not member or moderator
    utils.remove_alias_member(member=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['reject_not_authorized']

    # is moderator
    utils.assign_alias_moderator(moderator=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

    # Not member or moderator
    utils.remove_alias_moderator(moderator=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['reject_not_authorized']

def test_policy_membersandmoderators_as_internal_user():
    utils.add_domain()
    utils.add_user()
    utils.add_alias(policy=MAILLIST_POLICY_MEMBERSANDMODERATORSONLY)

    _user = tdata.user
    d = {}
    d['sender'] = _user
    d['recipient'] = tdata.alias

    s = utils.set_smtp_session(**d)
    action = utils.send_policy(s)

    # Not member or moderator
    assert action == SMTP_ACTIONS['reject_not_authorized']

    # is member
    utils.assign_alias_member(member=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

    # Not member or moderator
    utils.remove_alias_member(member=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['reject_not_authorized']

    # is moderator
    utils.assign_alias_moderator(moderator=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['default']

    # Not member or moderator
    utils.remove_alias_moderator(moderator=_user)
    action = utils.send_policy(s)
    assert action == SMTP_ACTIONS['reject_not_authorized']
