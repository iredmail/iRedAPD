import socket

policy_data = """request=smtpd_access_policy
protocol_state=RCPT
protocol_name=SMTP
helo_name=some.domain.tld
queue_id=8045F2AB23
sender=POSTmaster@gmail.com
recipient=postmaster@a.io
recipient_count=0
client_address=2a00:1450:4864:20::32a
client_name=mail-wm1-x32a.google.com
reverse_client_name=mail-wm1-x32a.google.com
instance=123.456.7
sasl_method=
sasl_username=
sasl_sender=
size=123
ccert_subject=
ccert_issuer=
ccert_fingerprint=
encryption_protocol=
encryption_cipher=
encryption_keysize=
etrn_domain=
stress=
ccert_pubkey_fingerprint=

"""

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 7777))
s.sendall(policy_data)
data = s.recv(1024)
print data
s.close()
