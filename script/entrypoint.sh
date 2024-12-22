#!/bin/env bash

ENV_PREFIX="PDF2ZH_"
ENV_LIST=(THREADS SOURCE_LANG TARGET_LANG AUTH_FILE)
ENV_LIST_ARGS=(-p -li -lo --authorized)


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

cmd="pdf2zh ${_tmp_args} $PDF2ZH_OTHER_ARGS $@"
echo "Running: $cmd"
exec $cmd