# Dynamic profile discovery script
# scripts/discover_profiles.sh
#!/bin/bash

PATCH_FILE=$1
ESXI_HOST=$2
ESXI_PASSWORD=$3

# Upload patch temporarily
sshpass -p "$ESXI_PASSWORD" scp "$PATCH_FILE" root@$ESXI_HOST:/tmp/

# Get profiles
PROFILES=$(sshpass -p "$ESXI_PASSWORD" ssh root@$ESXI_HOST \
  "esxcli software sources profile list -d /tmp/$(basename $PATCH_FILE) | \
   grep -v '^Name' | \
   awk '{print \$1}' | \
   grep -v '\-sg$'")

# Clean up
sshpass -p "$ESXI_PASSWORD" ssh root@$ESXI_HOST "rm /tmp/$(basename $PATCH_FILE)"

# Find standard profile
DEFAULT_PROFILE=$(echo "$PROFILES" | grep '\-standard$' | head -1)
if [ -z "$DEFAULT_PROFILE" ]; then
  DEFAULT_PROFILE=$(echo "$PROFILES" | head -1)
fi

# Output JSON
echo "{\"profiles\": [$(echo "$PROFILES" | sed 's/^/"/;s/$/",/'
