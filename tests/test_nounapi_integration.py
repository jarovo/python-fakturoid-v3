import pytest
from fakturoid import nounapi, models
import typing
from decimal import Decimal
from collections import abc
import pytest_asyncio

NameFactoryType = typing.Callable[[], str]


def test_model_datamodel():
    assert nounapi.Account() == nounapi.Account()
    assert nounapi.Account() in [nounapi.Account()]
    assert nounapi.Account(name="foo") in [nounapi.Account(name="foo")]
    assert nounapi.Account(name="foo") not in [nounapi.Account()]
    assert nounapi.Account() not in [nounapi.Account(name="foo")]


@pytest_asyncio.fixture()
async def fa():
    async with nounapi.Fakturoid() as fa:
        yield fa


@pytest_asyncio.fixture()
async def example_subject(fa: nounapi.Fakturoid, name_factory: NameFactoryType):
    return await nounapi.Subject(name=name_factory()).a_create(fa)


@pytest.mark.asyncio
async def test_subject_crud(fa: nounapi.Fakturoid, name_factory: NameFactoryType):
    subject = await nounapi.Subject(name=name_factory()).a_create(fa)
    assert subject.name
    assert subject.id
    subject.name = subject.name + "updated"
    subject = await subject.a_update(fa)
    assert subject.name.endswith("updated")
    assert subject in [
        item async for item in await nounapi.Subject(name=subject.name).a_index(fa)
    ]
    assert subject.id
    await subject.a_delete(fa)


class AccDocCRUDResource(typing.Protocol):
    async def a_create(self, fa: nounapi.Fakturoid) -> typing.Self: ...

    async def a_update(self, fa: nounapi.Fakturoid) -> typing.Self: ...

    async def a_delete(self, fa: nounapi.Fakturoid) -> None: ...

    async def a_index(
        self, fa: nounapi.Fakturoid
    ) -> abc.AsyncIterable[typing.Self]: ...

    async def a_search(
        self, fa: nounapi.Fakturoid
    ) -> abc.AsyncIterable[typing.Self]: ...

    lines: list[models.Line]


@pytest.mark.asyncio
@pytest.mark.parametrize("acc_doc_t", [nounapi.Invoice])
async def test_accounting_doc_crud(
    acc_doc_t: type[AccDocCRUDResource],
    example_subject: nounapi.Subject,
    fa: nounapi.Fakturoid,
    name_factory: typing.Callable[[], str],
):
    assert example_subject.id
    created_doc = await nounapi.Invoice(subject_id=example_subject.id).a_create(fa)
    assert created_doc.lines == []

    created_doc.lines = [
        models.Line(name=name_factory(), unit_price=Decimal(1), quantity=Decimal(1))
    ]
    updated_doc = await created_doc.a_update(fa)

    assert 1 == len(updated_doc.lines)
