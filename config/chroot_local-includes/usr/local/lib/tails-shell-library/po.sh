# This shell library is meant to be used with `set -e` and `set -u`.

# Import str_grep()
. /usr/local/lib/tails-shell-library/common.sh

po_languages () {
   for po in po/*.po ; do
      rel="${po%.po}"
      echo "${rel#po/}"
   done
}

diff_without_pot_creation_date () {
   old="$(tempfile)"
   new="$(tempfile)"
   # This is sed for "remove only the first occurrence":
   sed '/^"POT-Creation-Date:/{x;//!d;x}' "${1}" > "${old}"
   sed '/^"POT-Creation-Date:/{x;//!d;x}' "${2}" > "${new}"
   # `tail -n+3` => read from line 3 so we skip the unified diff
   # header (---/+++) which is uninteresting for us, and will only
   # interfer with how we use this function.
   diff="$(diff -u "${old}" "${new}" | tail -n+3)"
   [ -n "${diff}" ] && echo "${diff}"
   [ -z "${diff}" ]
}

diff_without_pot_creation_date_and_comments () {
    diff="$(diff_without_pot_creation_date "${1}" "${2}")"
    [ -n "${diff}" ] && echo "${diff}"
    echo "${diff}" | while IFS='' read -r cur; do
        if str_grep "${cur}" -q '^-'; then
            IFS='' read -r next
            if ! str_grep "${cur}"  -q '^-#:.*:[0-9]\+$' || \
               ! str_grep "${next}" -q '^+#:.*:[0-9]\+$'; then
                return 1
            fi
        elif str_grep "${cur}" -q '^+'; then
            return 1
        fi
    done
    return ${?}
}

intltool_update_po () {
   (
        cd po
        for locale in "$@" ; do
            intltool-update --dist --gettext-package=tails $locale -o ${locale}.po.new

            [ -f ${locale}.po ]     || continue
            [ -f ${locale}.po.new ] || continue

            if [ "${FORCE}" = yes ]; then
                echo "Force-updating '${locale}.po'."
                mv ${locale}.po.new ${locale}.po
            elif diff_without_pot_creation_date "${locale}.po" "${locale}.po.new" >/dev/null; then
                    echo "${locale}: Only header changes in PO file, delete new PO file."
                    rm ${locale}.po.new
            else
                echo "${locale}: Real changes in PO file: substitute old PO file."
                mv ${locale}.po.new ${locale}.po
            fi
        done
    )
}
