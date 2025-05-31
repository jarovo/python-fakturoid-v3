from dataclasses import dataclass

from fakturoid.routing import RouteParamAware, route_param


def test_routing_param_collection():

    @dataclass
    class ToDo(RouteParamAware):
        unique_id: str = "xxx"
        name: str = "foo"

        @property
        @route_param("id")
        def prop_id(self):
            return self.unique_id

        @property
        @route_param("name")
        def prop_name(self):
            return self.name

    todo_route_params = dict(ToDo().get_route_params())
    assert "id" in todo_route_params
    assert "xxx" == todo_route_params["id"]
    assert "foo" == todo_route_params["name"]
