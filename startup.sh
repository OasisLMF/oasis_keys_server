#!/bin/bash
APACHE_UID=$(id -g www-data)
chown -R $APACHE_UID /var/oasis/keys_data/

apache2ctl start 
tail -f /var/log/oasis/keys_server.log
