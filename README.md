# ocap_analyzer
## Basic description
- Flask based python web app.
- Downloads a json OCAP replay file, stores it in /cache folder, collects statistic(stores in /cache/results folder also), generates Jinja based web page
- Checked via Python 3.8
- dependencies to install - 'pip install flask requests'

## Installation on VM (simple CentOS example, via root user)
1. copy files to some folder, e.g. /root/ocap_stats/
2. install python and pip, e.g. "yum install python3 python3-pip"
3. install dependencies, e.g. "pip install flask requests"
4. adjust firewall settings in order 80 port to be opened outside ,e.g. 'firewall-cmd --add-port=80/tcp --permanent'
5. create a new file(e.g. "ocap_stats.service") and copy it to /etc/systemd/system/ folder:
```
[Unit]
Description=Ocap statistic

[Service]
User=root
Group=root
WorkingDirectory=/root/ocap_stats
Environment="PATH=/usr/bin"
ExecStart=gunicorn main:app -b 0.0.0.0:80 --log-level=debug --timeout 90 --workers 5
Restart=always

[Install]
WantedBy=multi-user.target
```
6. run "systemctl daemon-reload" to reload 'autorun' service list
7. run "systemctl start ocap_stats" to start application service
8. run "systemctl enable ocap_stats" to add application service in 'autorun' list
9. run "systemctl status ocap_stats -l" to check status and logs
10. try to reach application from a web browser

## Some screenshots

![image](https://user-images.githubusercontent.com/79942827/234730940-b951f9bd-eb84-4ab1-b19a-a4e1e3ad78f1.png)

![image](https://user-images.githubusercontent.com/79942827/234731114-e9dc2151-5bb8-4747-9a3b-6138803914c9.png)

![image](https://user-images.githubusercontent.com/79942827/234731243-ac2779ed-ca8c-4cb6-b06e-3e9dcd614966.png)

![image](https://user-images.githubusercontent.com/79942827/234731308-2207080d-d594-48a2-a6eb-d2a28e21c159.png)
