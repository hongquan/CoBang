# Copyright © 2020, Nguyễn Hồng Quân <ng.hong.quan@gmail.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#       http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import locale
import gettext

from .consts import SHORT_NAME
from .app import CoBangApplication
from .resources import get_locale_folder
from .logging import GLibLogHandler


def main():
    locale.bindtextdomain(SHORT_NAME, get_locale_folder())
    gettext.bindtextdomain(SHORT_NAME, get_locale_folder())
    locale.textdomain(SHORT_NAME)
    gettext.textdomain(SHORT_NAME)
    with GLibLogHandler().applicationbound():
        app = CoBangApplication()
        return app.run(sys.argv)


if __name__ == '__main__':
    main()
