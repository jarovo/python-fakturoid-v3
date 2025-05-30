import pytest
from os import environ
from fakturoid import nounapi
import typing


def test_model_datamodel():
    assert nounapi.Account() == nounapi.Account()
    assert nounapi.Account() in [nounapi.Account()]
    assert nounapi.Account(name="foo") in [nounapi.Account(name="foo")]
    assert nounapi.Account(name="foo") not in [nounapi.Account()]
    assert nounapi.Account() not in [nounapi.Account(name="foo")]


@pytest.mark.asyncio
async def test_subject_crud(name_factory: typing.Callable[[], str]):
    fa = nounapi.Fakturoid(environ["FAKTUROID_SLUG"])
    await fa._oauth_token_client_credentials_flow(**fa.from_env())

    res = await nounapi.Subject(name=name_factory()).acreate(fa)
    assert res.name
    assert res.id
    res.name = res.name + "updated"
    res = await res.aupdate(fa)
    assert res.name.endswith("updated")
    assert res in [
        item async for item in await nounapi.Subject(name=res.name).aindex(fa)
    ]
    assert res.id
    await res.adelete(fa)
