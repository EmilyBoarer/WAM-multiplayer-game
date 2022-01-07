# copyright Emily Boarer 2020
# this is designed to replace some of the functionality of the requests library, 
# except without dependancies other than the python standard library

import http.client

class Response:
    def __init__(self, status, content):
        self.status = status
        self.content = content

def request(method, baseurl, path, timeout):
    conn = http.client.HTTPConnection(baseurl, timeout=timeout)
    conn.request(method,path)
    r1 = conn.getresponse()
    content = r1.read()
    conn.close()
    return Response(r1.status, str(content)[2:-1] )

def post(baseurl, path, timeout = 10):
    return request("POST", baseurl, path, timeout)

def get(baseurl, path, timeout = 10):
    return request("GET", baseurl, path, timeout)

def put(baseurl, path, timeout = 10):
    return request("PUT", baseurl, path, timeout)


