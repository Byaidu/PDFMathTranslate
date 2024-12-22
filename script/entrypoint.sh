#!/bin/env bash

ENV_PREFIX="PDF2ZH_"
ENV_LIST=(THREADS SOURCE_LANG TARGET_LANG AUTH_FILE)
ENV_LIST_ARGS=(-t -li -lo --authorized)


_tmp_args=""

for i in ${!ENV_LIST[@]}; do
    ENV_NAME="${ENV_PREFIX}${ENV_LIST[$i]}"
    ENV_VALUE="${!ENV_NAME}"
    if [ -z "$ENV_VALUE" ]; then
        continue
    fi
    ENV_ARGS="${ENV_LIST_ARGS[$i]}"
    _tmp_args="${_tmp_args} ${ENV_ARGS} ${ENV_VALUE}"
done

# Welcome message
echo "=================================================="
echo " Welcome to PDF2ZH (PDFMathTranslate)!"
echo " PDF scientific paper translation and bilingual comparison."
echo " Project repository: https://github.com/Byaidu/PDFMathTranslate"
echo "--------------------------------------------------"

# Get the current timestamp
start_time=$(date "+%Y-%m-%d %H:%M:%S")

# Trim whitespace from _tmp_args
_tmp_args=$(echo "${_tmp_args}" | xargs)
# Define the command
cmd="pdf2zh -i ${_tmp_args} $PDF2ZH_OTHER_ARGS $@"

# Print the command to be executed with the start time
echo "[$start_time] Running: $cmd"
echo "=================================================="

# Execute the command
exec $cmd