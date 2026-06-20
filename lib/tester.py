# -*- coding: utf-8 -*-
import json
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

import requests
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

logger = logging.getLogger('meltor.tester')

# All HTTP methods useful for API testing
ALL_HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS',
                    'TRACE', 'CONNECT', 'PROPFIND', 'PROPPATCH', 'MKCOL',
                    'COPY', 'MOVE', 'LOCK', 'UNLOCK', 'SEARCH', 'SUBSCRIBE',
                    'UNSUBSCRIBE', 'NOTIFY', 'POLL', 'REPORT', 'VIEW']

# Keys that commonly contain API URLs in JSON responses
HATEOAS_KEYS = [
    'url', 'uri', 'href', 'link', 'links', 'endpoint', 'endpoints',
    'api', 'api_url', 'base_url', 'rest_url', 'graphql_url',
    'swagger_url', 'openapi_url', 'upload_url', 'download_url',
    'callback_url', 'webhook_url', 'redirect_url',
    'next', 'prev', 'first', 'last', 'self', 'edit',
    'create', 'post_url', 'get_url', 'put_url', 'delete_url',
    'patch_url', 'stream_url', 'ws_url', 'websocket_url',
    'sse_url', 'events_url', 'notification_url',
    'service_url', 'documentation', 'docs',
    'register_url', 'login_url', 'logout_url',
    'token_url', 'authorize_url', 'revoke_url',
    'introspection_url', 'userinfo_url', 'jwks_uri',
    'issuer', 'authorization_endpoint', 'token_endpoint',
    'userinfo_endpoint', 'end_session_endpoint',
    'revocation_endpoint', 'introspection_endpoint',
    'registration_endpoint', 'device_authorization_endpoint',
    'connection_url', 'cluster_url', 'node_url', 'proxy_url',
    'collection', 'items', 'self_link',
    's3_url', 'bucket_url', 'cdn_url', 'distribution_url',
    'resource', 'resources', 'route', 'routes',
    'action', 'actions', 'mutation', 'mutations',
    'query', 'queries', 'subscription', 'subscriptions',
    'signed_url', 'presigned_url', 'public_url', 'private_url',
    'data_url', 'export_url', 'import_url', 'sync_url',
    'backup_url', 'restore_url', 'deploy_url',
    'publish_url', 'archive_url',
]

URL_VALUE_KEYS = [
    'url', 'uri', 'href', 'link', 'endpoint', 'api_url', 'base_url',
    'rest_url', 'graphql_url', 'swagger_url', 'openapi_url',
    'callback_url', 'webhook_url', 'redirect_url', 'next', 'prev',
    'first', 'last', 'self', 'edit', 'action',
    'login_url', 'logout_url', 'register_url',
    'token_url', 'authorize_url', 'revoke_url',
    'introspection_url', 'userinfo_url', 'jwks_uri',
    'signed_url', 'presigned_url', 'upload_url', 'download_url',
    'ws_url', 'wss_url', 'websocket_url', 'sse_url', 'events_url',
    'notification_url', 'push_url', 'service_url',
    'connection_url', 'proxy_url', 'gateway_url',
]


class EndpointTester:
    def __init__(self, concurrency=15, timeout=10, base_url=None,
                 proxy=None, cookie=None, headers=None, graphql=False,
                 follow_redirects=True, extract_body_apis=True):
        self.concurrency = concurrency
        self.timeout = timeout
        self.base_url = base_url.rstrip('/') if base_url else None
        self.graphql = graphql
        self.follow_redirects = follow_redirects
        self.extract_body_apis = extract_body_apis
        self.discovered_from_responses = []

        self.session = requests.Session()
        headers_default = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        if headers:
            headers_default.update(headers)
        self.session.headers.update(headers_default)
        self.session.max_redirects = 5

        if cookie:
            self.session.headers.update({'Cookie': cookie})
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

    def test_endpoint(self, endpoint):
        url = endpoint.get('url', '')
        method = endpoint.get('method', 'GET').upper()

        if not url:
            return {**endpoint, 'status': None, 'working': False, 'error': 'No URL'}

        if url.startswith('/') and self.base_url:
            full_url = urljoin(self.base_url, url)
        else:
            full_url = url

        result = {
            **endpoint,
            'full_url': full_url,
            'tested_method': method,
            'status': None,
            'working': False,
            'error': None,
            'response_time': None,
            'content_type': None,
            'response_body_preview': None,
            'redirect_chain': [],
            'response_headers': {},
        }

        try:
            resp = self.session.request(
                method,
                full_url,
                timeout=self.timeout,
                allow_redirects=True,
                verify=False,
            )
            result['status'] = resp.status_code
            result['working'] = 200 <= resp.status_code < 300
            result['response_time'] = resp.elapsed.total_seconds()
            result['content_type'] = resp.headers.get('Content-Type', '')
            result['redirect_url'] = resp.url if resp.url != full_url else None
            result['response_headers'] = dict(resp.headers)

            # Record redirect chain
            if resp.history:
                result['redirect_chain'] = [
                    {'url': r.url, 'status': r.status_code} for r in resp.history
                ]

            # Extract more API endpoints from response body
            if self.extract_body_apis and resp.text and len(resp.text) < 500000:
                result['response_body_preview'] = resp.text[:2000]
                body_apis = self._extract_urls_from_body(resp.text, resp.headers.get('Content-Type', ''), full_url)
                if body_apis:
                    self.discovered_from_responses.extend(body_apis)

        except requests.ConnectionError:
            result['status'] = 0
            result['error'] = 'Connection refused'
        except requests.Timeout:
            result['status'] = 0
            result['error'] = 'Timeout'
        except requests.TooManyRedirects:
            result['status'] = 0
            result['error'] = 'Too many redirects'
        except requests.RequestException as e:
            result['status'] = 0
            result['error'] = str(e)[:100]
        except Exception as e:
            result['status'] = 0
            result['error'] = str(e)[:100]

        return result

    def _extract_urls_from_body(self, body_text, content_type, source_url):
        endpoints = []
        if not body_text:
            return endpoints

        # JSON bodies - look for HATEOAS links and URL-like values
        if 'json' in content_type or body_text.strip().startswith(('{', '[')):
            try:
                data = json.loads(body_text)
                self._hunt_json_for_links(data, source_url, endpoints, 0)
            except (json.JSONDecodeError, ValueError):
                pass

        # XML bodies
        if 'xml' in content_type or body_text.strip().startswith('<?xml'):
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(body_text, 'xml')
                for tag in soup.find_all(True):
                    for attr in ['href', 'src', 'action', 'location', 'uri']:
                        val = tag.get(attr, '')
                        if val and (val.startswith(('http://', 'https://', '/'))):
                            full = urljoin(source_url, val) if not val.startswith('http') else val
                            endpoints.append({
                                'url': full, 'method': 'GET',
                                'source': f'{source_url} (xml:{attr})',
                                'line': None, 'confidence': 'medium',
                                'info': 'tester-hateoas',
                            })
            except Exception:
                pass

        # HTML bodies with HATEOAS links
        if 'html' in content_type:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(body_text, 'html.parser')
                for link in soup.find_all('link', rel=lambda x: x and any(
                    r.lower() in ('service', 'api', 'rest', 'swagger', 'openapi',
                                  'docs', 'collection', 'next', 'prev', 'first',
                                  'last', 'edit', 'create', 'delete', 'update',
                                  'self', 'alternate', 'preconnect', 'dns-prefetch',
                                  'preload', 'prefetch', 'modulepreload')
                    for r in (x if isinstance(x, list) else [x])
                ) if x else False):
                    href = link.get('href', '')
                    rel = link.get('rel', [])
                    if href:
                        full = urljoin(source_url, href) if not href.startswith('http') else href
                        endpoints.append({
                            'url': full, 'method': 'GET',
                            'source': f'{source_url} (hateoas:{" ".join(rel) if isinstance(rel, list) else rel})',
                            'line': None, 'confidence': 'medium',
                            'info': 'tester-hateoas',
                        })
            except Exception:
                pass

        return endpoints

    def _hunt_json_for_links(self, data, source_url, endpoints, depth=0, max_depth=4):
        if depth > max_depth:
            return
        if isinstance(data, dict):
            for key, value in data.items():
                kl = key.lower()
                if kl in URL_VALUE_KEYS and isinstance(value, str):
                    if value.startswith(('http://', 'https://', '/')):
                        full = urljoin(source_url, value) if not value.startswith('http') else value
                        endpoints.append({
                            'url': full, 'method': 'GET',
                            'source': f'{source_url} (json:{key})',
                            'line': None, 'confidence': 'medium',
                            'info': 'tester-hateoas',
                        })
                if isinstance(value, (dict, list)):
                    self._hunt_json_for_links(value, source_url, endpoints, depth + 1, max_depth)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._hunt_json_for_links(item, source_url, endpoints, depth + 1, max_depth)
                elif isinstance(item, str) and item.startswith(('http://', 'https://', '/')):
                    full = urljoin(source_url, item) if not item.startswith('http') else item
                    endpoints.append({
                        'url': full, 'method': 'GET',
                        'source': f'{source_url} (json:array)',
                        'line': None, 'confidence': 'low',
                        'info': 'tester-hateoas',
                    })

    def test_graphql_introspection(self, endpoints):
        graphql_endpoints = [
            ep for ep in endpoints
            if 'graphql' in ep.get('url', '').lower()
        ]
        results = []
        for ep in graphql_endpoints:
            url = ep.get('full_url', ep.get('url', ''))
            if not url.startswith('http'):
                if self.base_url:
                    url = urljoin(self.base_url, url)
                else:
                    continue
            query = {'query': '{ __schema { types { name fields { name } } } }'}
            try:
                resp = self.session.post(
                    url,
                    json=query,
                    timeout=self.timeout,
                    verify=False,
                )
                if resp.status_code == 200 and 'data' in resp.text:
                    results.append({
                        **ep,
                        'full_url': url,
                        'graphql_introspection': True,
                        'status': resp.status_code,
                        'working': True,
                    })
                else:
                    results.append({
                        **ep,
                        'full_url': url,
                        'graphql_introspection': False,
                        'status': resp.status_code,
                        'working': False,
                    })
            except requests.RequestException as e:
                results.append({
                    **ep,
                    'full_url': url,
                    'graphql_introspection': False,
                    'error': str(e)[:100],
                })
        return results

    def test_all(self, endpoints):
        if not endpoints:
            return []

        tested = []
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {executor.submit(self.test_endpoint, ep): i for i, ep in enumerate(endpoints)}
            for future in as_completed(futures):
                try:
                    tested.append(future.result())
                except Exception as e:
                    idx = futures[future]
                    tested.append({**endpoints[idx], 'status': None, 'working': False, 'error': str(e)[:100]})

        if self.graphql:
            graphql_results = self.test_graphql_introspection(endpoints)
            seen_urls = {r.get('full_url', r.get('url', '')) for r in tested}
            for gr in graphql_results:
                gr_url = gr.get('full_url', gr.get('url', ''))
                if gr_url not in seen_urls:
                    tested.append(gr)

        # Sort: working first, then by status, then by URL
        tested.sort(key=lambda x: (
            0 if x.get('working') else 1,
            x.get('status') or 999,
            x.get('url', '')
        ))

        return tested

    def test_single_method(self, endpoints, method='GET'):
        modified = [{**ep, 'method': method} for ep in endpoints]
        return self.test_all(modified)

    def test_all_methods(self, endpoints):
        all_tested = []
        for method in ALL_HTTP_METHODS[:10]:  # Test first 10 methods by default
            modified = [{**ep, 'method': method} for ep in endpoints]
            tested = self.test_all(modified)
            all_tested.extend(tested)
        return all_tested
