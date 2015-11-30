#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/include/common.sh"

check_overlayroot
overlayroot_mounted=$_RET
overlayroot_not_mounted_error=$_ERROR_MSG
overlayroot_upperdir=$_UPPER_LAYER
active_mode=$_ACTIVE_MODE

if $overlayroot_mounted; then
  log_info "Overlayroot is mounted"
else
  log_info "Overlayroot is not mounted, the reason: ${overlayroot_not_mounted_error}"
fi
log_info "Active mode is ${active_mode}"