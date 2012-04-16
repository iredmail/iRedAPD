import sys
import ldap
from libs import SMTP_ACTIONS


class LDAPModeler:
    def __init__(self, cfg, logger):
        self.cfg = cfg

        # Read LDAP server related settings.
        self.uri = self.cfg.get('ldap', 'uri', 'ldap://127.0.0.1:389')
        self.binddn = self.cfg.get('ldap', 'binddn')
        self.bindpw = self.cfg.get('ldap', 'bindpw')
        self.baseDN = self.cfg.get('ldap', 'basedn')
        self.logger = logger

        # Initialize ldap connection.
        try:
            self.conn = ldap.initialize(self.uri)
            self.logger.debug('LDAP connection initialied success.')
        except Exception, e:
            self.logger.error('LDAP initialized failed: %s.' % str(e))
            sys.exit()

        # Bind to ldap server.
        try:
            self.conn.bind_s(self.binddn, self.bindpw)
            self.logger.debug('LDAP bind success.')
        except ldap.INVALID_CREDENTIALS:
            self.logger.error('LDAP bind failed: incorrect bind dn or password.')
            sys.exit()
        except Exception, e:
            self.logger.error('LDAP bind failed: %s.' % str(e))
            sys.exit()

    def __del__(self):
        try:
            self.conn.unbind_s()
            self.logger.debug('Close LDAP connection.')
        except Exception, e:
            self.logger.debug('Error while closing connection: %s' % str(e))

    def __get_recipient_dn_ldif(self, recipient):
        self.logger.debug('__get_recipient_dn_ldif (recipient): %s' % recipient)
        try:
            filter = '(&(|(mail=%s)(shadowAddress=%s))(|(objectClass=mailUser)(objectClass=mailList)(objectClass=mailAlias)))' % (recipient, recipient)
            self.logger.debug('__get_recipient_dn_ldif (ldap query filter): %s' % filter)

            result = self.conn.search_s(self.baseDN, ldap.SCOPE_SUBTREE, filter)

            if len(result) == 1:
                self.logger.debug('__get_recipient_dn_ldif (ldap query result): %s' % str(result))
                dn, entry = result[0]
                return (dn, entry)
            else:
                self.logger.debug('__get_recipient_dn_ldif: Can not find recipient in LDAP server.')
                return (None, None)
        except Exception, e:
            self.logger.debug('!!! ERROR !!! __get_recipient_dn_ldif (result): %s' % str(e))
            return (None, None)

    def __get_access_policy(self, recipient):
        """Get access policy of mail list.

        return (dn_of_mail_list, value_of_access_policy,)"""

        self.logger.debug('__get_access_policy (list): %s' % recipient)

        # Replace 'recipient' placehold in config file with mail list address.
        try:
            self.cfg.set('ldap', "recipient", recipient)
        except Exception, e:
            self.logger.error("""Error while replacing 'recipient': %s""" % (str(e)))

        # Search mail list object.
        searchBasedn = 'mail=%s,ou=Groups,domainName=%s,%s' % (recipient, recipient.split('@')[1], self.baseDN)
        searchScope = ldap.SCOPE_BASE
        searchFilter = self.cfg.get('ldap', 'filter_maillist')
        searchAttr = self.cfg.get('ldap', 'attr_access_policy', 'accessPolicy')

        self.logger.debug('__get_access_policy (searchBasedn): %s' % searchBasedn)
        self.logger.debug('__get_access_policy (searchScope): %s' % searchScope)
        self.logger.debug('__get_access_policy (searchFilter): %s' % searchFilter)
        self.logger.debug('__get_access_policy (searchAttr): %s' % searchAttr)

        try:
            result = self.conn.search_s(searchBasedn, searchScope, searchFilter, [searchAttr])
            self.logger.debug('__get_access_policy (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            self.logger.debug('__get_access_policy (not a mail list: %s) Returned (None)' % recipient)
            return (None, None)
        except Exception, e:
            self.logger.debug('__get_access_policy (ERROR while searching list): %s' % str(e))
            return (None, None)

        if len(result) != 1:
            return (None, None)
        else:
            # Example of result data:
            # [('dn', {'accessPolicy': ['value']})]
            listdn = result[0][0]
            listpolicy = result[0][1][searchAttr][0]
            returnVal = (listdn, listpolicy)

            self.logger.debug('__get_access_policy (returned): %s' % str(returnVal))
            return returnVal

    def __get_allowed_senders(self, listdn, recipient, listpolicy, sender=''):
        """return search_result_list_based_on_access_policy"""
        self.logger.debug('__get_allowed_senders (listpolicy): %s' % listpolicy)

        # Replace 'recipient' and 'sender' with email addresses.
        self.cfg.set("ldap", "recipient", recipient)
        self.cfg.set("ldap", "sender", sender)

        # Set search base dn, scope, filter and attribute list based on access policy.
        if listpolicy == 'membersOnly':
            baseDN = self.baseDN
            searchScope = ldap.SCOPE_SUBTREE
            # Filter used to get domain members.
            searchFilter = self.cfg.get("ldap", "filter_member")
            searchAttr = self.cfg.get("ldap", "attr_member")
        else:
            baseDN = listdn
            searchScope = ldap.SCOPE_BASE   # Use SCOPE_BASE to improve performance.
            # Filter used to get domain moderators.
            searchFilter = self.cfg.get("ldap", "filter_allowed_senders")
            searchAttr = self.cfg.get("ldap", "attr_moderator")

        self.logger.debug('__get_allowed_senders (baseDN): %s' % baseDN)
        self.logger.debug('__get_allowed_senders (searchScope): %s' % searchScope)
        self.logger.debug('__get_allowed_senders (searchFilter): %s' % searchFilter)
        self.logger.debug('__get_allowed_senders (searchAttr): %s' % searchAttr)

        try:
            result = self.conn.search_s(baseDN, searchScope, searchFilter, [searchAttr])
            self.logger.debug('__get_allowed_senders (search result): %s' % str(result))
        except ldap.NO_SUCH_OBJECT:
            self.logger.debug('__get_allowed_senders (not a mail list: %s) Returned (None)' % recipient)
            return None
        except Exception, e:
            self.logger.debug('__get_allowed_senders (ERROR while searching list): %s' % str(e))
            return None

        if len(result) != 1:
            return None
        else:
            # Example of result data:
            # [('dn', {'listAllowedUser': ['user@domain.ltd']})]
            return result[0][1][searchAttr]

    def __get_smtp_action(self, recipient, sender):
        """return smtp_action"""
        listdn, listpolicy = self.__get_access_policy(recipient)

        if listdn is None or listpolicy is None:
            return None
        else:
            if listpolicy == "public":
                # No restriction.
                return SMTP_ACTIONS['accept']
            elif listpolicy == "domain":
                # Allow all users under the same domain.
                if sender.split('@')[1] == recipient.split('@')[1]:
                    return SMTP_ACTIONS['accept']
                else:
                    return SMTP_ACTIONS['reject']
            elif listpolicy == "allowedOnly":
                # Bypass allowed users only.
                allowed_senders = self.__get_allowed_senders(listdn, recipient, 'allowedOnly', sender)

                if allowed_senders is not None:
                    addresses = set(allowed_senders)    # Remove duplicate addresses.
                    if sender in addresses:
                        return SMTP_ACTIONS['accept']
                    else:
                        return SMTP_ACTIONS['reject']
                else:
                    return SMTP_ACTIONS['reject']
            elif listpolicy == "membersOnly":
                allowed_senders = self.__get_allowed_senders(listdn, recipient, 'membersOnly', sender)

                if allowed_senders is not None:
                    addresses = set(allowed_senders)
                    if sender in addresses:
                        return SMTP_ACTIONS['accept']
                    else:
                        return SMTP_ACTIONS['reject']
                else:
                    return SMTP_ACTIONS['reject']

    def handle_data(self, map):
        if 'sender' in map.keys() and 'recipient' in map.keys():
            if len(map['sender']) < 6:
                # Not a valid email address.
                return 'DUNNO'

            # Get plugin module name and convert plugin list to python list type.
            self.plugins = self.cfg.get('ldap', 'plugins', '')
            self.plugins = [v.strip() for v in self.plugins.split(',')]

            if len(self.plugins) > 0:

                # Get account dn and LDIF data.
                recipientDn, recipientLdif = self.__get_recipient_dn_ldif(map['recipient'])

                # Return if recipient account doesn't exist.
                if recipientDn is None or recipientLdif is None:
                    self.logger.debug('Recipient DN or LDIF is None.')
                    return SMTP_ACTIONS['default']

                #
                # Import plugin modules.
                #
                self.modules = []

                # Load plugin module.
                for plugin in self.plugins:
                    try:
                        self.modules.append(__import__(plugin))
                    except ImportError:
                        # Print error message if plugin module doesn't exist.
                        # Use self.logger.info to let admin know this critical error.
                        self.logger.info('Error: plugin %s/%s.py not exist.' % (PLUGIN_DIR, plugin))
                    except Exception, e:
                        self.logger.debug('Error while importing plugin module (%s): %s' % (plugin, str(e)))

                #
                # Apply plugins.
                #
                self.action = ''
                for module in self.modules:
                    try:
                        self.logger.debug('Apply plugin (%s).' % (module.__name__, ))
                        pluginAction = module.restriction(
                            ldapConn=self.conn,
                            ldapBaseDn=self.baseDN,
                            ldapRecipientDn=recipientDn,
                            ldapRecipientLdif=recipientLdif,
                            smtpSessionData=map,
                            logger=self.logger,
                        )

                        self.logger.debug('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                        if not pluginAction.startswith('DUNNO'):
                            self.logger.info('Response from plugin (%s): %s' % (module.__name__, pluginAction))
                            return pluginAction
                    except Exception, e:
                        self.logger.debug('Error while apply plugin (%s): %s' % (module, str(e)))

            else:
                # No plugins available.
                return 'DUNNO'
        else:
            return SMTP_ACTIONS['defer']

