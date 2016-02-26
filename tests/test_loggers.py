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

import re
import unittest

import pytest

from pretend import stub

from structlog.common import KeyValueRenderer
from structlog.loggers import (
    BoundLogger, NOPLogger, _GLOBAL_NOP_LOGGER, BaseLogger,
    _DEFAULT_PROCESSORS, _DEFAULT_BIND_FILTER,
)


def test_binds_independently():
    logger = stub(msg=lambda event: event, err=lambda event: event)
    b = BoundLogger.wrap(logger, processors=[KeyValueRenderer(sort_keys=True)])
    b = b.bind(x=42, y=23)
    b1 = b.bind(foo='bar')
    assert "event='event1' foo='bar' x=42 y=23 z=1" == b1.msg('event1', z=1)
    assert "event='event2' foo='bar' x=42 y=23 z=0" == b1.err('event2', z=0)
    b2 = b.bind(foo='qux')
    assert "event='event3' foo='qux' x=42 y=23 z=2" == b2.msg('event3', z=2)
    assert "event='event4' foo='qux' x=42 y=23 z=3" == b2.err('event4', z=3)


def test_processor_returning_none_raises_valueerror():
    logger = stub(msg=lambda event: event)
    b = BoundLogger.wrap(logger, processors=[lambda *_: None])
    with pytest.raises(ValueError) as e:
        b.msg('boom')
    assert re.match(
        r'Processor \<function .+\> returned None.', e.value.args[0]
    )


def test_processor_returning_false_silently_aborts_chain(capsys):
    logger = stub(msg=lambda event: event)
    # The 2nd processor would raise a ValueError if reached.
    b = BoundLogger.wrap(logger, processors=[lambda *_: False,
                                             lambda *_: None])
    b.msg('silence!')
    assert ('', '') == capsys.readouterr()


def test_processor_can_return_both_str_and_tuple():
    logger = stub(msg=lambda args, **kw: (args, kw))
    b1 = BoundLogger.wrap(logger, processors=[lambda *_: 'foo'])
    b2 = BoundLogger.wrap(logger, processors=[lambda *_: (('foo',), {})])
    assert b1.msg('foo') == b2.msg('foo')


def test_NOPLogger_returns_itself_on_bind():
    nl = NOPLogger(None, None, None, None)
    assert nl is nl.bind(foo=42)


def test_NOPLogger_returns_itself_on_wrap():
    assert NOPLogger(None, None, None, None).wrap(None) is _GLOBAL_NOP_LOGGER


def test_BoundLogger_returns_GLOBAL_NOP_LOGGER_if_bind_filter_matches():
    def filter_throw_away(*_):
        return False

    b = BoundLogger.wrap(None, bind_filter=filter_throw_away)
    nl = b.bind(foo=42)
    assert nl == _GLOBAL_NOP_LOGGER
    # `logger` is None, so we get an AttributeError if the following call
    # doesn't get intercepted.
    nl.info('should not blow up')


def test_meta():
    """
    Class hierarchy is sound.
    """
    assert issubclass(BoundLogger, BaseLogger)
    assert isinstance(BoundLogger.wrap(None), BaseLogger)
    assert issubclass(NOPLogger, BaseLogger)
    assert isinstance(_GLOBAL_NOP_LOGGER, BaseLogger)


def test_wrapper_caches():
    """
    __getattr__() gets called only once per logger method.
    """
    logger = stub(msg=lambda event: event, err=lambda event: event)
    b = BoundLogger.wrap(logger)
    assert 'msg' not in b.__dict__
    b.msg('foo')
    assert 'msg' in b.__dict__


class ConfigureTestCase(unittest.TestCase):
    """
    There's some global state here so we use a class to be able to clean up.
    """
    def setUp(self):
        self.b_def = BoundLogger.wrap(None)

    def tearDown(self):
        BoundLogger.reset_defaults()

    def test_reset(self):
        x = stub()
        y = stub()
        BoundLogger.configure(processors=[x], bind_filter=y)
        BoundLogger.reset_defaults()
        b = BoundLogger.wrap(None)
        assert x is not b._processors[0]
        assert y is not b._bind_filter
        assert self.b_def._processors == b._processors
        assert self.b_def._bind_filter == b._bind_filter
        assert _DEFAULT_PROCESSORS == b._processors
        assert _DEFAULT_BIND_FILTER == b._bind_filter[0]

    def test_just_processors(self):
        x = stub()
        BoundLogger.configure(processors=[x])
        b = BoundLogger.wrap(None)
        assert x == b._processors[0]
        assert self.b_def._bind_filter is b._bind_filter

    def test_just_bind_filter(self):
        x = stub()
        BoundLogger.configure(bind_filter=x)
        b = BoundLogger.wrap(None)
        assert self.b_def._processors == b._processors
        assert x is b._bind_filter[0]

    def test_both(self):
        x = stub()
        y = stub()
        BoundLogger.configure(processors=[x], bind_filter=y)
        b = BoundLogger.wrap(None)
        assert 1 == len(b._processors)
        assert x is b._processors[0]
        assert y is b._bind_filter[0]

    def test_overwrite_bind_filter(self):
        x = stub()
        y = stub()
        z = stub()
        BoundLogger.configure(processors=[x], bind_filter=y)
        b = BoundLogger.wrap(None, bind_filter=z)
        assert 1 == len(b._processors)
        assert x is b._processors[0]
        assert z is b._bind_filter[0]

    def test_overwrite_processors(self):
        x = stub()
        y = stub()
        z = stub()
        BoundLogger.configure(processors=[x], bind_filter=y)
        b = BoundLogger.wrap(None, processors=[z])
        assert 1 == len(b._processors)
        assert z is b._processors[0]
        assert y is b._bind_filter[0]

    def test_affects_all(self):
        x = stub()
        y = stub()
        b = BoundLogger.wrap(None)
        BoundLogger.configure(processors=[x], bind_filter=y)
        assert 1 == len(b._processors)
        assert y is b._bind_filter[0]
        assert x is b._processors[0]

    def test_configure_does_not_affect_overwritten(self):
        """
        This is arguably an ugly test.  However it aspires to prove that any
        order of configuring and wrapping works as advertised.
        """
        x = stub()
        y = stub()
        z = stub()
        BoundLogger.configure(processors=[x], bind_filter=y)
        b = BoundLogger.wrap(None, processors=[z], bind_filter=z)
        part_def_b = BoundLogger.wrap(None, bind_filter=z)
        def_b1 = BoundLogger.wrap(None)
        BoundLogger.configure(processors=[x], bind_filter=y)
        assert 1 == len(b._processors)
        assert z is b._bind_filter[0]
        assert z is b._processors[0]
        def_b2 = BoundLogger.wrap(None)
        assert 1 == len(def_b1._processors)
        assert y is def_b1._bind_filter[0]
        assert x is def_b1._processors[0]
        assert 1 == len(def_b2._processors)
        assert y is def_b2._bind_filter[0]
        assert x is def_b2._processors[0]
        assert x is part_def_b._processors[0]
        assert z is part_def_b._bind_filter[0]
        assert def_b1._processors is BoundLogger._processors
        assert def_b1._bind_filter is BoundLogger._bind_filter
        assert def_b2._processors is BoundLogger._processors
        assert def_b2._bind_filter is BoundLogger._bind_filter
        assert part_def_b._bind_filter != BoundLogger._bind_filter
        assert part_def_b._processors is BoundLogger._processors
