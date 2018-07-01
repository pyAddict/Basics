from abc import ABC, abstractmethod
from collections import deque
from typing import Callable, Deque, Iterable

from streamAPI.stream.decos import check_pipeline, close_pipeline
from streamAPI.stream.exception import PipelineNOTClosed
from streamAPI.stream.optional import EMPTY, Optional
from streamAPI.utility.Types import Filter, Function, X
from streamAPI.utility.utils import always_true, get_functions_clazz


class GroupByValueType(type):
    """
    In group_by method of Stream class, we may want to
    used customised container type for value holding.

    For example:
        Stream([1,2,5,1,3,4,2]).group_by(lambda x:x%2)
        -> {1: [1, 5, 1, 3], 0: [2, 4, 2]}

        Here value container class is List.

        If we want value container class to be Set
        Stream([1, 2, 5, 1, 3, 4, 2]).group_by(lambda x: x % 2, value_container_clazz=SetType)
        -> {1: {1, 3, 5}, 0: {2, 4}}

    By default, value container class will be of Type List. In case we want it be of
    specific type, then the class has to implement "add" method. This can be fulfilled by
    making GroupByValueType class as a meta class.

    Here we implement two Class ListType and SetType.
    """

    def __init__(cls, *args, **kwargs):
        type.__init__(cls, *args, **kwargs)

    @abstractmethod
    def add(self, o):
        pass


class ListType(list, metaclass=GroupByValueType):
    """
    This is the default choice of class for holding value after "group_by"
    operation on Stream class object.

    Stream([1,2,5,1,3,4,2]).group_by(lambda x:x%2,value_container_clazz=ListType)
    -> {1: [1, 5, 1, 3], 0: [2, 4, 2]}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add(self, o):
        return self.append(o)


class SetType(set, metaclass=GroupByValueType):
    """
    Stream([1,2,5,1,3,4,2]).group_by(lambda x:x%2,value_container_clazz=SetType)
    -> {1: {1, 3, 5}, 0: {2, 4}}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    add = set.add


class Supplier(Iterable[X]):
    """
    This class provide a wrapper around a callable function.

    Example:
        from random import random

        supplier = Supplier(random)

        print(next(supplier))
        print(next(supplier))
        print(next(supplier))

        for idx, x in enumerate(supplier):
            print(x)

            if idx == 10:
                break

    """

    def __init__(self, func: Callable[[], X]):
        self.func = func

    def __iter__(self):
        while True:
            yield next(self)

    def __next__(self):
        return self.func()


class AbstractCondition(ABC):
    @abstractmethod
    def apply(self, e): pass


class _IfThen(AbstractCondition):
    """
    Objects of this class will be chained together in ChainedCondition
    class object.

    def transform(x):
        if predicate(x):
            return Optional(func(x))
        else:
            return EMPTY


    That is equivalent to: IfThen(predicate, func)
    """

    def __init__(self, predicate: Filter, func: Function):
        self._if = predicate
        self._func = func

    def apply(self, e) -> Optional:
        return Optional(self._func(e)) if self._if(e) else EMPTY


class ChainedCondition(AbstractCondition):
    """
    This class will help Stream in transforming elements on the basis
    of conditions.

    def transform(x):
        if predicate1(x):
            return f1(x)
        elif predicate2(x):
            return f2(x)
        .
        .
        .
        else:
            return fn(x)

    That is equivalent to:

    ChainedCondition().if_then(predicate1,f1).if_then(predicate2,f2). ... .otherwise(fn)

    Note that before applying element, chainedCondition must be closed; ChainedCondition
    can be closed by invoking "otherwise" or "done" method.

    If "done" method has been chosen to close the Pipeline and if no condition
    defined by ChainedCondition object returns True then element is returned.

    """

    def __init__(self, name=None):
        self._conditions: Deque[_IfThen] = deque()
        self._closed = False
        self._name = name
        self._else_called = False

    @classmethod
    def if_else(cls, predicate, if_, else_) -> 'ChainedCondition':
        """
        Creates a ChainedCondition with given "if" and "else" condition.

        If predicate returns True on an element then ChainedCondition
        will return if_(element) otherwise else_(element) will be returned
        on invoking "apply" method.

        :param predicate:
        :param if_:
        :param else_:
        :return:
        """

        return cls().if_then(predicate, if_).otherwise(else_)

    @property
    def closed(self):
        """
        Gets current state of ChainedCondition pipeline.
        :return:
        """

        return self._closed

    @closed.setter
    def closed(self, closed):
        """
        Updates state of ChainedCondition pipeline.

        :param closed:
        :return:
        """

        self._closed = closed

    @check_pipeline
    def if_then(self, predicate: Filter, func: Function):
        """
        Creates _IfThen object from given predicate and func.

        :param predicate:
        :param func:
        :return:
        """

        self._conditions.append(_IfThen(predicate, func))
        return self

    @close_pipeline
    def otherwise(self, func: Function):
        """
        Adds "else" condition to ChainedCondition object.
        After this method, pipeline will be closed.

        It is required that "if" condition must be specified
        before invoking this method.

        :param func:
        :return:
        """

        if not self._conditions:
            raise AttributeError("No 'if' condition added.")

        return self.if_then(always_true, func)

    @close_pipeline
    def done(self):
        """
        closes the ChainedCondition pipeline.
        :return:
        """

        return self

    def apply(self, e):
        """
        Transforms given element using added conditions.

        If no condition returns True on element e then returns e.

        Note that ChainedCondition pipeline must be closed
        before invoking this method.

        :param e:
        :return:
        """

        if self._closed is False:
            raise PipelineNOTClosed('close operation such as else_ '
                                    'or done has not been invoked.')

        for condition in self._conditions:
            y = condition.apply(e)

            if y is not EMPTY:
                return y.get()
        else:
            return e

    def default_name(self) -> str:
        size = len(self._conditions)

        if size == 0:
            return 'ChainedCondition has not defined any condition'

        if size == 1:
            return "ChainedCondition defines 'if' condition"

        if self._else_called:
            if size == 2:
                return "ChainedCondition defines 'if' and 'else' condition"

            return ("ChainedCondition defines 'if' then {} elif condition{} "
                    "and 'else' condition".format(size - 2, 's' if size > 3 else ''))
        else:
            return ("ChainedCondition defines 'if' then {} elif condition{}"
                    .format(size - 1, 's' if size > 2 else ''))

    def __str__(self):
        return self._name or self.default_name()

    def __repr__(self):
        return str(self)


if __name__ == 'streamAPI.stream.streamHelper':
    __all__ = get_functions_clazz(__name__, __file__)
