#!/bin/bash
# Bluetooth auto-reconnect daemon for AirPods
# Monitors D-Bus for device state changes and reconnects when AirPods wake up.
# Based on: https://github.com/thevar1able/airpods-helper
#
# Runs as a persistent systemd user service.

MAC="04:9D:05:6F:ED:D5"
DBUS_PATH="/org/bluez/hci0/dev_${MAC//:/_}"

# Wait for BT adapter + PipeWire to stabilize on boot
sleep 5

# Initial connection attempt
echo "Initial connect attempt for $MAC..."
bluetoothctl connect "$MAC" 2>&1 || true

# Monitor D-Bus for PropertiesChanged on the device
# When Connected flips to true (AirPods taken out of case), force profile connection
exec python3 - "$MAC" "$DBUS_PATH" << 'PYEOF'
import sys
import signal
import dbus
import dbus.mainloop.glib
from gi.repository import GLib

MAC = sys.argv[1]
DBUS_PATH = sys.argv[2]

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

last_connected = None

def on_properties_changed(interface, changed, invalidated, path=None):
    global last_connected
    if interface != "org.bluez.Device1":
        return
    if "Connected" not in changed:
        return

    connected = bool(changed["Connected"])

    if connected and last_connected is False:
        print(f"AirPods woke up, forcing profile connection...")
        try:
            dev = dbus.Interface(
                bus.get_object("org.bluez", DBUS_PATH),
                "org.bluez.Device1"
            )
            dev.Connect()
            print("Connect() succeeded")
        except dbus.exceptions.DBusException as e:
            print(f"Connect() failed: {e.get_dbus_message()}")
    elif not connected:
        print(f"AirPods disconnected")

    last_connected = connected

# Subscribe to PropertiesChanged on the specific device path
bus.add_signal_receiver(
    on_properties_changed,
    signal_name="PropertiesChanged",
    dbus_interface="org.freedesktop.DBus.Properties",
    path=DBUS_PATH,
)

# Also listen for adapter-level signals (device appearing after BT restart)
bus.add_signal_receiver(
    on_properties_changed,
    signal_name="PropertiesChanged",
    dbus_interface="org.freedesktop.DBus.Properties",
    path_keyword="path",
)

print(f"Monitoring {MAC} for connection events...")

# Clean exit on SIGTERM
signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))

loop = GLib.MainLoop()
loop.run()
PYEOF
