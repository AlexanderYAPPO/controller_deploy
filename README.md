All parameters are set via ansible/grop_vars/all file

To deploy a controller node run controller_deploy.yml
To deploy a compute node run compute_deploy.yml
To deploy a node with glance run utils_deploy.yml

Swift deployment just installs Swift and configures it without creating any rings.

StorageArraysTest contains a script for testing scsi devices perfomance with fio and dd.

overlayroot_managing directory contains scripts for changing overlay root modes, see reamde inside.