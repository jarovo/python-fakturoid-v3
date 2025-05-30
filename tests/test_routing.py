from dataclasses import dataclass

from fakturoid.routing import RouteParamAware, route_param


def test_routing_param_collection():

    @dataclass
    class ToDo(RouteParamAware):
        unique_id: str = "xxx"

        @property
        @route_param("id")
        def prop_id(self):
            return self.unique_id

    todo_route_params = dict(ToDo("foo").get_route_params())
    assert "id" in todo_route_params
    assert "foo" == todo_route_params["id"]
