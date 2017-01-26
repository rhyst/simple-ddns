import requests
import json
import hmac
import hashlib
import subprocess
import re
from auth import SECRET_KEY
from settings import DNS_URL

def generate_signature(data):
        mac = hmac.new(SECRET_KEY, msg=data.encode('utf-8'), digestmod=hashlib.sha1)
        return "sha1=" + mac.hexdigest()

ip = (subprocess.getoutput("echo $(dig +short myip.opendns.com @resolver1.opendns.com)"))
if re.search(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', ip):
	data = json.dumps({"ip": ip})
	sig = generate_signature(data)
	r = requests.post(DNS_URL, data=data, headers={'X-Signature':sig})
