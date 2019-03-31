cp mitsi.edit /lib/systemd/system/mitsi.service
chmod 644 /lib/systemd/system/mitsi.service
systemctl daemon-reload
systemctl enable mitsi.service
service mitsi start
