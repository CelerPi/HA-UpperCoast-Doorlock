# Yunhai Intercom Add-on

This add-on runs the long-lived backend for the Yunhai virtual indoor station.
The current skeleton loads Home Assistant add-on options and keeps the process
alive so protocol listeners can be migrated in small, testable slices.

It uses host networking because the intercom protocol needs to bind UDP 10000
and UDP 10008 on the Home Assistant host network.
