#!/bin/bash

# Script that encodes k8s secrets with base64.
# Might have many bugs!!!

# Unencoded file to read secrets from
IN_FILE=${1:-k8_secret.yaml}

if [ ! -f $IN_FILE ]; then
    echo "File $IN_FILE not found"
fi

# File to write output to
OUT_FILE=${2:-k8_secret_encrypted.yaml}
if [ ! -f $OUT_FILE ]; then
    echo "File $OUT_FILE not found"
fi

# Do not split with spaces in for loop
IFS=$'\n'

# Copy input file to output, so that we can start replacing it in-place.
cp "$IN_FILE" "$OUT_FILE"

# Use awk to get the secrets out of k8_secret, found under the "data" section in the yaml.
for i in $(awk '/^[^ ]/{ f=/^data:/; next } f{ if (match($0, /^\s+[a-zA-Z0-9_]+\s*:.+/)) { print $0 }}' $OUT_FILE); do
    # For each line containing a secret, encode its value in the OUT_FILE in place.
    # Set base64's wrap to zero to have it all in one line.
    # Use commas in the sed regexp, as we may have '/' in the values (e.g. CMSWEB_FRONTEND_PROXY_URL).
    # Leading spaces are not preserved in the replacement string, so we're adding them manually.
    i_escaped=$(echo $i | awk '{ gsub(/\\/, "\\\\"); gsub(/\^/, "\\^"); gsub(/\(/, "\\("); gsub(/\//, "\\/");  printf $0 }')
    sed_expr="s,^$i_escaped$,  $(echo $i | awk '{print $1}') $(echo $i | awk '{printf $2}' | base64 --wrap 0),g"
    sed -E "$sed_expr" -i "$OUT_FILE"
done
