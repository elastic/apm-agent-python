from elasticapm.utils import get_url_dict


def get_data_from_request(request):
    url = '{}://{}{}'.format(request.protocol, request.host, request.uri)
    data = {
        "headers": dict(**request.headers),
        "method": request.method,
        "socket": {
            "remote_address": request.remote_ip,
            "encrypted": request.protocol == 'https'
        },
        "cookies": dict(**request.cookies),
        "url": get_url_dict(url),
        "body": request.body
    }

    data["headers"].pop("Cookie", None)
    return data


def get_data_from_response(response):
    data = {"status_code": response.get_status()}
    if response._headers:
        data["headers"] = response._headers._dict
    return data
