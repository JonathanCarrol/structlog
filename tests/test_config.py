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

import warnings

import pytest

from pretend import stub

from structlog._compat import PY3
from structlog._config import (
    BoundLoggerLazyProxy,
    _CONFIG,
    _BUILTIN_DEFAULT_CONTEXT_CLASS,
    _BUILTIN_DEFAULT_PROCESSORS,
    _BUILTIN_DEFAULT_WRAPPER_CLASS,
    configure,
    configure_once,
    reset_defaults,
    wrap_logger,
)
from structlog._loggers import BoundLogger


@pytest.fixture
def proxy():
    """
    Returns a BoundLoggerLazyProxy constructed w/o paramaters & None as logger.
    """
    return BoundLoggerLazyProxy(None)


class Wrapper(BoundLogger):
    """
    Custom wrapper class for testing.
    """


class TestConfigure(object):
    def teardown_method(self, method):
        reset_defaults()

    def test_configure_all(self, proxy):
        x = stub()
        configure(processors=[x], context_class=dict)
        b = proxy.bind()
        assert [x] == b._processors
        assert dict is b._context.__class__

    def test_reset(self, proxy):
        x = stub()
        configure(processors=[x], context_class=dict, wrapper_class=Wrapper)
        reset_defaults()
        b = proxy.bind()
        assert [x] != b._processors
        assert _BUILTIN_DEFAULT_PROCESSORS == b._processors
        assert isinstance(b, _BUILTIN_DEFAULT_WRAPPER_CLASS)
        assert _BUILTIN_DEFAULT_CONTEXT_CLASS == b._context.__class__

    def test_just_processors(self, proxy):
        x = stub()
        configure(processors=[x])
        b = proxy.bind()
        assert [x] == b._processors
        assert _BUILTIN_DEFAULT_PROCESSORS != b._processors
        assert _BUILTIN_DEFAULT_CONTEXT_CLASS == b._context.__class__

    def test_just_context_class(self, proxy):
        configure(context_class=dict)
        b = proxy.bind()
        assert dict is b._context.__class__
        assert _BUILTIN_DEFAULT_PROCESSORS == b._processors

    def test_configure_sets_is_configured(self):
        assert False is _CONFIG.is_configured
        configure()
        assert True is _CONFIG.is_configured

    def test_rest_resets_is_configured(self):
        configure()
        reset_defaults()
        assert False is _CONFIG.is_configured


class TestBoundLoggerLazyProxy(object):
    def teardown_method(self, method):
        reset_defaults()

    def test_repr(self):
        p = BoundLoggerLazyProxy(
            None, processors=[1, 2, 3], context_class=dict,
            initial_values={'foo': 42},
        )
        assert (
            "<BoundLoggerLazyProxy(logger=None, wrapper_class=None, "
            "processors=[1, 2, 3], "
            "context_class=<%s 'dict'>, "
            "initial_values={'foo': 42})>"
            % ('class' if PY3 else 'type',)
        ) == repr(p)

    def test_returns_bound_logger_on_bind(self, proxy):
        assert isinstance(proxy.bind(), BoundLogger)

    def test_returns_bound_logger_on_new(self, proxy):
        assert isinstance(proxy.new(), BoundLogger)

    def test_prefers_args_over_config(self):
        p = BoundLoggerLazyProxy(None, processors=[1, 2, 3],
                                 context_class=dict)
        b = p.bind()
        assert isinstance(b._context, dict)
        assert [1, 2, 3] == b._processors

        class Class(object):
            def __init__(self, *args, **kw):
                pass

            def update(self, *args, **kw):
                pass
        configure(processors=[4, 5, 6], context_class=Class)
        b = p.bind()
        assert not isinstance(b._context, Class)
        assert [1, 2, 3] == b._processors

    def test_falls_back_to_config(self, proxy):
        b = proxy.bind()
        assert isinstance(b._context, _CONFIG.default_context_class)
        assert _CONFIG.default_processors == b._processors

    def test_bind_honors_initial_values(self):
        p = BoundLoggerLazyProxy(None, initial_values={'a': 1, 'b': 2})
        b = p.bind()
        assert {'a': 1, 'b': 2} == b._context
        b = p.bind(c=3)
        assert {'a': 1, 'b': 2, 'c': 3} == b._context

    def test_bind_binds_new_values(self, proxy):
        b = proxy.bind(c=3)
        assert {'c': 3} == b._context

    def test_honors_wrapper_class(self):
        p = BoundLoggerLazyProxy(None, wrapper_class=Wrapper)
        b = p.bind()
        assert isinstance(b, Wrapper)

    def test_honors_wrapper_from_config(self, proxy):
        configure(wrapper_class=Wrapper)
        b = proxy.bind()
        assert isinstance(b, Wrapper)

    def test_new_binds_only_initial_values_impolicit_ctx_class(self, proxy):
        proxy = BoundLoggerLazyProxy(None, initial_values={'a': 1, 'b': 2})
        b = proxy.new(foo=42)
        assert {'a': 1, 'b': 2, 'foo': 42} == b._context

    def test_new_binds_only_initial_values_explicit_ctx_class(self, proxy):
        proxy = BoundLoggerLazyProxy(None,
                                     initial_values={'a': 1, 'b': 2},
                                     context_class=dict)
        b = proxy.new(foo=42)
        assert {'a': 1, 'b': 2, 'foo': 42} == b._context


class TestFunctions(object):
    def teardown_method(self, method):
        reset_defaults()

    def test_wrap_passes_args(self):
        logger = object()
        p = wrap_logger(logger, processors=[1, 2, 3], context_class=dict)
        assert logger is p._logger
        assert [1, 2, 3] == p._processors
        assert dict is p._context_class

    def test_wrap_returns_proxy(self):
        assert isinstance(wrap_logger(None), BoundLoggerLazyProxy)

    def test_configure_once_issues_warning_on_repeated_call(self):
        with warnings.catch_warnings(record=True) as warns:
            configure_once()
        assert 0 == len(warns)
        with warnings.catch_warnings(record=True) as warns:
            configure_once()
        assert 1 == len(warns)
        assert RuntimeWarning == warns[0].category
        assert 'Repeated configuration attempted.' == warns[0].message.args[0]