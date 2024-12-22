#!/bin/env bash

ENV_PREFIX="PDF2ZH_"
ENV_LIST=(THREADS SOURCE_LANG TARGET_LANG)
ENV_LIST_ARGS=(--thread --lang-in --lang-out)

# define the default values
_tmp_args=""

# Handle for auth
_auth_dir="$HOME/.auth"
_auth_user_file="$_auth_dir/user"
_auth_pass_file="$_auth_dir/pass"
_auth_enabled=false

echo "=================================================="
# Create the auth directory if it does not exist
mkdir -p "$_auth_dir" || { echo "Error: Failed to create directory $_auth_dir"; exit 1; }

# Check if user and password are set via environment variables
if [ -n "$PDF2ZH_AUTH_USER" ] && [ -n "$PDF2ZH_AUTH_PASS" ]; then
    echo -e "$PDF2ZH_AUTH_USER\n" > "$_auth_user_file"
    echo -e "$PDF2ZH_AUTH_PASS\n" > "$_auth_pass_file"
    _auth_enabled=true
    # Clear sensitive variables immediately after use
    unset PDF2ZH_AUTH_USER PDF2ZH_AUTH_PASS
fi

# Check if additional auth files are specified and valid
_auth_user_file_valid=false
_auth_pass_file_valid=false

if [ -n "$PDF2ZH_AUTH_USER_FILE" ] && [ -f "$PDF2ZH_AUTH_USER_FILE" ]; then
    _user_lines=$(awk 'END {print NR}' "$PDF2ZH_AUTH_USER_FILE")
    _auth_user_file_valid=true
fi

if [ -n "$PDF2ZH_AUTH_PASS_FILE" ] && [ -f "$PDF2ZH_AUTH_PASS_FILE" ]; then
    _pass_lines=$(awk 'END {print NR}' "$PDF2ZH_AUTH_PASS_FILE")
    _auth_pass_file_valid=true
fi

# Check if user and password file line counts are the same
if [ "$_auth_user_file_valid" = true ] && [ "$_auth_pass_file_valid" = true ]; then
    if [ "$_user_lines" -ne "$_pass_lines" ]; then
        echo -e "\033[1;31mError: Line counts in user file=${PDF2ZH_AUTH_USER_FILE} and password=${PDF2ZH_AUTH_PASS_FILE} file do not match. Will not use auth file."
    else
        cat "$PDF2ZH_AUTH_USER_FILE" > "$_auth_user_file"
        cat "$PDF2ZH_AUTH_PASS_FILE" > "$_auth_pass_file"
        _auth_enabled=true
    fi
fi

# Clean up sensitive environment variables
unset PDF2ZH_AUTH_USER_FILE PDF2ZH_AUTH_PASS_FILE _user_lines _pass_lines

# handle debug mode
if [ "$PDF2ZH_DEBUG" = "true" ]; then
    _tmp_args="${_tmp_args} --debug"
fi

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
echo "--------------------------------------------------"
echo "Welcome to PDF2ZH (PDFMathTranslate)!"
echo "PDF scientific paper translation and bilingual comparison."
echo "Project repository: https://github.com/Byaidu/PDFMathTranslate"
echo "--------------------------------------------------"

# Get the current timestamp
start_time=$(date "+%Y-%m-%d %H:%M:%S")

# Trim whitespace from _tmp_args
_tmp_args=$(echo "${_tmp_args}" | xargs)
# Define the command which will be excuted
cmd="pdf2zh --interactive ${_tmp_args} $PDF2ZH_OTHER_ARGS $@"
cmd=$(echo $cmd | xargs)
# Define the command to be printed, this is used to hide sensitive information
_cmd_print=$cmd

# Add authorization arguments if auth is enabled
if [ "$_auth_enabled" = true ]; then
    chmod 600 "$_auth_user_file" "$_auth_pass_file" || { echo "Error: Failed to set permissions on auth files"; exit 1; }
    echo -e "\033[1;33mWarning: --authorized flag doesn't work, so disable auth. And Ignore the --authorized in the print message\033[0m"
    # cmd="${cmd} --authorized ${_auth_user_file} ${_auth_pass_file}"
    # Hide sensitive paths, only show filenames
    _auth_user_file_name=$(basename "$_auth_user_file")
    _auth_pass_file_name=$(basename "$_auth_pass_file")
    # Update the printed command to hide full paths
    _cmd_print="${_cmd_print} --authorized ****/${_auth_user_file_name} ****/${_auth_pass_file_name}"
fi
# Unset sensitive variables
unset _auth_user_file _auth_pass_file

# Print the command to be executed with the start time
echo "[$start_time] Running: $_cmd_print"
echo "=================================================="

# Execute the command
exec $cmd