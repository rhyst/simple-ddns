from flask import Flask, request
from celery import Celery
import json
import hmac
import hashlib
import os
import logging
import datetime
import pexpect
import sys
import smtplib
import subprocess
from auth import SECRET_KEY
from settings import NGINX_CONF_NAME, APP_ROUTE

brokerurl = 'amqp://'

app = Flask(__name__)
celery = Celery(app.name, broker=brokerurl)
ip = ""

@app.route(APP_ROUTE,methods=['GET', 'POST'])
def dns():
	logging.basicConfig(filename='log.log',level=logging.INFO, filemode='a+')

	global ip
	if request.method == "GET":
		return(ip)

	if not _validate_signature(request.get_data()):
		logging.info('{}: Validation failed'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))
		return("500")

	logging.info('{}: DNS update recieved'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))
	logging.info('{}: DNS update recieved'.format(app.name))

	str_response = request.data.decode('utf-8')
	data = json.loads(str_response)

	try:
		ip = data["ip"]
	except KeyError:
		return("422")

	logging.info('{}: {}'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S"), data))
	do_dns.delay(ip)
	return("OK")


@celery.task(bind=True, queue="dns")
def do_dns(self, ip):
	print('{}: Writing file'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))
	conf_path = os.path.join(os.getcwd(), "nginx")
	if not os.path.exists(conf_path):
    		os.makedirs(conf_path)
	conf_path = os.path.join(conf_path, NGINX_CONF_NAME)
	if os.path.isfile(conf_path):
		os.remove(conf_path)
	with open(conf_path, "w+") as f:
		f.write("proxy_pass https://{};".format(ip))
	stdoutdata = subprocess.getoutput("/usr/bin/sudo nginx -t")
	if stdoutdata.splitlines()[0] == "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok" and stdoutdata.splitlines()[1] == "nginx: configuration file /etc/nginx/nginx.conf test is successful":
		print('{}: Valid, restarting nginx'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))
		stdoutdata = subprocess.getoutput("/usr/bin/sudo nginx -s reload")
		if stdoutdata == "":
			print('{}: nginx succesfully restarted'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))
		else:
			print('{}: {}'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S"), stdoutdata))
	else:
		print('{}: nginx config not valid'.format(datetime.datetime.now().strftime("%Y%m%d:%I:%M:%S")))


def _validate_signature(data):
	sha_name, signature = request.headers['X-Signature'].split('=')
	# HMAC requires its key to be bytes, but data is strings.
	mac = hmac.new(SECRET_KEY, msg=data, digestmod=hashlib.sha1)
	return hmac.compare_digest(mac.hexdigest(), signature)

if __name__ == "__main__":
	app.run(host='0.0.0.0')
