export_gnome_env() {
    # Get LIVE_USERNAME
    . /etc/live/config.d/username.conf
    local gnome_shell_pid="$(pgrep --newest --euid ${LIVE_USERNAME} gnome-shell)"
    local tmp_env_file="$(tempfile)"
    local vars="(DBUS_SESSION_BUS_ADDRESS|DISPLAY|XAUTHORITY|DESKTOP_SESSION|XMODIFIERS|QT_IM_MODULE|SESSION_MANAGER|(GNOME|GDM|XDG)[^=]*)"
    tr '\0' '\n' < "/proc/${gnome_shell_pid}/environ" | \
        grep -E "^${vars}=" > "${tmp_env_file}"
    while read line; do export "${line}"; done < "${tmp_env_file}"
    rm "${tmp_env_file}"
}
