[Service]
Environment="UI_PASSWORD=changeme"
Environment="SSH_USERNAME=your_ssh_user"
Environment="SSH_PASSWORD=your_ssh_pass"
ExecStart=/usr/bin/python3 /path/to/rag_api.py


#reload restart
sudo systemctl daemon-reexec
sudo systemctl restart your-service-name