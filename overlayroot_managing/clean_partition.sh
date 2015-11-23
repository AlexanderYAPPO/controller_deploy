#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/include/common.sh"
source "${project_root}/include/clean_partition_logic.sh"

check_overlayroot
active_mode=$_ACTIVE_MODE

if [ "$#" -ne 1 ]; then
  show_clean_partition_usage
fi

partition_to_remove=$1
rm_partition "$active_mode" "$partition_to_remove"
