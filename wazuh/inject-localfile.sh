#!/bin/sh
CONF=/var/ossec/etc/ossec.conf
grep -q sentinel_cef "$CONF" && echo "ALREADY PRESENT" && exit 0
awk '!done && /<\/ossec_config>/ {
  print "  <localfile>"
  print "    <log_format>syslog</log_format>"
  print "    <location>/var/ossec/sentinel_logs/sentinel_cef.log</location>"
  print "  </localfile>"
  done=1
}
{ print }' "$CONF" > /tmp/ossec.new && mv /tmp/ossec.new "$CONF"
grep -n "sentinel_cef" "$CONF"