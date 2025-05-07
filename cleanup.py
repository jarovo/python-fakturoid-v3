import fakturoid
from tests import conf

fa = fakturoid.Fakturoid(
    conf.FAKTUROID_SLUG,
    conf.FAKTUROID_CLIENT_ID,
    conf.FAKTUROID_CLIENT_SECRET,
    conf.TESTS_USER_AGENT,
)
subjects_to_delete = {
    subject.id: subject.name
    for subject in fa.subjects.list()
    if subject.name.startswith(conf.TESTS_OBJECTS_NAME_PREFIX)
}
print(f"Deleting {subjects_to_delete}")
for id in subjects_to_delete:
    assert id
    fa.subjects.delete(id)
