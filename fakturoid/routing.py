class Router:
    def __init__(self, resource: str):
        self.resource = resource

    def load(self) -> str:
        return f"/accounts/${{slug}}/{self.resource}.json"

    def create(self) -> str:
        return f"/accounts/${{slug}}/{self.resource}.json"

    def update(self, id: int | str) -> str:
        return f"/accounts/${{slug}}/{self.resource}/{id}.json"

    def index(self) -> str:
        return f"/accounts/${{slug}}/{self.resource}.json"

    def search(self) -> str:
        return f"/accounts/${{slug}}/{self.resource}/search.json"

    def detail(self, id: int | str) -> str:
        return f"/accounts/${{slug}}/{self.resource}/{id}.json"

    def delete(self, id: int | str) -> str:
        return f"/accounts/${{slug}}/{self.resource}/{id}.json"

    def fire_action(self, id: int | str) -> str:
        return f"/accounts/${{slug}}/{self.resource}/{id}/fire.json"
