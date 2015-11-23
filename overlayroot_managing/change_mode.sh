#!/bin/bash

set -e

curr_dir="$(dirname "$BASH_SOURCE")"
source "${curr_dir}/include/change_mode_logic.sh"

check_overlayroot
active_mode=$_ACTIVE_MODE

if [ "$#" -gt 1 ]; then
  show_change_mode_usage
elif [ "$#" -eq 1 ]; then
  change_mode $active_mode $1
elif [ "$#" -eq 0 ]; then
  change_mode_prompt_destination $active_mode
fi

