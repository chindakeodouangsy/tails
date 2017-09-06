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
   old="$1"
   new="$2"

   [ $(diff "$old" "$new" | grep -Ec '^>') -eq 1 -a \
     $(diff "$old" "$new" | grep -Ec '^<') -eq 1 -a \
     $(diff "$old" "$new" | grep -Ec '^[<>] "POT-Creation-Date:') -eq 2 ]
}

diff_without_pot_creation_date_and_comments () {
    old="$(tempfile)"
    new="$(tempfile)"
    # This is sed for "remove only the first occurrence":
    sed '/^"POT-Creation-Date:/{x;//!d;x}' "${1}" > "${old}"
    sed '/^"POT-Creation-Date:/{x;//!d;x}' "${2}" > "${new}"
    # `tail -n+3` => read from line 3 so we skip the unified diff
    # header (---/+++, which we otherwise would match)
    diff -u "${old}" "${new}" | tail -n+3 | while IFS='' read -r cur; do
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
    ret="${?}"
    rm "${old}" "${new}"
    return ${ret}
}

intltool_update_po () {
   (
        cd po
        for locale in "$@" ; do
            intltool-update --dist --gettext-package=tails $locale -o ${locale}.po.new

            [ -f ${locale}.po ]     || continue
            [ -f ${locale}.po.new ] || continue

            if diff_without_pot_creation_date "${locale}.po" "${locale}.po.new"; then
                    echo "${locale}: Only header changes in potfile, delete new PO file."
                    rm ${locale}.po.new
            else
                echo "${locale}: Real changes in PO file: substitute old PO file."
                mv ${locale}.po.new ${locale}.po
            fi
        done
    )
}
