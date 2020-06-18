import gettext

from .consts import SHORT_NAME


gettext.textdomain(SHORT_NAME)
_ = gettext.gettext
