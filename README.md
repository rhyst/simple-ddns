# simple-ddns

simple-ddns is a little flask application that can be run on a VPS to keep track of something elses IP address (a home network for example). The flask app provides a `get` method to view the ip and a `post` method to set the ip. It can edit an nginx configuration to redirect a subdomain or url to the ip. An included python script can be used on the client (via cron job or manually) to update the flask app.

This will walk through setting it up with an nginx server.

## Set Up

### Flask Server

Install `python3`, `virtualenv`, `rabbitmq`.

We use Flask as the http api framework for our app. Because we want it to respond to http requests quickly we run the bulk of the logic in a Celery task. Celery is asynchronous task queue so we can add our task there and the flask app can carry on to respond to the http request. Celery needs a broker, a place for the flask app to queue its tasks and celery to read from. We use rabbitmq because its the default supported by celery and you literally just have to install it and it will work.

```
git clone https://gitlab.com/rhyst/simple-ddns
cd simple-ddns
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
```

Generate secure random hex string. Github recommends:

```
ruby -rsecurerandom -e 'puts SecureRandom.hex(20)'  
```

Create a file, `auth.py`

```
SECRET_KEY=b'securerandomhexstring'
```

Create a file `settings.py`

```
NGINX_CONF_NAME="ddns-example.com.conf"
APP_ROUTE="/dns/"
```

You can now test it by running `wsgi.py` but it will run on localhost, in this case `localhost/dns/`. You can use a tool like httpie to test `post`-ing to it.

```
http --json PUT localhost/dns/ ip=192.168.1.1
```

To set it up with nginx read on. In your nginx site conf file:

```
location = /dns {
        rewrite ^ /dns/;
}
location /dns/ {
        try_files $uri @dns;
}
location @dns {
        include uwsgi_params;
        uwsgi_pass unix:/path/to/simpleddns/dns.sock;
}

```

The `APP_ROUTE` setting should match whatver url you use in the nginx conf. You can then run:

```
sudo nginx -t
```

To test the config. And if it works:

```
sudo nginx -s reload
```

You probably want to run these as systemd services so they start on boot and restart themselves. Create two files in `/etc/systemd/system/`:

`dns.service`

```
[Unit]
Description=uWSGI instance to serve dns project
After=network.target

[Service]
User=your-user
Group=www-data
WorkingDirectory=/path/to/simple-ddns/
Environment="PATH=/path/to/simple-ddns/venv/bin"
ExecStart=/path/to/simple-ddns/venv/bin/uwsgi --ini wsgi.ini

[Install]
WantedBy=multi-user.target
```

`dns_celery.service`

```
[Unit]
Description=Celery instance to serve deploy dns
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/simple-ddns/
Environment="PATH=/path/to/simple-ddns/venv/bin"
ExecStart=/path/to/simple-ddns/dns/venv/bin/celery worker -A dns.celery -f /path/to/simple-ddns/log-celery.log --concurrency=1 -n dnsWorker  -Q dns

[Install]
WantedBy=multi-user.target
```

Ensuring that you replace the user name and the paths. Then:

```
sudo systemctl enable dns.service
sudo systemctl enable dns_celery.service
sudo systemctl start dns.service
sudo systemctl start dns_celery.service
```

To set up the subdomain redirect you will need to add something like this to your nginx config:

```
server_name subdomain.example.com;

root /var/www/example.com;

location / {
	include /path/to/simple-dddns/nginx/ddns-example.com.conf;
}

```

The name of the conf file should match the `NGINX_CONF_NAME` in `settings.py`.

Because we need to be able to restart nginx we will add some commands to our sudoers file so that flask won't need to authenticate.

```
su
visudo /etc/sudoers.d/your_user
```

Always use visudo to edit this file. Then add

```
your_user ALL=(ALL) NOPASSWD: /usr/sbin/service nginx start,/usr/sbin/service nginx stop,/usr/sbin/service nginx restart,/usr/sbin/nginx -t,/usr/sbin/nginx -s reload
```

And then because nginx will want to read the conf file thats generated in the `nginx` folder we need to add ourselves to the `www-data` group:

```
usermod -a -G www-data your-user
```

That should all work now.

### Client

Install `python3`, `virtualenv`, `dnsutils`.

```
git clone https://gitlab.com/rhyst/simple-ddns/
cd simple-ddns/client
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.client.txt
```

You'll need to make two files. `settings.py`:

```
DNS_URL="url to your flask app"
```

And `auth.py`:

```
SECRET_KEY=b'somehexstringsharedwiththeflaskapp'
```

Then to run:

```
./venv/bin/python3 dns_client_script.py 
```

To automate it:

```
crontab -e
```

Then append

```
30 * * * * /path/to/simple-ddns/client/venv/bin/python3 /path/to/simple-ddns/client/dns_client_script.py 
```

