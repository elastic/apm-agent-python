#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import os

import pytest

from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span

graphene = pytest.importorskip("graphene")
graphql = pytest.importorskip("graphql")

pytestmark = pytest.mark.graphene


class Query(graphene.ObjectType):
    rand = graphene.String()


class Success(graphene.ObjectType):
    yeah = graphene.String()


class Error(graphene.ObjectType):
    message = graphene.String()


class CreatePostResult(graphene.Union):
    class Meta:
        types = [Success, Error]


class CreatePost(graphene.Mutation):
    class Arguments:
        text = graphene.String(required=True)

    result = graphene.Field(CreatePostResult)

    def mutate(self, info, text):
        result = Success(yeah="yeah")

        return CreatePost(result=result)


class Mutations(graphene.ObjectType):
    create_post = CreatePost.Field()


class Query(graphene.ObjectType):
    succ = graphene.Field(Success)
    err = graphene.Field(Error)
    gevent = graphene.Field(Success)

    def resolve_succ(self, *args, **kwargs):
        return Success(yeah="hello world")

    def resolve_err(self, *args, **kwargs):
        #        import pdb; pdb.set_trace()
        return Error(message="oops")


@pytest.mark.skipif(not hasattr(graphql, "VERSION") or graphql.VERSION[0] >= 3, reason="Executor is reimplementated in graphql-core 3")
@pytest.mark.integrationtest
def test_create_post(instrument, elasticapm_client):
    query_string = """
    mutation {
      createPost(text: "Try this out") {
        result {
          __typename
        }
      }
    }
    """

    schema = graphene.Schema(query=Query, mutation=Mutations)

    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_graphene", "test"):
        result = schema.execute(query_string)
        assert not result.errors
        assert result.data["createPost"]["result"]["__typename"] == "Success"
    elasticapm_client.end_transaction("BillingView")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    expected_signatures = {
        "GraphQL.mutation __typename",
        "GraphQL.mutation createPost",
        "GraphQL.mutation result",
        "test_graphene",
    }
    assert {t["name"] for t in spans} == expected_signatures
    assert transactions[0]['name'] == 'GraphQL MUTATION createPost'


@pytest.mark.skipif(not hasattr(graphql, "VERSION") or graphql.VERSION[0] >= 3, reason="Executor is reimplementated in graphql-core 3")
@pytest.mark.integrationtest
def test_fetch_data(instrument, elasticapm_client):
    query_string = "{succ{yeah},err{__typename}}"

    schema = graphene.Schema(query=Query)

    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_graphene", "test"):
        result = schema.execute(query_string)
        assert result.data == {"succ": {"yeah": "hello world"}, "err": {"__typename": "Error"}}
    elasticapm_client.end_transaction("BillingView")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    expected_signatures = {
        "GraphQL.query __typename",
        "GraphQL.query err",
        "GraphQL.query succ",
        "test_graphene",
    }
    assert {t["name"] for t in spans} == expected_signatures
    assert transactions[0]['name'] == 'GraphQL QUERY succ+err'
