import os
import gettext


if os.path.exists('po/locale'):
    translation = gettext.translation('tails-server', 'po/locale', fallback=True)
else:
    translation = gettext.translation('tails-server', '/usr/share/locale',
                                      fallback=True)
_ = translation.ugettext
