from tests.contrib.tornado import BaseTestClassTornado


class TestApiMcafee(BaseTestClassTornado):

    def test_error_handler(self):
        url = "/error"
        response = self.fetch(url, method='GET')
        print(response)
