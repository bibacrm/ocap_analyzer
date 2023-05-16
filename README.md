# ocap_analyzer
## Basic description
- Flask based python web app.
- Downloads a json OCAP replay file, stores it in /cache folder, collects statistic(stores in /cache/results , /cache/missions, /cache/total_stats folder), generates Jinja based web pages
- Provides statistic for specific mission, brief statistic for all missions in one table, statistic per arma account, statistic per steam_account, attendance statistic, total statistic per project
- Checked via Python 3.8
- dependencies to install - "pip install -r requirements.txt" (flask requests apscheduler tqdm)
- description of configuration parameters is available in config.py file
- bulk download of replays with required statistic generation can be triggered via 'bulk_processing.py' script

## Installation on VM (simple CentOS example, via root user)
1. copy files to some folder, e.g. /root/ocap_stats/
2. install python and pip, e.g. "yum install python3 python3-pip"
3. install dependencies, e.g. "pip install -r requirements.txt"
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
ExecStart=gunicorn main:app -b 0.0.0.0:80 --log-level=debug --timeout 90 --workers 5 --preload
Restart=always

[Install]
WantedBy=multi-user.target
```
- 0.0.0.0 - si network sharing configuration to be available for anyone
- :80 - port
- timeout 90 - timeout application will keep connection opened, e.g. time for web page to be opened/downloaded
- workers - usually calculated as (CPU_amount*2)+1, so '5' is for VM with 2 CPUs, '9' will be for VM with 4 CPUs
- preload - is required to orchestrate process scheduler correctly only on first application load.

6. run "systemctl daemon-reload" to reload 'autorun' service list
7. run "systemctl start ocap_stats" to start application service
8. run "systemctl enable ocap_stats" to add application service in 'autorun' list
9. run "systemctl status ocap_stats -l" to check status and logs
10. try to reach application from a web browser

## Some screenshots

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/958c484b-fb49-47f6-9020-9fcbd95e357a)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/3e9cab40-efcb-4e72-86a4-55ade54b0da6)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/7b00b991-4e2e-41cc-9250-5441136ac824)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/23d42ca7-8d34-434b-9723-33e8a420546b)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/35f0e3a5-fd74-4360-9e27-99195797761b)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/852df1b0-2c14-4674-a00c-e3e76ab30926)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/51a3e8c1-1855-45f8-9aef-0239656e4067)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/a859eda5-f6ad-4ac1-ab82-7b4607fd4b7f)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/223e8a15-3501-4a53-b5f0-0da3610efa6e)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/36d8d403-aacc-49ed-b360-de08b91b5e8b)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/5ca92a35-6e0d-43d6-9754-ec06d100d8cd)

![image](https://github.com/bibacrm/ocap_analyzer/assets/79942827/4d7956b8-897d-49ce-a39c-4d6cdfe8f686)

