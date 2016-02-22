# Copyright 2013 Hynek Schlawack
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, division, print_function

from functools import wraps

from structlog._compat import string_types
from structlog.common import format_exc_info, render_kv


class BoundLogger(object):
    @classmethod
    def fromLogger(cls, logger, processors=None):
        """
        Create a new BoundLogger for `logger`.

        :param logger: An instance of a logger whose method calls will be
            wrapped.
        :param list processors: List of processors.

        :rtype: BoundLogger
        """
        return cls(
            logger,
            processors or [
                format_exc_info,
                render_kv,
            ], {}
        )

    def __init__(self, logger, processors, event_dict):
        """
        Use `fromLogger()`.
        """
        self._logger = logger
        self._event_dict = event_dict
        self._processors = processors

    def bind(self, **kw):
        """
        Memorize all keyword arguments for future log calls.
        """
        event_dict = dict(self._event_dict, **kw)
        return self.__class__(self._logger, self._processors, event_dict)

    def __getattr__(self, name):
        log_meth = getattr(self._logger, name)

        @wraps(log_meth)
        def wrapped(event=None, **kw):
            """
            Before calling actual logger method, transform the accumulated
            `event_dict` together with the event itself using the processor
            chain.
            """
            res = dict(self._event_dict, event=event, **kw)
            for processor in self._processors:
                res = processor(self._logger, name, res)
                if res is None:
                    raise ValueError('Processor returned None.')
                elif res is False:
                    return
            if isinstance(res, string_types):
                args, kw = (res,), {}
            else:
                args, kw = res
            return log_meth(*args, **kw)
        return wrapped
