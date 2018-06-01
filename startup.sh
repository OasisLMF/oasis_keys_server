#!/bin/bash

apache2ctl start 
tail -f /var/log/oasis/keys_server.log
