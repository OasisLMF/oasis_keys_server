#!/bin/bash
APACHE_UID=$(id -g www-data)
chown -R $APACHE_UID /var/oasis/keys_data/

mkdir -p /var/log/oasis 
touch /var/log/oasis/keys_server.log
chown -R www-data:www-data /var/log/oasis

apache2ctl start 
tail -f /var/log/oasis/keys_server.log
