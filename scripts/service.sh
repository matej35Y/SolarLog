#!/usr/bin/env bash
# SolarLog Bridge Background Service Controller

PLIST="$HOME/Library/LaunchAgents/com.solarlog.bridge.plist"
LOG_FILE="$(cd "$(dirname "$0")/.." && pwd)/bridge.log"

case "$1" in
    start)
        launchctl load -w "$PLIST" 2>/dev/null || true
        echo "✅ SolarLog Bridge service started."
        ;;
    stop)
        launchctl unload -w "$PLIST" 2>/dev/null || true
        echo "🛑 SolarLog Bridge service stopped."
        ;;
    restart)
        launchctl unload "$PLIST" 2>/dev/null || true
        launchctl load -w "$PLIST"
        echo "🔄 SolarLog Bridge service restarted."
        ;;
    status)
        echo "=== LaunchAgent Status ==="
        launchctl list | grep solarlog || pgrep -fl "scripts/bridge.py" || echo "Not running in launchd"
        echo ""
        echo "=== Recent Bridge Logs ==="
        if [ -f "$LOG_FILE" ]; then
            tail -n 25 "$LOG_FILE"
        else
            echo "No log file found at $LOG_FILE"
        fi
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
