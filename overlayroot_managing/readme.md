## Scripts for managing overlayroot

We assume that the host has access to three partitions -- "current", "testing" and "stable".
First two supposed to be overlayfs'ed on the last one. The "stable" partition, which acts as a lower layer in
overlayfs, is always read-only in normal conditions. It can be changed only by these scripts for two purposes:
alter overlayroot configuration or copy all files from "testing" to "stable".

The host can be in three states (modes) -- "current", "testing" and "off". In first two "/" mountpoint is overlayfs with
"stable" as a read-only lowerdir and "current" or "testing" as an upperdir. In "off", no overlayfs is mounted to the root,
it is a usual boot from the "stable" partition.

So, the typical workflow should be as follows.
Firstly we install the OS image into "stable" partition and enter the "current" state. Here we develop it (installing packages,
configuring apps, etc) until we find it appropriate for use. Then we copy "current" partition to "testing" and enter
the "testing" state. Here we continue working and still can make fixes and improvements. Finally, when we are 100%
sure that the image is production-ready, we copy the "testing" partition down to the "stable". Now we can delete
files from "testing", and the iteration of development cycle ends.

Available scripts:

1. `initial_setup.sh` Initial setup for the host.
2. `include/common.sh` Here we can configure the devices of current and testing partitions
3. `show_mode.sh` Shows the current state (mode).
4. `current_to_testing.sh` Copies all files from current to testing partition.
5. `testing_to_stable.sh` Copies all files from testing to stable partition.
6. `change_mode.sh` Switching between modes. Usage: change_mode.sh [current | testing | off]
7. `clean_partition` Cleans out current and testing partitions. Usage: change_mode.sh <current | testing>

Some actions, such as copying files from testing to stable while overlayfs is mounted are against overlayfs rules.
In all such cases a user will be warned. Immediate reboot after completing these actions is strongly recommended.