from dataclasses import dataclass, field
import typing
from string import Template

ATTR_NAME_FIELD = "_route_param_name"


class RouteParamProvider(typing.Protocol):
    def get_route_params(self) -> typing.Iterator[tuple[str, str]]: ...


def make_getter[T](fget: typing.Callable[[RouteParamProvider], str]):
    def _route_param_name_getter(x: RouteParamProvider) -> str:
        return fget(x)

    return _route_param_name_getter


class RouteParamAware:
    _route_param_registry: dict[str, typing.Callable[[RouteParamProvider], str]] = {}

    def __init_subclass__(cls, **kwargs: dict[str, typing.Any]):
        super().__init_subclass__(**kwargs)
        cls._route_param_registry = {}

        for attr in cls.__dict__.values():
            if isinstance(attr, property):
                if getattr(attr, "fget", None) and (
                    route_param_name := getattr(attr.fget, ATTR_NAME_FIELD, None)
                ):
                    assert attr.fget
                    cls._route_param_registry[route_param_name] = make_getter(attr.fget)

    def get_route_params(self) -> typing.Iterator[tuple[str, str]]:
        for name, prop_getter in self._route_param_registry.items():
            yield name, prop_getter(self)


@dataclass
class RouteParamResolver:
    models: typing.Iterable[RouteParamProvider]
    context: dict[str, str] = field(default_factory=dict[str, str])

    def __post_init__(self):
        self.load_params()

    def substitute(self, path_template: Template) -> str:
        try:
            return path_template.substitute(self.context)
        except KeyError as err:
            raise KeyError(
                f"Couldn't resolve route param {err}. Available route params: {self.context} loaded from {self.models}."
            )

    def load_params(self) -> None:
        for model in self.models:
            self.context.update(model.get_route_params())


def route_param(name: str):
    def decorator(fn: typing.Callable[..., typing.Any]):
        setattr(fn, ATTR_NAME_FIELD, name)
        return fn

    return decorator
