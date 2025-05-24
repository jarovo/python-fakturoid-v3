import fakturoid
from os import environ

fakturoid_slug = environ["FAKTUROID_SLUG"]
assert (
    environ.get("ALLOW_WIPENING") == fakturoid_slug
), f"ALLOW_WIPENING needs to be defined to allow wipening {fakturoid_slug}"

fa = fakturoid.Fakturoid.from_env()

subjects_to_delete = {subject.id: subject.name for subject in fa.subjects.list()}
print(f"Deleting {subjects_to_delete}")
for id in subjects_to_delete:
    assert id
    fa.subjects.delete(id)
