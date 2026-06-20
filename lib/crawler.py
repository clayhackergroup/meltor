# -*- coding: utf-8 -*-
import re
import time
import json
import random
import logging
import warnings
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup, Comment
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings('ignore', category=InsecureRequestWarning)

logger = logging.getLogger('meltor.crawler')

API_KEYWORDS_PATTERN = re.compile(
    r'/(?:api|v[1-9]|graphql|rest|swagger|openapi|auth|login|register|logout|token|oauth|'
    r'users?|posts?|comments?|todos?|items?|products?|orders?|payments?|webhooks?|'
    r'notifications?|messages?|search|upload|files?|media|sockets?|events?|stream|'
    r'health|status|config|settings?|preferences?|profiles?|avatars?|images?|docs?|help|'
    r'export|import|sync|backup|restore|deploy|publish|draft|archive|trash|'
    r'reviews?|ratings?|likes?|shares?|follows?|subscriptions?|'
    r'invoices?|receipts?|transactions?|balances?|wallets?|'
    r'organizations?|workspaces?|teams?|projects?|boards?|'
    r'tickets?|issues?|milestones?|sprints?|tasks?|'
    r'analytics?|reports?|dashboards?|metrics?|'
    r'notifications?|alerts?|webhooks?|callbacks?|'
    r'carts?|checkout?|shipping?|fulfillment?|'
    r'addresses?|contacts?|leads?|deals?|opportunities?|'
    r'documents?|attachments?|templates?|schemas?|'
    r'versions?|releases?|changelogs?|roadmaps?|'
    r'moderation|flags?|reports?|appeals?|'
    r'sso|saml|oidc|webauthn|mfa|2fa|'
    r'soap|odata|jsonrpc|xmlrpc|trpc|grpc|'
    r'webdav|caldav|carddav|'
    r'well-known|openid-configuration|oauth-authorization-server|'
    r'servers?|nodes?|clusters?|regions?|zones?|'
    r'subdomains?|domains?|dns|ssl|tls|certificates?|'
    r'functions?|triggers?|schedules?|crons?|'
    r'caches?|queues?|jobs?|tasks?|workers?)',
    re.IGNORECASE
)


class Crawler:
    def __init__(self, base_url, max_depth=3, max_pages=30, timeout=10, delay=0.2,
                 jitter=0, proxy=None, cookie=None, headers=None,
                 scope='same-domain', include=None, exclude=None,
                  wayback=False, deobfuscate=False, fuzz=False, deep=False,
                  crawl_apis=False, sitemap=True, robots=True, well_known=True,
                  source_maps=True, custom_paths=None,
                  dir_bust=True, dir_depth=2):
        self.base_url = base_url.rstrip('/')
        parsed = urlparse(self.base_url)
        self.domain = parsed.netloc
        self.scheme = parsed.scheme
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay
        self.jitter = jitter
        self.proxy = proxy
        self.scope = scope
        self.include = re.compile(include, re.IGNORECASE) if include else None
        self.exclude = re.compile(exclude, re.IGNORECASE) if exclude else None
        self.wayback = wayback
        self.deobfuscate = deobfuscate
        self.fuzz = fuzz
        self.deep = deep
        self.crawl_apis = crawl_apis
        self.sitemap = sitemap
        self.robots = robots
        self.well_known = well_known
        self.source_maps = source_maps
        self.custom_paths = custom_paths or []
        self.dir_bust = dir_bust
        self.dir_depth = dir_depth

        self.discovery_timeout = (2, 3)  # (connect, read) timeout for probe/discovery requests
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
        headers_default = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        if headers:
            headers_default.update(headers)
        self.session.headers.update(headers_default)
        self.session.verify = False

        if cookie:
            self.session.headers.update({'Cookie': cookie})
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

        self.visited_urls = set()
        self.visited_paths = set()
        self.pages = []
        self.js_files = []
        self.endpoints_from_html = []
        self.openapi_specs = []
        self.discovery_stats = {
            'robots_endpoints': 0,
            'sitemap_urls': 0,
            'well_known_endpoints': 0,
            'fuzzed_endpoints': 0,
            'openapi_specs': 0,
            'source_map_endpoints': 0,
            'csp_endpoints': 0,
            'link_header_endpoints': 0,
            'hateoas_endpoints': 0,
            'html_comment_endpoints': 0,
            'manifest_endpoints': 0,
            'service_worker_endpoints': 0,
            'response_body_endpoints': 0,
            'git_exposed': 0,
            'env_exposed': 0,
            'custom_endpoints': 0,
            'dir_bust_endpoints': 0,
        }

    def _rate_limit(self):
        if self.delay > 0:
            jitter_amount = random.uniform(0, self.jitter) if self.jitter > 0 else 0
            time.sleep(self.delay + jitter_amount)

    def _probe_concurrent(self, paths, timeout=(2, 3), max_workers=20):
        results = []
        url_map = {}
        for p in paths:
            u = p if p.startswith('http') else urljoin(self.base_url, p)
            url_map[p] = u
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            fut_map = {ex.submit(self.session.get, u, timeout=timeout): p for p, u in url_map.items()}
            for fut in as_completed(fut_map):
                try:
                    resp = fut.result()
                    results.append((fut_map[fut], url_map[fut_map[fut]], resp))
                except Exception:
                    pass
        return results

    def _in_scope(self, url):
        if not url:
            return False
        if self.scope == 'strict':
            normalized = self.normalize_url(url)
            base_normalized = self.normalize_url(self.base_url)
            if not normalized.startswith(base_normalized.rstrip('/')):
                return False
        else:
            if not self.is_same_domain(url):
                return False
        if self.include and not self.include.search(url):
            return False
        if self.exclude and self.exclude.search(url):
            return False
        return True

    def normalize_url(self, url):
        parsed = urlparse(url)
        path = parsed.path.rstrip('/') if parsed.path != '/' else parsed.path
        normalized = urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))
        return normalized

    def is_same_domain(self, url):
        parsed = urlparse(url)
        return parsed.netloc == self.domain or not parsed.netloc

    def resolve_url(self, href):
        if not href or href.startswith('#') or href.startswith('javascript:'):
            return None
        if href.startswith('//'):
            href = f'{self.scheme}:{href}'
        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ('http', 'https'):
            return None
        return absolute

    def resolve_path(self, path):
        if not path:
            return None
        if path.startswith('http'):
            return path if self._in_scope(path) else None
        return urljoin(self.base_url, path)

    # ═══════════════════════════════════════════════════════════════
    # 1. ROBOTS.TXT PARSING
    # ═══════════════════════════════════════════════════════════════

    def _fetch_robots_txt(self):
        if not self.robots:
            return []
        urls = []
        try:
            robots_url = urljoin(self.base_url, '/robots.txt')
            resp = self.session.get(robots_url, timeout=self.timeout)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    line = line.strip()
                    if line.lower().startswith('disallow:') or line.lower().startswith('allow:'):
                        path = line.split(':', 1)[1].strip()
                        if path and path != '/':
                            full = self.resolve_url(path)
                            if full and self._in_scope(full):
                                urls.append(full)
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        if sitemap_url:
                            sm_urls = self._parse_sitemap(sitemap_url)
                            urls.extend(sm_urls)
                    # Check for API hints in comments
                    if line.startswith('#') and ('api' in line.lower() or 'endpoint' in line.lower()):
                        api_match = re.search(r'(https?://[^\s]+)', line)
                        if api_match:
                            full = self.resolve_url(api_match.group(1))
                            if full and self._in_scope(full):
                                urls.append(full)
        except requests.RequestException:
            pass
        for url in urls:
            if self._is_api_like_path(url):
                self.endpoints_from_html.append({
                    'url': url, 'method': 'GET',
                    'source': f'{urljoin(self.base_url, "/robots.txt")} (robots)',
                    'line': None, 'confidence': 'medium',
                })
                self.discovery_stats['robots_endpoints'] += 1
        return urls

    # ═══════════════════════════════════════════════════════════════
    # 2. SITEMAP.XML PARSING
    # ═══════════════════════════════════════════════════════════════

    def _parse_sitemap(self, sitemap_url):
        urls = []
        try:
            resp = self.session.get(sitemap_url, timeout=self.timeout)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for loc in soup.find_all('loc'):
                    loc_url = loc.text.strip()
                    if self._in_scope(loc_url):
                        urls.append(loc_url)
                for sitemap_tag in soup.find_all('sitemap'):
                    loc = sitemap_tag.find('loc')
                    if loc:
                        nested = self._parse_sitemap(loc.text.strip())
                        urls.extend(nested)
        except requests.RequestException:
            pass
        for url in urls:
            if self._is_api_like_path(url):
                self.endpoints_from_html.append({
                    'url': url, 'method': 'GET',
                    'source': f'{sitemap_url} (sitemap)',
                    'line': None, 'confidence': 'medium',
                })
                self.discovery_stats['sitemap_urls'] += 1
        return urls

    def _fetch_sitemaps(self):
        urls = []
        common_sitemaps = [
            '/sitemap.xml', '/sitemap_index.xml', '/sitemap/',
            '/wp-sitemap.xml', '/sitemaps/sitemap.xml',
            '/sitemap/sitemap.xml', '/sitemap-index.xml',
            '/sitemap.xml.gz', '/sitemap_index.xml.gz',
        ]
        for sm_path in common_sitemaps:
            sm_url = urljoin(self.base_url, sm_path)
            sm_urls = self._parse_sitemap(sm_url)
            urls.extend(sm_urls)
        return urls

    # ═══════════════════════════════════════════════════════════════
    # 3. .WELL-KNOWN DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    WELL_KNOWN_PATHS = [
        # Security
        '/.well-known/security.txt', '/.well-known/security',
        # OAuth / OIDC
        '/.well-known/oauth-authorization-server', '/.well-known/openid-configuration',
        '/.well-known/openid-federation',
        # Web App
        '/.well-known/change-password', '/.well-known/assetlinks.json',
        '/.well-known/apple-app-site-association',
        # Security & Identity
        '/.well-known/keybase.txt', '/.well-known/matrix/server',
        '/.well-known/matrix/client', '/.well-known/webfinger',
        '/.well-known/host-meta', '/.well-known/host-meta.json',
        '/.well-known/nodeinfo',
        # Email security
        '/.well-known/mta-sts.txt', '/.well-known/autoconfig/mail/config-v1.1.xml',
        '/.well-known/autodiscover/autodiscover.xml',
        # PGP / Security
        '/.well-known/openpgpkey/hu/', '/.well-known/dnt-policy.txt',
        '/.well-known/pki-validation/',
        # SSH
        '/.well-known/sshfp',
        # Two-step verification
        '/.well-known/appspecific.json',
        # Payment
        '/.well-known/posh/', '/.well-known/posh/github.json',
        # Tor
        '/.well-known/tor-signed-headers.txt',
        # General / API discovery
        '/.well-known/api', '/.well-known/apidoc',
        '/.well-known/swagger', '/.well-known/openapi',
        '/.well-known/graphql', '/.well-known/rest',
        # Social
        '/.well-known/webmention', '/.well-known/social',
        # ActivityPub
        '/.well-known/webfinger?resource=acct:relay@localhost',
        # Time
        '/.well-known/timezone',
    ]

    def _probe_well_known(self):
        if not self.well_known:
            return []
        endpoints = []
        for wk_path, url, resp in self._probe_concurrent(self.WELL_KNOWN_PATHS, timeout=self.timeout):
            if resp.status_code not in (200, 204):
                continue
            content_type = resp.headers.get('Content-Type', '')
            ep = {
                'url': wk_path, 'method': 'GET',
                'source': '.well-known discovery',
                'line': None, 'confidence': 'high',
            }
            self.endpoints_from_html.append(ep)
            endpoints.append(ep)
            self.discovery_stats['well_known_endpoints'] += 1
            if 'json' in content_type:
                try:
                    body = resp.json()
                    self._hunt_json_for_apis(body, '.well-known', url)
                except (json.JSONDecodeError, ValueError):
                    pass
            if 'openid-configuration' in wk_path or 'oauth' in wk_path:
                try:
                    body = resp.json()
                    for key in ['issuer', 'authorization_endpoint', 'token_endpoint',
                                'userinfo_endpoint', 'jwks_uri', 'registration_endpoint',
                                'end_session_endpoint', 'check_session_iframe',
                                'revocation_endpoint', 'introspection_endpoint']:
                        val = body.get(key)
                        if val and isinstance(val, str) and self._in_scope(val):
                            self.endpoints_from_html.append({
                                'url': val, 'method': 'GET',
                                'source': f'{wk_path} (oidc)',
                                'line': None, 'confidence': 'high',
                            })
                except (json.JSONDecodeError, ValueError, AttributeError):
                    pass
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 4. COMPREHENSIVE OPENAPI / API SPEC DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    API_SPEC_PATHS = [
        # OpenAPI / Swagger (JSON)
        '/openapi.json', '/swagger.json', '/api-docs', '/api/swagger.json',
        '/swagger/v1/swagger.json', '/swagger/v2/swagger.json', '/swagger/v3/swagger.json',
        '/api/openapi.json', '/api/v1/openapi.json', '/api/v2/openapi.json', '/api/v3/openapi.json',
        '/v1/openapi.json', '/v2/openapi.json', '/v3/openapi.json',
        '/v1/api-docs', '/v2/api-docs', '/v3/api-docs',
        '/api/swagger/v1/swagger.json', '/api/swagger/v2/swagger.json',
        '/swagger-resources', '/swagger-resources/',
        '/api/v1/swagger.json', '/api/v2/swagger.json',
        '/v1/swagger.json', '/v2/swagger.json',
        '/spec.json', '/spec/openapi.json',
        '/api/spec.json', '/api-spec.json',
        '/.well-known/openapi.json', '/.well-known/swagger.json',
        '/docs/swagger.json', '/docs/openapi.json',
        '/api/documentation/swagger.json',
        '/api/rest/v1/openapi.json', '/api/rest/v2/openapi.json',
        '/rest/v1/swagger.json', '/rest/v2/swagger.json',
        '/api/v1/documentation', '/api/v2/documentation',
        '/documentation/swagger.json', '/documentation/openapi.json',
        '/api/docs', '/api/docs/', '/api/documentation',
        # OpenAPI / Swagger (YAML)
        '/openapi.yaml', '/openapi.yml', '/swagger.yaml', '/swagger.yml',
        '/api/openapi.yaml', '/api/openapi.yml',
        '/v1/openapi.yaml', '/v1/openapi.yml',
        '/api/v1/openapi.yaml', '/api/v1/openapi.yml',
        '/spec.yaml', '/spec.yml',
        '/api/spec.yaml', '/api/spec.yml',
        '/docs/api-docs.yaml', '/docs/api-docs.yml',
        '/api/docs.yaml', '/api/docs.yml',
        # RAML
        '/api.raml', '/api/v1/api.raml', '/api/v2/api.raml',
        '/docs/api.raml', '/raml/api.raml',
        '/api/api.raml',
        '/v1/api.raml', '/v2/api.raml',
        # API Blueprint
        '/api.apib', '/api/v1/api.apib',
        '/docs/api.apib', '/blueprint.apib',
        '/api.apib.html',
        # AsyncAPI
        '/asyncapi.json', '/asyncapi.yaml', '/asyncapi.yml',
        '/api/asyncapi.json', '/api/asyncapi.yaml',
        '/docs/asyncapi.json',
        # I/O Docs
        '/io-docs', '/api/io-docs',
        # WSDL (SOAP)
        '/service.wsdl', '/wsdl', '/api.wsdl',
        '/api/service.wsdl', '/soap/service.wsdl',
        '/wsdl/service.wsdl', '/services.wsdl',
        '?wsdl', '/endpoint.wsdl',
        '/v1/service.wsdl', '/v2/service.wsdl',
        # WADL
        '/application.wadl', '/api/application.wadl',
        '/v1/application.wadl',
        # Postman collections
        '/postman.json', '/postman_collection.json',
        '/api/postman.json', '/api/postman_collection.json',
        '/docs/postman.json', '/export/postman.json',
        '/collections/postman.json',
        '/api/v1/postman.json', '/api/v2/postman.json',
        # GraphQL introspection (common paths)
        '/graphql', '/graphql/console', '/graphiql', '/graphiql/',
        '/api/graphql', '/v1/graphql', '/v2/graphql', '/v3/graphql',
        '/gql', '/api/gql', '/query', '/api/query',
        '/api/v1/graphql', '/api/v2/graphql',
        '/graphql/explorer', '/graphql-playground',
        '/api/graphiql', '/graphql/graphiql',
        '/graphql/schema.json', '/graphql/schema',
        '/v1/graphql/schema', '/api/graphql/schema',
        '/api/graphql/schema.json',
        # gRPC-web
        '/grpc', '/grpc.web', '/api/grpc',
        '/grpc/reflection', '/grpc.reflection',
        '/api/grpc/reflection',
    ]

    def _discover_api_specs(self):
        endpoints = []
        for api_path, url, resp in self._probe_concurrent(self.API_SPEC_PATHS, timeout=self.timeout):
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get('Content-Type', '')
            if 'json' in content_type or api_path.endswith('.json'):
                try:
                    spec = resp.json()
                    parsed = self._parse_openapi_json(spec, url)
                    endpoints.extend(parsed)
                    self.endpoints_from_html.extend(parsed)
                    self.openapi_specs.append({'url': url, 'type': 'openapi', 'endpoints': parsed})
                    self.discovery_stats['openapi_specs'] += 1
                    self.discovery_stats['openapi_endpoints'] = self.discovery_stats.get('openapi_endpoints', 0) + len(parsed)
                except json.JSONDecodeError:
                    pass
            else:
                text = resp.text
                parsed = self._parse_openapi_yaml(text, url)
                if parsed:
                    endpoints.extend(parsed)
                    self.endpoints_from_html.extend(parsed)
                    self.openapi_specs.append({'url': url, 'type': 'openapi_yaml', 'endpoints': parsed})
                    self.discovery_stats['openapi_specs'] += 1
                    self.discovery_stats['openapi_endpoints'] = self.discovery_stats.get('openapi_endpoints', 0) + len(parsed)
                if 'postman' in api_path.lower() or content_type == 'application/json':
                    self._parse_postman(text, url, endpoints)
                if api_path.endswith('.wsdl') or 'wsdl' in api_path:
                    self._parse_wsdl(text, url, endpoints)
        return endpoints

    def _parse_postman(self, text, source_url, endpoints):
        try:
            data = json.loads(text)
            items = data.get('item', []) if isinstance(data, dict) else []
            if isinstance(data, list):
                items = data
            self._walk_postman_items(items, source_url, endpoints)
        except (json.JSONDecodeError, AttributeError):
            pass

    def _walk_postman_items(self, items, source_url, endpoints):
        for item in items:
            if isinstance(item, dict):
                if 'item' in item:
                    self._walk_postman_items(item['item'], source_url, endpoints)
                request = item.get('request', {})
                if request:
                    url_info = request.get('url', {})
                    if isinstance(url_info, dict):
                        url_str = url_info.get('raw', '')
                    elif isinstance(url_info, str):
                        url_str = url_info
                    else:
                        url_str = ''
                    if not url_str:
                        url_str = request.get('url', '')
                    method = request.get('method', 'GET').upper()
                    if url_str and self._in_scope(url_str):
                        ep = {
                            'url': url_str, 'method': method,
                            'source': f'{source_url} (postman)',
                            'line': None, 'confidence': 'high',
                        }
                        endpoints.append(ep)
                        self.endpoints_from_html.append(ep)

    def _parse_wsdl(self, text, source_url, endpoints):
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'xml')
            for service in soup.find_all('service'):
                for port in service.find_all('port'):
                    address = port.find('address')
                    if address and address.get('location'):
                        loc = address['location']
                        if self._in_scope(loc):
                            ep = {
                                'url': loc, 'method': 'POST',
                                'source': f'{source_url} (wsdl)',
                                'line': None, 'confidence': 'high',
                            }
                            endpoints.append(ep)
                            self.endpoints_from_html.append(ep)
            for binding in soup.find_all('binding'):
                for operation in binding.find_all('operation'):
                    op_name = operation.get('name', '')
                    ep = {
                        'url': source_url, 'method': 'POST',
                        'source': f'{source_url} (wsdl:{op_name})',
                        'line': None, 'confidence': 'high',
                    }
                    endpoints.append(ep)
                    self.endpoints_from_html.append(ep)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # 5. SOURCE MAP DISCOVERY
    # ═══════════════════════════════════════════════════════════════

    def _check_source_maps(self):
        if not self.source_maps:
            return []
        endpoints = []
        for js in self.js_files:
            js_url = js.get('url', '')
            content = js.get('content', '')
            # Check for sourceMappingURL comment
            sm_matches = re.findall(r'/[/#]\s*sourceMappingURL\s*=\s*([^\s]+)', content)
            for sm_match in sm_matches:
                sm_url = self.resolve_url(sm_match) if not sm_match.startswith('http') else sm_match
                if sm_url and self._in_scope(sm_url):
                    try:
                        sm_resp = self.session.get(sm_url, timeout=self.timeout)
                        if sm_resp.status_code == 200:
                            try:
                                sm_data = sm_resp.json()
                                sources = sm_data.get('sources', [])
                                for src in sources:
                                    if self._is_api_like_path(src):
                                        ep = {
                                            'url': src, 'method': 'GET',
                                            'source': f'{sm_url} (sourcemap)',
                                            'line': None, 'confidence': 'high',
                                        }
                                        endpoints.append(ep)
                                        self.endpoints_from_html.append(ep)
                                        self.discovery_stats['source_map_endpoints'] += 1
                            except json.JSONDecodeError:
                                pass
                    except requests.RequestException:
                        pass
            # Also check if the JS URL + .map works
            map_url = js_url + '.map'
            if self._in_scope(map_url) and map_url not in self.visited_urls:
                try:
                    resp = self.session.get(map_url, timeout=self.timeout)
                    if resp.status_code == 200 and 'json' in resp.headers.get('Content-Type', ''):
                        sm_data = resp.json()
                        sources = sm_data.get('sources', [])
                        for src in sources:
                            if self._is_api_like_path(src):
                                ep = {
                                    'url': src, 'method': 'GET',
                                    'source': f'{map_url} (sourcemap)',
                                    'line': None, 'confidence': 'high',
                                }
                                endpoints.append(ep)
                                self.endpoints_from_html.append(ep)
                                self.discovery_stats['source_map_endpoints'] += 1
                except requests.RequestException:
                    pass
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 6. API PATH FUZZING
    # ═══════════════════════════════════════════════════════════════

    FUZZ_PATHS = [
        # Common API base paths
        '/api', '/api/v1', '/api/v2', '/api/v3', '/api/v4', '/api/v5',
        '/v1', '/v2', '/v3', '/v4', '/v5',
        '/rest', '/rest/v1', '/rest/v2', '/rest/v3',
        '/api/rest', '/api/rest/v1', '/api/rest/v2',
        '/graphql', '/graphql/v1', '/graphql/v2',
        '/internal', '/internal/api', '/internal/v1', '/internal/v2',
        '/private', '/private/api', '/private/v1', '/private/v2',
        '/public', '/public/api', '/public/v1', '/public/v2',
        '/admin', '/admin/api', '/admin/rest', '/admin/v1', '/admin/v2',
        '/management', '/management/api', '/manage', '/manage/api',
        '/dashboard/api', '/dashboard/v1',
        '/api/dashboard', '/api/console',
        '/api/admin', '/api/internal',
        '/api/public', '/api/private',
        '/api/v1/public', '/api/v1/private',
        '/api/v1/internal', '/api/v1/admin',
        '/api/v2/public', '/api/v2/private',
        # Cloud / K8s paths
        '/api/v1/namespaces', '/api/v1/pods', '/api/v1/services',
        '/api/v1/deployments', '/api/v1/configmaps', '/api/v1/secrets',
        '/api/v1/nodes', '/api/v1/endpoints',
        '/api/v1/healthz', '/api/v1/version',
        '/healthz', '/readyz', '/livez',
        '/metrics', '/api/metrics',
        '/swagger/api', '/swagger/api/v1',
        # Common resources (GET)
        '/api/users', '/api/posts', '/api/comments', '/api/items',
        '/api/products', '/api/orders', '/api/payments',
        '/api/auth/login', '/api/auth/register', '/api/auth/logout',
        '/api/auth/refresh', '/api/auth/token', '/api/auth/verify',
        '/api/auth/me', '/api/auth/session', '/api/auth/password',
        '/api/auth/otp', '/api/auth/mfa', '/api/auth/2fa',
        '/api/auth/webauthn', '/api/auth/sso',
        '/api/health', '/api/status', '/api/ping', '/api/version',
        '/api/config', '/api/settings',
        '/api/search', '/api/upload', '/api/download',
        '/api/notifications', '/api/messages',
        '/api/webhooks', '/api/webhook',
        '/api/analytics', '/api/metrics', '/api/tracking',
        '/api/export', '/api/import',
        '/api/sync', '/api/backup', '/api/restore',
        '/api/tasks', '/api/jobs', '/api/workers',
        '/api/sse', '/api/events', '/api/stream', '/api/poll',
        '/api/websocket', '/api/ws',
        '/api/files', '/api/media', '/api/images', '/api/videos',
        '/api/documents', '/api/attachments', '/api/avatars',
        '/api/organizations', '/api/workspaces', '/api/teams',
        '/api/projects', '/api/boards', '/api/tickets',
        '/api/reports', '/api/dashboards',
        '/api/templates', '/api/schemas',
        '/api/versions', '/api/releases', '/api/changelog',
        '/api/invoices', '/api/receipts', '/api/transactions',
        '/api/addresses', '/api/contacts',
        '/api/leads', '/api/deals', '/api/opportunities',
        '/api/subscriptions', '/api/plans', '/api/pricing',
        '/api/notifications/sse', '/api/notifications/push',
        '/api/notifications/email', '/api/notifications/sms',
        '/api/comments', '/api/likes', '/api/shares',
        '/api/follows', '/api/subscribers',
        '/api/invitations', '/api/invites',
        '/api/feed', '/api/timeline', '/api/activity',
        '/api/bookmarks', '/api/favorites',
        '/api/votes', '/api/ratings', '/api/reviews',
        '/api/tags', '/api/categories',
        '/api/playlists', '/api/albums', '/api/collections',
        '/api/devices', '/api/sessions', '/api/connections',
        '/api/geo', '/api/locations', '/api/places',
        '/api/currencies', '/api/countries', '/api/languages',
        '/api/themes', '/api/widgets', '/api/plugins',
        '/api/modules', '/api/extensions',
        '/api/translations', '/api/localization',
        '/api/permissions', '/api/roles', '/api/groups',
        '/api/audit', '/api/audit-log', '/api/activity-log',
        '/api/logs', '/api/debug', '/api/trace',
        '/api/banners', '/api/announcements', '/api/news',
        '/api/coupons', '/api/discounts', '/api/promotions',
        '/api/referrals', '/api/affiliates',
        '/api/gateways', '/api/providers', '/api/integrations',
        '/api/sources', '/api/destinations',
        '/api/pipelines', '/api/workflows', '/api/automations',
        '/api/rules', '/api/policies', '/api/constraints',
        '/api/limits', '/api/thresholds',
        '/api/alerts', '/api/alarms', '/api/incidents',
        '/api/slas', '/api/slos', '/api/slis',
        '/api/costs', '/api/budgets', '/api/billing',
        '/api/wallets', '/api/balances', '/api/ledgers',
        '/api/withdrawals', '/api/deposits',
        '/api/refunds', '/api/disputes', '/api/chargebacks',
        '/api/taxes', '/api/fees', '/api/commissions',
        # GraphQL variants
        '/graphql/private', '/graphql/public', '/graphql/admin',
        '/graphql/internal', '/graphql/explorer',
        '/api/graphql/private', '/api/graphql/public',
        '/api/graphql/admin', '/api/graphql/internal',
        '/admin/graphql', '/admin/api/graphql',
        '/internal/graphql', '/internal/api/graphql',
        '/graphql/batch', '/graphql/subscriptions',
        # SOAP
        '/soap', '/soap/', '/soap/v1', '/soap/v2',
        '/api/soap', '/api/soap/v1',
        '/services', '/services/',
        '/ws', '/ws/',
        # gRPC-web
        '/grpc', '/grpc/', '/grpc/v1', '/grpc/v2',
        '/api/grpc', '/api/grpc/v1',
        '/grpc.web', '/api/grpc.web',
        # WebDAV
        '/webdav', '/dav', '/remote.php/dav',
        '/remote/webdav', '/remote.php/webdav',
        # CalDAV / CardDAV
        '/caldav', '/carddav', '/remote.php/caldav',
        # OData
        '/odata', '/api/odata', '/odata/v1', '/odata/v2', '/odata/v4',
        # JSON-RPC / XML-RPC
        '/jsonrpc', '/api/jsonrpc', '/api/rpc',
        '/xmlrpc', '/api/xmlrpc',
        '/rpc', '/api/rpc', '/rpc/v1',
        # tRPC
        '/trpc', '/api/trpc', '/trpc/v1',
        # Serverless function paths
        '/api/functions', '/api/triggers', '/api/tasks',
        '/functions', '/triggers',
        '/api/hooks', '/api/callbacks',
        '/api/jobs', '/api/queues',
        '/api/v1/functions', '/api/v1/triggers',
        # CMS-specific
        '/api/pages', '/api/posts', '/api/articles',
        '/api/menus', '/api/navigation',
        '/api/blocks', '/api/layouts',
        '/api/custom-fields', '/api/acf',
        '/api/options', '/api/site-options',
        '/api/seo', '/api/redirects',
        '/api/forms', '/api/submissions',
        '/api/snippets', '/api/shortcodes',
        '/api/media', '/api/assets', '/api/thumbnails',
        # Framework-specific
        '/api/routes', '/api/actions', '/api/loaders',
        '/api/callback', '/api/webhook/callback',
        '/api/hooks', '/api/middleware', '/api/filters',
        '/api/__test', '/api/__debug', '/api/__admin',
        '/api/__internal', '/api/__private',
        '/api/db', '/api/database', '/api/query',
        '/api/cache', '/api/queue', '/api/redis',
        '/api/email', '/api/sms', '/api/push',
        '/api/storage', '/api/s3', '/api/blob', '/api/fs',
        '/api/realtime', '/api/presence',
        '/api/moderation', '/api/flags', '/api/reports',
        '/api/inventory', '/api/stock', '/api/warehouses',
        '/api/carts', '/api/checkout', '/api/orders',
        '/api/shipping', '/api/tracking', '/api/delivery',
        '/api/fulfillment', '/api/returns',
        '/api/gdpr', '/api/consent', '/api/privacy',
        '/api/oauth', '/api/oauth2', '/api/openid',
        '/api/sso', '/api/saml', '/api/oidc',
        '/api/2fa', '/api/mfa', '/api/totp',
        '/api/captcha', '/api/recaptcha', '/api/verify',
        '/api/encryption', '/api/keys', '/api/certificates',
        '/api/notifications/push',
        '/api/notifications/email',
        '/api/notifications/sms',
        '/api/notifications/webhook',
        # Sub-resource paths
        '/api/users/me', '/api/users/me/profile',
        '/api/users/me/preferences', '/api/users/me/settings',
        '/api/users/me/notifications',
        '/api/users/me/sessions', '/api/users/me/devices',
        '/api/users/me/security', '/api/users/me/activity',
        '/api/users/me/billing', '/api/users/me/subscription',
        # Payment / commerce
        '/api/checkout/sessions', '/api/checkout/cart',
        '/api/payments/methods', '/api/payments/intents',
        '/api/payments/confirm', '/api/payments/refund',
        '/api/subscriptions/trials',
        '/api/invoices/upcoming',
        # Search / discovery
        '/api/search/suggest', '/api/search/autocomplete',
        '/api/discover', '/api/explore', '/api/trending',
        '/api/recommendations', '/api/suggestions',
        # Web3 / crypto
        '/api/web3', '/api/blockchain', '/api/ethereum',
        '/api/nfts', '/api/tokens', '/api/contracts',
        '/api/wallets', '/api/transactions',
        # AI / ML
        '/api/ai', '/api/ml', '/api/models',
        '/api/predict', '/api/inference',
        '/api/embeddings', '/api/vectors',
        '/api/completions', '/api/chat',
        '/api/chat/completions',
        '/api/agents', '/api/assistants',
    ]

    def _fuzz_paths(self):
        if not self.fuzz:
            return []
        endpoints = []
        # Filter paths not already visited
        fuzz_set = [p for p in self.FUZZ_PATHS if p not in self.visited_paths]
        self.visited_paths.update(fuzz_set)
        for fuzz_path, url, resp in self._probe_concurrent(fuzz_set, timeout=self.timeout):
            if resp.status_code == 404 or resp.status_code == 0:
                continue
            ep = {
                'url': fuzz_path, 'method': 'GET',
                'source': 'fuzzing',
                'line': None, 'confidence': 'medium',
            }
            endpoints.append(ep)
            self.endpoints_from_html.append(ep)
            self.discovery_stats['fuzzed_endpoints'] += 1
            if self.deep or self.crawl_apis:
                body = self._extract_endpoints_from_body(resp.text, resp.headers.get('Content-Type', ''), url)
                self.endpoints_from_html.extend(body)
                self.discovery_stats['response_body_endpoints'] += len(body)
                endpoints.extend(body)
        return endpoints

    def _probe_custom_paths(self):
        if not self.custom_paths:
            return []
        endpoints = []
        probe_set = [p for p in self.custom_paths if p not in self.visited_paths]
        self.visited_paths.update(probe_set)
        for path, url, resp in self._probe_concurrent(probe_set, timeout=self.timeout):
            if resp.status_code == 404 or resp.status_code == 0:
                continue
            ep = {
                'url': path, 'method': 'GET',
                'source': 'custom_endpoints',
                'line': None, 'confidence': 'high',
            }
            endpoints.append(ep)
            self.endpoints_from_html.append(ep)
            self.discovery_stats['custom_endpoints'] = self.discovery_stats.get('custom_endpoints', 0) + 1
            if self.deep or self.crawl_apis:
                body = self._extract_endpoints_from_body(resp.text, resp.headers.get('Content-Type', ''), url)
                self.endpoints_from_html.extend(body)
                self.discovery_stats['response_body_endpoints'] += len(body)
                endpoints.extend(body)
        return endpoints

    API_RESOURCE_NAMES = [
        'users', 'posts', 'comments', 'items', 'products', 'orders', 'payments',
        'auth/login', 'auth/register', 'auth/logout', 'auth/refresh', 'auth/token',
        'auth/verify', 'auth/me', 'auth/session', 'auth/password',
        'health', 'status', 'ping', 'version',
        'config', 'settings', 'search', 'upload', 'download',
        'notifications', 'messages', 'inbox', 'outbox',
        'webhooks', 'webhook', 'callback',
        'analytics', 'metrics', 'tracking',
        'export', 'import', 'sync', 'backup', 'restore',
        'tasks', 'jobs', 'workers',
        'sse', 'events', 'stream', 'poll',
        'websocket', 'ws',
        'files', 'media', 'images', 'videos', 'documents', 'attachments', 'avatars',
        'organizations', 'workspaces', 'teams',
        'projects', 'boards', 'tickets',
        'reports', 'dashboards',
        'templates', 'schemas',
        'versions', 'releases', 'changelog',
        'invoices', 'receipts', 'transactions',
        'addresses', 'contacts',
        'leads', 'deals', 'opportunities',
        'subscriptions', 'plans', 'pricing',
        'likes', 'shares', 'follows', 'subscribers',
        'invitations', 'invites',
        'feed', 'timeline', 'activity',
        'bookmarks', 'favorites',
        'votes', 'ratings', 'reviews',
        'tags', 'categories',
        'playlists', 'albums', 'collections',
        'devices', 'sessions', 'connections',
        'geo', 'locations', 'places',
        'currencies', 'countries', 'languages',
        'themes', 'widgets', 'plugins', 'modules', 'extensions',
        'translations', 'localization',
        'permissions', 'roles', 'groups',
        'audit', 'audit-log', 'activity-log', 'logs',
        'banners', 'announcements', 'news',
        'coupons', 'discounts', 'promotions',
        'referrals', 'affiliates',
        'gateways', 'providers', 'integrations',
        'pipelines', 'workflows', 'automations',
        'rules', 'policies', 'constraints', 'limits',
        'alerts', 'alarms', 'incidents',
        'costs', 'budgets', 'billing',
        'wallets', 'balances', 'ledgers',
        'withdrawals', 'deposits',
        'refunds', 'disputes', 'chargebacks',
        'taxes', 'fees', 'commissions',
        'posts', 'pages', 'articles',
        'menus', 'navigation', 'blocks', 'layouts',
        'custom-fields', 'options',
        'seo', 'redirects',
        'forms', 'submissions',
        'snippets', 'shortcodes',
        'assets', 'thumbnails',
        'routes', 'actions', 'loaders',
        'hooks', 'middleware', 'filters',
        'db', 'database', 'query',
        'cache', 'queue', 'redis',
        'email', 'sms', 'push',
        'storage', 's3', 'blob', 'fs',
        'realtime', 'presence',
        'moderation', 'flags',
        'inventory', 'stock', 'warehouses',
        'carts', 'checkout',
        'shipping', 'delivery',
        'fulfillment', 'returns',
        'gdpr', 'consent', 'privacy',
        'oauth', 'oauth2', 'openid',
        'sso', 'saml', 'oidc',
        '2fa', 'mfa', 'totp',
        'captcha', 'recaptcha', 'verify',
        'encryption', 'keys', 'certificates',
        'checkout/sessions', 'checkout/cart',
        'payments/methods', 'payments/intents',
        'payments/confirm',
        'subscriptions/trials',
        'search/suggest', 'search/autocomplete',
        'discover', 'explore', 'trending',
        'recommendations', 'suggestions',
        'web3', 'blockchain',
        'nfts', 'tokens', 'contracts',
        'ai', 'ml', 'models',
        'predict', 'inference',
        'embeddings', 'vectors', 'completions',
        'chat', 'chat/completions',
        'agents', 'assistants',
    ]

    def _directory_api_busting(self):
        if not self.dir_bust:
            return []
        all_endpoints = []
        # Collect initial "directory roots" from all discovered paths
        current_roots = set()
        for ep in self.endpoints_from_html:
            path = ep.get('url', '')
            if path.startswith('/') and not any(path.endswith(ext) for ext in
                ('.js','.css','.png','.jpg','.jpeg','.gif','.svg','.ico',
                 '.json','.xml','.yaml','.yml','.html','.php','.asp','.aspx',
                 '.woff','.woff2','.ttf','.eot','.mp4','.mp3','.pdf','.zip','.gz')):
                parts = path.rstrip('/').split('/')
                for i in range(2, len(parts) + 1):
                    parent = '/'.join(parts[:i])
                    if parent and parent not in self.visited_paths:
                        current_roots.add(parent)

        if not current_roots:
            return all_endpoints

        bust_depth = self.dir_depth
        for level in range(bust_depth):
            if not current_roots:
                break
            # Generate sub-paths for current roots
            sub_paths = []
            for root in sorted(current_roots, key=len, reverse=True):
                for resource in self.API_RESOURCE_NAMES:
                    sub = f'{root}/{resource}'
                    if sub not in self.visited_paths:
                        sub_paths.append(sub)
                for resource in ['users/me', 'users/me/profile', 'users/me/settings',
                                 'users/me/sessions', 'users/me/devices',
                                 'users/me/billing', 'users/me/subscription']:
                    sub = f'{root}/{resource}'
                    if sub not in self.visited_paths:
                        sub_paths.append(sub)

            if not sub_paths:
                break

            self.visited_paths.update(sub_paths)
            probe_set = sub_paths[:600]
            found = []
            for path, url, resp in self._probe_concurrent(probe_set, timeout=self.timeout):
                if resp.status_code == 404 or resp.status_code == 0:
                    continue
                ep = {
                    'url': path, 'method': 'GET',
                    'source': 'dir_busting',
                    'line': None, 'confidence': 'medium',
                }
                found.append(ep)
                all_endpoints.append(ep)
                self.endpoints_from_html.append(ep)
                self.discovery_stats['dir_bust_endpoints'] += 1
                if self.deep or self.crawl_apis:
                    body = self._extract_endpoints_from_body(resp.text, resp.headers.get('Content-Type', ''), url)
                    self.endpoints_from_html.extend(body)
                    self.discovery_stats['response_body_endpoints'] += len(body)
                    all_endpoints.extend(body)

            # Build next level roots from newly found paths (only if more levels remain)
            next_roots = set()
            if level + 1 < bust_depth:
                for ep in found:
                    path = ep.get('url', '')
                    if not any(path.endswith(ext) for ext in
                        ('.json','.xml','.yaml','.yml','.html','.php','.asp','.aspx')):
                        parts = path.rstrip('/').split('/')
                        for i in range(2, len(parts) + 1):
                            parent = '/'.join(parts[:i])
                            if parent and parent not in self.visited_paths and parent != root:
                                next_roots.add(parent)
            current_roots = next_roots

        return all_endpoints

    # ═══════════════════════════════════════════════════════════════
    # 7. RESPONSE BODY API EXTRACTION (HATEOAS + JSON/XML)
    # ═══════════════════════════════════════════════════════════════

    def _extract_endpoints_from_body(self, body_text, content_type, source_url):
        endpoints = []
        if not body_text:
            return endpoints

        # JSON bodies
        if 'json' in content_type or body_text.strip().startswith(('{', '[')):
            try:
                data = json.loads(body_text)
                urls = self._hunt_json_for_apis(data, source_url, source_url)
                endpoints.extend(urls)
            except (json.JSONDecodeError, ValueError):
                pass

        # XML bodies
        if 'xml' in content_type or body_text.strip().startswith('<?xml'):
            try:
                soup = BeautifulSoup(body_text, 'xml')
                for tag in soup.find_all(True):
                    href = tag.get('href') or tag.get('src') or tag.get('action') or ''
                    if href and self._is_api_like_path(href):
                        resolved = self.resolve_url(href)
                        if resolved:
                            endpoints.append({
                                'url': resolved, 'method': 'GET',
                                'source': f'{source_url} (xml)',
                                'line': None, 'confidence': 'medium',
                            })
            except Exception:
                pass

        # HTML bodies with HATEOAS links
        if 'html' in content_type:
            soup = BeautifulSoup(body_text, 'html.parser')

            # Extract from rel="service" links
            for link in soup.find_all('link', rel=lambda x: x and 'service' in x if x else False):
                href = link.get('href', '')
                if href and self._is_api_like_path(href):
                    resolved = self.resolve_url(href)
                    if resolved:
                        endpoints.append({
                            'url': resolved, 'method': 'GET',
                            'source': f'{source_url} (hateoas:service)',
                            'line': None, 'confidence': 'medium',
                        })
                        self.discovery_stats['hateoas_endpoints'] += 1

            # Extract <a rel="..." href="..."> with API-like rel values
            for a in soup.find_all('a', href=True):
                rel = a.get('rel', [])
                if isinstance(rel, list) and any(r.lower() in ('service', 'api', 'rest', 'swagger', 'openapi', 'docs', 'collection', 'self', 'next', 'prev', 'first', 'last', 'edit', 'create', 'delete', 'update') for r in rel):
                    href = a['href']
                    resolved = self.resolve_url(href)
                    if resolved and self._in_scope(resolved):
                        endpoints.append({
                            'url': resolved, 'method': 'GET',
                            'source': f'{source_url} (hateoas:{" ".join(rel)})',
                            'line': None, 'confidence': 'medium',
                        })
                        self.discovery_stats['hateoas_endpoints'] += 1

        # Universal URL extraction
        urls_in_body = re.findall(
            r'https?://[^\s<>"\'{}|\\^`\[\]]+',
            body_text
        )
        for found_url in urls_in_body:
            found_url = found_url.rstrip('.,;:!?)')
            if self._in_scope(found_url) and self._is_api_like_path(found_url):
                endpoints.append({
                    'url': found_url, 'method': 'GET',
                    'source': f'{source_url} (body_url)',
                    'line': None, 'confidence': 'low',
                })

        return endpoints

    def _hunt_json_for_apis(self, data, source_url, context_url, depth=0, max_depth=5):
        endpoints = []
        if depth > max_depth:
            return endpoints

        if isinstance(data, dict):
            for key, value in data.items():
                kl = key.lower()
                # Check for URL-like keys
                if kl in ('url', 'uri', 'href', 'link', 'endpoint', 'api', 'api_url',
                          'base_url', 'rest_url', 'graphql_url', 'swagger_url',
                          'openapi_url', 'upload_url', 'download_url', 'callback_url',
                          'webhook_url', 'redirect_url', 'next', 'prev', 'first', 'last',
                          'self', 'edit', 'create', 'post_url', 'get_url', 'put_url',
                          'delete_url', 'patch_url', 'stream_url', 'ws_url',
                          'websocket_url', 'sse_url', 'events_url', 'notification_url',
                          'image_url', 'file_url', 'avatar_url', 'profile_url',
                          'service_url', 'documentation', 'docs',
                          'register_url', 'login_url', 'logout_url',
                          'token_url', 'authorize_url', 'revoke_url',
                          'introspection_url', 'userinfo_url', 'jwks_uri',
                          'issuer', 'authorization_endpoint', 'token_endpoint',
                          'userinfo_endpoint', 'end_session_endpoint',
                          'revocation_endpoint', 'introspection_endpoint',
                          'registration_endpoint', 'device_authorization_endpoint',
                          'pushed_authorization_request_endpoint',
                          'connection_url', 'cluster_url', 'node_url', 'proxy_url',
                          'mutation_url', 'query_url', 'subscription_url',
                          'playground_url', 'explorer_url',
                          'collection', 'self_link',
                          's3_url', 'bucket_url', 'cdn_url', 'distribution_url'):
                    if isinstance(value, str) and self._in_scope(value):
                        endpoints.append({
                            'url': value, 'method': 'GET',
                            'source': f'{source_url} (json:{key})',
                            'line': None, 'confidence': 'high' if 'url' in kl or 'endpoint' in kl else 'medium',
                        })
                # Recurse deeper
                if isinstance(value, (dict, list)):
                    endpoints.extend(self._hunt_json_for_apis(value, source_url, context_url, depth + 1, max_depth))

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    endpoints.extend(self._hunt_json_for_apis(item, source_url, context_url, depth + 1, max_depth))
                elif isinstance(item, str) and item.startswith(('http://', 'https://', '/')):
                    if self._in_scope(item) and self._is_api_like_path(item):
                        endpoints.append({
                            'url': item, 'method': 'GET',
                            'source': f'{source_url} (json:array)',
                            'line': None, 'confidence': 'low',
                        })

        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 8. CSP & LINK HEADER PARSING
    # ═══════════════════════════════════════════════════════════════

    def _parse_csp_header(self, resp, page_url):
        endpoints = []
        csp = resp.headers.get('Content-Security-Policy', '')
        if csp:
            # Extract all URLs from CSP directives
            urls = re.findall(r'https?://[^\s;\'"]+', csp)
            for url in urls:
                if self._in_scope(url) and self._is_api_like_path(url):
                    ep = {
                        'url': url, 'method': 'GET',
                        'source': f'{page_url} (csp)',
                        'line': None, 'confidence': 'medium',
                    }
                    endpoints.append(ep)
                    self.endpoints_from_html.append(ep)
                    self.discovery_stats['csp_endpoints'] += 1
        return endpoints

    def _parse_link_header(self, resp, page_url):
        endpoints = []
        link_header = resp.headers.get('Link', '')
        if link_header:
            # Parse: <url>; rel="value"
            for match in re.finditer(r'<([^>]+)>\s*;\s*rel="([^"]+)"', link_header):
                url = match.group(1)
                rel = match.group(2).lower()
                resolved = self.resolve_url(url)
                if resolved and self._in_scope(resolved) and (
                    self._is_api_like_path(resolved) or
                    rel in ('service', 'api', 'rest', 'swagger', 'openapi',
                            'docs', 'collection', 'preconnect', 'preload','dns-prefetch')
                ):
                    ep = {
                        'url': resolved, 'method': 'GET',
                        'source': f'{page_url} (link:{rel})',
                        'line': None, 'confidence': 'medium',
                    }
                    endpoints.append(ep)
                    self.endpoints_from_html.append(ep)
                    self.discovery_stats['link_header_endpoints'] += 1
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 9. HTML COMMENTS MINING
    # ═══════════════════════════════════════════════════════════════

    def _mine_html_comments(self, html, page_url):
        endpoints = []
        soup = BeautifulSoup(html, 'html.parser')
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            text = str(comment)
            # Extract URLs from comments
            urls = re.findall(r'https?://[^\s<>"\'{}|\\^`\[\]]+', text)
            for url in urls:
                url = url.rstrip('.,;:!?)')
                if self._in_scope(url) and self._is_api_like_path(url):
                    ep = {
                        'url': url, 'method': 'GET',
                        'source': f'{page_url} (html_comment)',
                        'line': None, 'confidence': 'medium',
                    }
                    endpoints.append(ep)
                    self.endpoints_from_html.append(ep)
                    self.discovery_stats['html_comment_endpoints'] += 1

            # Check for API keywords in comments
            api_hints = re.findall(
                r'(api|endpoint|route|url|link|https?://[^\s]+)',
                text, re.IGNORECASE
            )
            if len(api_hints) >= 2:
                # Comment is rich with API hints, extract any relative paths too
                rel_paths = re.findall(r"['\"](/[a-zA-Z0-9_/.-]*)['\"]", text)
                for path in rel_paths:
                    if self._is_api_like_path(path):
                        ep = {
                            'url': path, 'method': 'GET',
                            'source': f'{page_url} (html_comment:path)',
                            'line': None, 'confidence': 'low',
                        }
                        endpoints.append(ep)
                        self.endpoints_from_html.append(ep)
                        self.discovery_stats['html_comment_endpoints'] += 1

            # Extract JSON from comments
            json_match = re.search(r'\{[^{}]*"[^"]*"[^{}]*\}', text)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    self._hunt_json_for_apis(data, f'{page_url} (comment_json)', page_url)
                except (json.JSONDecodeError, ValueError):
                    pass

        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 10. MANIFEST + SERVICE WORKER
    # ═══════════════════════════════════════════════════════════════

    def _check_manifest(self):
        endpoints = []
        manifest_paths = [
            '/manifest.json', '/site.webmanifest', '/app.webmanifest',
            '/manifest.webapp',
        ]
        for mp in manifest_paths:
            url = urljoin(self.base_url, mp)
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200 and 'json' in resp.headers.get('Content-Type', ''):
                    data = resp.json()
                    for key in ['start_url', 'scope', 'serviceworker', 'src',
                                'api_url', 'base_url', 'endpoint']:
                        val = data.get(key)
                        if isinstance(val, str) and self._in_scope(val):
                            ep = {
                                'url': val, 'method': 'GET',
                                'source': f'{mp} (manifest)',
                                'line': None, 'confidence': 'medium',
                            }
                            endpoints.append(ep)
                            self.endpoints_from_html.append(ep)
                            self.discovery_stats['manifest_endpoints'] += 1
                    # Check icons array
                    for icon in data.get('icons', []):
                        src = icon.get('src', '')
                        if src and self._in_scope(src):
                            pass  # icons are rarely API endpoints
                    # Check shortcuts
                    for shortcut in data.get('shortcuts', []):
                        url_s = shortcut.get('url', '')
                        if url_s and self._is_api_like_path(url_s):
                            ep = {
                                'url': url_s, 'method': 'GET',
                                'source': f'{mp} (manifest:shortcut)',
                                'line': None, 'confidence': 'low',
                            }
                            endpoints.append(ep)
                            self.endpoints_from_html.append(ep)
            except (requests.RequestException, json.JSONDecodeError):
                continue
        return endpoints

    def _check_service_worker(self):
        endpoints = []
        sw_paths = ['/sw.js', '/service-worker.js', '/serviceworker.js',
                     '/sw.js.map', '/service-worker.js.map']
        for swp in sw_paths:
            url = urljoin(self.base_url, swp)
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    content = resp.text
                    # Parse the service worker for fetch handlers and API endpoints
                    sw_endpoints = self._extract_endpoints_from_body(
                        content, 'text/javascript', url
                    )
                    endpoints.extend(sw_endpoints)
                    for ep in sw_endpoints:
                        self.endpoints_from_html.append(ep)
                        self.discovery_stats['service_worker_endpoints'] += 1

                    # Look for cache names that might hint at API routes
                    cache_urls = re.findall(
                        r"caches\.open\(['\"]([^'\"]+)['\"]\)", content
                    )
                    for cu in cache_urls:
                        if self._is_api_like_path(cu):
                            ep = {
                                'url': cu, 'method': 'GET',
                                'source': f'{url} (sw:cache)',
                                'line': None, 'confidence': 'low',
                            }
                            endpoints.append(ep)
                            self.endpoints_from_html.append(ep)
            except requests.RequestException:
                continue
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 11. GIT / ENV DISCLOSURE
    # ═══════════════════════════════════════════════════════════════

    DISCLOSURE_PATHS = [
        # Git
        '/.git/config', '/.git/HEAD', '/.git/index',
        '/.git/logs/HEAD', '/.git/refs/heads/master',
        '/.git/packed-refs', '/.git/description',
        '/.git/info/exclude', '/.gitignore',
        '/.gitattributes',
        # Environment files
        '/.env', '/.env.example', '/.env.production', '/.env.local',
        '/.env.development', '/.env.staging',
        '/.env.dev', '/.env.prod', '/.env.stage',
        '/.env.testing', '/.env.ci',
        '/.env.backup', '/.env.old',
        '/env.json', '/environment.json',
        '/env.yaml', '/env.yml',
        # CI/CD
        '/.gitlab-ci.yml', '/.github/workflows/',
        '/.circleci/config.yml',
        '/.github/workflows/build.yml',
        '/.github/workflows/deploy.yml',
        '/.github/workflows/release.yml',
        '/bitbucket-pipelines.yml',
        '/Jenkinsfile',
        '/.travis.yml', '/.drone.yml',
        '/.buildkite/pipeline.yml',
        '/.teamcity/settings.kts',
        '/cloudbuild.yaml',
        '/.woodpecker.yml',
        # Web server config
        '/.htaccess', '/.htpasswd',
        '/web.config', '/web.config.bak',
        '/nginx.conf', '/nginx.conf.example',
        '/nginx/default.conf',
        '/Caddyfile',
        '/httpd.conf', '/apache.conf',
        '.htaccess', '.htpasswd',
        # Database dumps
        '/dump.sql', '/backup.sql', '/db.sql',
        '/database.sql', '/mysql.sql', '/postgres.sql',
        '/dump.psql', '/dump.mysql',
        '/backup.tar.gz', '/backup.zip',
        '/db_backup.sql', '/db.sql.gz',
        # Config files
        '/config.json', '/config.js', '/config.php',
        '/config.yaml', '/config.yml',
        '/config.xml', '/config.ini',
        '/configuration.json',
        '/appsettings.json', '/appsettings.Development.json',
        '/application.yml', '/application.properties',
        '/application.conf', '/application.config',
        '/runtime.json', '/runtime.yaml',
        '/settings.json', '/settings.py',
        '/settings.php', '/settings.yml',
        '/local.json', '/local.config',
        # Secrets / credentials
        '/credentials.json', '/credentials',
        '/credentials.yml', '/credentials.yaml',
        '/service-account.json', '/service-account-key.json',
        '/service-account.yaml',
        '/firebase.json', '/firebase-config.json',
        '/firebase-admin.json', '/firebase-adminsdk.json',
        '/.npmrc', '/.yarnrc', '/.gemrc',
        '/.p12', '/.jks', '/.key', '/.pem', '/.cert',
        '/.ssh/id_rsa', '/.ssh/id_rsa.pub',
        '/.ssh/authorized_keys', '/.ssh/known_hosts',
        '/.ssh/config',
        '/secrets.json', '/secrets.yml', '/secrets.yaml',
        '/secret.json', '/secret.yml',
        '/key.json', '/keys.json',
        '/token.json', '/tokens.json',
        '/token.txt', '/tokens.txt',
        # Cloud provider credentials
        '/.aws.json', '/aws.json',
        '/aws.yml', '/aws-config.json',
        '/.aws/credentials', '/.aws/config',
        '/.azure.json', '/azure.json',
        '/.azure/credentials', '/azure-profile.json',
        '/.gcp.json', '/gcp.json',
        '/google-cloud.json', '/google-credentials.json',
        '/.digitalocean.json',
        '/.heroku.json', '/heroku.json',
        '/.netlify.json', '/netlify.json',
        '/.vercel.json', '/vercel.json',
        '/now.json',
        # Third-party API keys
        '/.stripe', '/stripe.json',
        '/stripe-key.json',
        '/sendgrid.json', '/sendgrid.env',
        '/mailgun.json', '/mailgun.env',
        '/twilio.json', '/twilio.yml',
        '/twilio.env',
        '/mailchimp.json', '/mailchimp.env',
        '/algolia.json', '/algolia.env',
        '/auth0.json', '/auth0.env',
        '/okta.json', '/okta.env',
        '/sentry.json', '/sentry.env',
        '/datadog.json', '/datadog.env',
        '/newrelic.json', '/newrelic.env',
        # Database config
        '/database.yml', '/database.json',
        '/database.php', '/database.config',
        '/databases.yml',
        '/mongodb.json', '/mongo.json',
        '/mysql.json', '/postgres.json',
        '/redis.json', '/redis.conf',
        '/elasticsearch.yml',
        # Deploy scripts
        '/deploy.sh', '/deploy.rb', '/deploy.php',
        '/deploy.env', '/build.env',
        '/deploy.py', '/deploy.yaml', '/deploy.yml',
        '/deploy.conf',
        '/build.sh', '/build.py', '/build.xml',
        '/Makefile', '/makefile',
        '/Dockerfile', '/docker-compose.yml',
        '/docker-compose.yaml',
        '/Dockerfile.prod', '/Dockerfile.dev',
        '/docker-compose.prod.yml',
        '/.dockerignore',
        '/Procfile', '/app.json',
        '/.editorconfig',
        # Package manifests
        '/package.json', '/bower.json', '/composer.json',
        '/composer.lock', '/yarn.lock',
        '/package-lock.json',
        '/requirements.txt', '/Pipfile', '/Pipfile.lock',
        '/Gemfile', '/Gemfile.lock',
        '/go.mod', '/go.sum',
        '/Cargo.toml', '/Cargo.lock',
        '/build.gradle', '/pom.xml',
        '/mix-manifest.json',
        # Build artifacts
        '/build/', '/dist/', '/.next/', '/.nuxt/',
        '/out/', '/target/', '/bin/', '/obj/',
        # Source maps
        '/webpack.config.js', '/vite.config.ts',
        '/rollup.config.js',
        '/gruntfile.js', '/gulpfile.js',
        '/.babelrc', '/.eslintrc',
        '/tsconfig.json', '/tsconfig.build.json',
        '/.prettierrc', '/.stylelintrc',
        # Framework artifacts
        '/artisan', '/wp-config.php',
        '/wp-config.php.bak',
        '/wp-admin/install.php',
        '/debug.log', '/error.log',
        '/storage/logs/laravel.log',
        '/runtime/logs/',
        '/api/logs/', '/api/debug/',
        '/api/__debug', '/api/__test',
        '/__test__/', '/tests/', '/spec/',
        '/test/', '/testing/',
        '/docs/', '/documentation/',
        '/api/docs/', '/api/documentation/',
        '/phpinfo.php', '/info.php',
        '/api/test', '/api/workflows/',
        '/api/schedules/',
        '/api/health/ready', '/api/health/live',
        # Kubernetes
        '/kubeconfig', '/.kube/config',
        '/k8s.yaml', '/k8s.yml',
        '/kubernetes.yaml', '/kubernetes.yml',
        '/helmfile.yaml',
        # Terraform
        '/.terraform/', '/terraform.tfstate',
        '/terraform.tfvars', '/terraform.tf',
        '/main.tf', '/variables.tf',
        '/outputs.tf', '/backend.tf',
        '/provider.tf',
        # Serverless
        '/.serverless/',
        '/.elasticbeanstalk/',
        '/serverless.yml', '/serverless.yaml',
        '/serverless.env.yml',
        '/sam.yaml', '/template.yaml',
        '/function.json',
        # Various
        '/.well-known/apple-app-site-association',
        '/.well-known/assetlinks.json',
        '/crossdomain.xml', '/clientaccesspolicy.xml',
        '/sitemap.xml', '/robots.txt',
        '/security.txt', '/humans.txt',
        '/favicon.ico',
        '/api/health', '/api/version',
        '/health', '/healthcheck',
        '/status', '/ping',
    ]

    def _check_disclosure_paths(self):
        endpoints = []
        for dp, url, resp in self._probe_concurrent(self.DISCLOSURE_PATHS, timeout=self.timeout):
            if resp.status_code != 200:
                continue
            ep = {
                'url': dp, 'method': 'GET',
                'source': 'disclosure_check',
                'line': None, 'confidence': 'high',
                'info': f'exposed:{resp.status_code}',
            }
            endpoints.append(ep)
            self.endpoints_from_html.append(ep)

            content_type = resp.headers.get('Content-Type', '')
            if 'git' in dp.lower():
                self.discovery_stats['git_exposed'] += 1
                if '/config' in dp:
                    git_urls = re.findall(r'url\s*=\s*(.+)', resp.text)
                    for gu in git_urls:
                        gu = gu.strip()
                        if gu.startswith(('http://', 'https://')):
                            ep2 = {
                                'url': gu, 'method': 'GET',
                                'source': f'{url} (git_remote)',
                                'line': None, 'confidence': 'high',
                            }
                            endpoints.append(ep2)
                            self.endpoints_from_html.append(ep2)
            elif '.env' in dp or 'env.' in dp:
                self.discovery_stats['env_exposed'] += 1
                env_urls = re.findall(r'(https?://[^\s"\'<>]+)', resp.text)
                for eu in env_urls:
                    eu = eu.rstrip('.,;:!?)')
                    if self._in_scope(eu):
                        ep2 = {
                            'url': eu, 'method': 'GET',
                            'source': f'{url} (env)',
                            'line': None, 'confidence': 'high',
                        }
                        endpoints.append(ep2)
                        self.endpoints_from_html.append(ep2)

            if 'json' in content_type:
                try:
                    data = resp.json()
                    json_eps = self._hunt_json_for_apis(data, url, url)
                    for jep in json_eps:
                        self.endpoints_from_html.append(jep)
                        endpoints.append(jep)
                except (json.JSONDecodeError, ValueError):
                    pass
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 12. COMMON GRAPHQL ENDPOINTS (extended)
    # ═══════════════════════════════════════════════════════════════

    GRAPHQL_PATHS = [
        '/api/graphql', '/graphql', '/graphql/console', '/graphiql',
        '/gql', '/api/gql', '/query', '/api/query',
        '/graphql/public', '/graphql/private',
        '/api/graphql/public', '/api/graphql/private',
        '/v1/graphql', '/v2/graphql', '/v3/graphql',
        '/api/v1/graphql', '/api/v2/graphql', '/api/v3/graphql',
        '/graph/v1', '/graph/v2',
        '/api/graph/v1', '/api/graph/v2',
        '/graphql/v1', '/graphql/v2',
        '/graphql/explorer', '/graphql-playground',
        '/graphql/graphiql',
        '/graphql/subscriptions', '/graphql/subscription',
        '/api/subscriptions', '/api/subscription',
        '/graphql/schema', '/graphql/schema.json',
        '/api/graphql/schema', '/api/graphql/schema.json',
        '/graphql/config', '/api/graphql/config',
        '/graphql/health', '/api/graphql/health',
        '/api/hasura', '/hasura',
        '/api/hasura/graphql',
        '/v1/graphql/config',
        '/api/v1/graphql/config',
        '/api/graphql/explorer',
        '/graphql/playground',
        '/admin/api/graphql',
        '/api/admin/graphql',
        '/api/graphql/admin',
        '/api/graphql/private',
        '/api/internal/graphql',
        '/graphql/internal',
        '/graphql/private',
        '/api/graphql/v1/public',
        '/api/graphql/v1/private',
        '/api/graphql/v2/public',
        '/api/graphql/v2/private',
        '/gql/v1', '/gql/v2',
        '/api/gql/v1', '/api/gql/v2',
        '/graphql/api', '/api/v1/graphql/api',
        '/graphql/relay',
        '/api/graphql/batch',
        '/graphql/batch',
        '/api/graphql/debug',
        '/graphql/debug',
        '/api/graphql/test',
        '/graphql/test',
    ]

    def _discover_graphql(self):
        endpoints = []
        urls = [urljoin(self.base_url, p) for p in self.GRAPHQL_PATHS]
        with ThreadPoolExecutor(max_workers=20) as ex:
            def probe(u, p):
                try:
                    resp = self.session.post(u, json={'query': '{ __typename }'},
                                             timeout=self.timeout,
                                             headers={'Content-Type': 'application/json'})
                    if resp.status_code in (200, 400):
                        if '"data"' in resp.text or '"errors"' in resp.text:
                            ep = {'url': p, 'method': 'POST', 'source': 'graphql_discovery',
                                  'line': None, 'confidence': 'high', 'info': 'graphql'}
                            return ep
                except requests.RequestException:
                    try:
                        resp = self.session.get(u, timeout=self.timeout)
                        if resp.status_code in (200, 400) and (
                            'graphiql' in resp.text.lower() or
                            'graphql' in resp.text.lower() or
                            'query' in resp.text.lower()
                        ):
                            ep = {'url': p, 'method': 'GET', 'source': 'graphql_discovery',
                                  'line': None, 'confidence': 'high', 'info': 'graphiql'}
                            return ep
                    except requests.RequestException:
                        pass
                return None
            fut_map = {ex.submit(probe, u, p): p for u, p in zip(urls, self.GRAPHQL_PATHS)}
            for fut in as_completed(fut_map):
                try:
                    ep = fut.result()
                    if ep:
                        endpoints.append(ep)
                        self.endpoints_from_html.append(ep)
                except Exception:
                    pass
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 13. CLOUD STORAGE / CDN PROBING
    # ═══════════════════════════════════════════════════════════════

    CLOUD_PROBE_PATTERNS = [
        # S3 bucket naming patterns based on domain
        lambda domain: f'https://{domain}.s3.amazonaws.com',
        lambda domain: f'https://s3.amazonaws.com/{domain}',
        lambda domain: f'https://{domain.replace(".", "-")}.s3.amazonaws.com',
        lambda domain: f'https://{domain}.s3-website-{random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"])}.amazonaws.com',
        lambda domain: f'https://{domain}.storage.googleapis.com',
        lambda domain: f'https://{domain}.blob.core.windows.net',
        lambda domain: f'https://cdn.{domain.replace("www.", "")}',
        lambda domain: f'https://api.{domain.replace("www.", "")}',
        lambda domain: f'https://{domain.replace("www.", "")}-api.herokuapp.com',
        lambda domain: f'https://{domain.replace("www.", "")}.netlify.app',
        lambda domain: f'https://{domain.replace("www.", "")}.vercel.app',
        lambda domain: f'https://{domain.replace("www.", "")}.pages.dev',
        lambda domain: f'https://{domain.replace("www.", "")}.firebaseapp.com',
        lambda domain: f'https://{domain.replace("www.", "")}.fly.dev',
        lambda domain: f'https://{domain.replace("www.", "")}.railway.app',
        lambda domain: f'https://{domain.replace("www.", "")}.render.com',
        lambda domain: f'https://{domain.replace("www.", "")}.onrender.com',
        lambda domain: f'https://{domain.replace("www.", "")}.koyeb.app',
        lambda domain: f'https://{domain}.workers.dev',
        lambda domain: f'https://{domain}.r2.dev',
        lambda domain: f'https://storage.googleapis.com/{domain}',
        lambda domain: f'https://{domain}.digitaloceanspaces.com',
        lambda domain: f'https://{domain}.linodeobjects.com',
        lambda domain: f'https://{domain}.wasabisys.com',
        lambda domain: f'https://{domain}.backblazeb2.com',
    ]

    def _probe_cloud_storage(self):
        if not self.deep:
            return []
        endpoints = []
        domain = self.domain
        for pattern_fn in self.CLOUD_PROBE_PATTERNS:
            try:
                url = pattern_fn(domain)
                if self._in_scope(url):
                    try:
                        resp = self.session.head(url, timeout=5)
                        if resp.status_code not in (404, 403, 0):
                            ep = {
                                'url': url, 'method': 'GET',
                                'source': 'cloud_probe',
                                'line': None, 'confidence': 'medium',
                            }
                            endpoints.append(ep)
                            self.endpoints_from_html.append(ep)
                    except requests.RequestException:
                        continue
            except Exception:
                continue
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # 14. THIRD-PARTY API PATTERNS (SDK endpoints)
    # ═══════════════════════════════════════════════════════════════

    THIRD_PARTY_API_PATTERNS = [
        # Firebase
        r'https?://[a-z0-9-]+\.firebaseio\.com',
        r'https?://[a-z0-9-]+\.firestore\.firebaseio\.com',
        r'https?://identitytoolkit\.googleapis\.com',
        r'https?://securetoken\.googleapis\.com',
        r'https?://fcm\.googleapis\.com',
        r'https?://firestore\.googleapis\.com',
        r'https?://firebaseremoteconfig\.googleapis\.com',
        r'https?://firebasecrashlytics\.googleapis\.com',
        r'https?://firebaseperf\.googleapis\.com',
        # Google APIs
        r'https?://[a-z]+-[a-z]+\.googleapis\.com',
        r'https?://www\.googleapis\.com',
        r'https?://oauth2\.googleapis\.com',
        r'https?://sheets\.googleapis\.com',
        r'https?://docs\.googleapis\.com',
        r'https?://drive\.googleapis\.com',
        r'https?://calendar\.googleapis\.com',
        r'https?://gmail\.googleapis\.com',
        r'https?://maps\.googleapis\.com',
        r'https?://places\.googleapis\.com',
        r'https?://routes\.googleapis\.com',
        r'https?://storage\.googleapis\.com',
        r'https?://bigquery\.googleapis\.com',
        r'https?://pubsub\.googleapis\.com',
        r'https?://datastore\.googleapis\.com',
        r'https?://cloudfunctions\.googleapis\.com',
        r'https?://run\.googleapis\.com',
        r'https?://cloud\.google\.com',
        # AWS
        r'https?://[a-z0-9-]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com',
        r'https?://[a-z0-9-]+\.lambda-url\.[a-z0-9-]+\.on\.aws',
        r'https?://[a-z0-9-]+\.s3\.amazonaws\.com',
        r'https?://s3[-\.][a-z0-9-]+\.amazonaws\.com/[a-zA-Z0-9-]+',
        r'https?://[a-z0-9-]+\.cloudfront\.net',
        r'https?://api\.googleapis\.com',
        # Azure
        r'https?://[a-z0-9-]+\.azurewebsites\.net',
        r'https?://[a-z0-9-]+\.azure-api\.net',
        r'https?://[a-z0-9-]+\.blob\.core\.windows\.net',
        r'https?://[a-z0-9-]+\.queue\.core\.windows\.net',
        r'https?://[a-z0-9-]+\.table\.core\.windows\.net',
        r'https?://management\.azure\.com',
        r'https?://graph\.microsoft\.com',
        r'https?://login\.microsoftonline\.com',
        # Stripe
        r'https?://api\.stripe\.com',
        r'https?://[a-z0-9-]+\.stripe\.com',
        r'https?://checkout\.stripe\.com',
        r'https?://js\.stripe\.com',
        r'https?://hooks\.stripe\.com',
        # PayPal
        r'https?://api\.paypal\.com',
        r'https?://api-m\.paypal\.com',
        r'https?://api\.sandbox\.paypal\.com',
        r'https?://www\.paypal\.com/api/',
        r'https?://svcs\.paypal\.com',
        r'https?://ipnpb\.paypal\.com',
        # Stripe Connect / others
        r'https?://connect\.stripe\.com',
        # Twilio
        r'https?://api\.twilio\.com',
        r'https?://[a-z0-9-]+\.twilio\.com',
        r'https?://[a-z0-9-]+\.twil\.io',
        # SendGrid
        r'https?://api\.sendgrid\.com',
        r'https?://sendgrid\.com/api/',
        # Mailgun
        r'https?://api\.mailgun\.net',
        r'https?://api\.mailgun\.com',
        # Mailchimp
        r'https?://[a-z0-9-]+\.api\.mailchimp\.com',
        r'https?://mandrillapp\.com',
        # Algolia
        r'https?://[a-z0-9-]+\.algolia\.net',
        r'https?://[a-z0-9-]+\.algolia\.io',
        # Contentful
        r'https?://cdn\.contentful\.com',
        r'https?://api\.contentful\.com',
        r'https?://graphql\.contentful\.com',
        r'https?://preview\.contentful\.com',
        # Sanity
        r'https?://[a-z0-9-]+\.api\.sanity\.io',
        r'https?://[a-z0-9-]+\.apicdn\.sanity\.io',
        r'https?://[a-z0-9-]+\.sanity\.io',
        # Supabase
        r'https?://[a-z0-9-]+\.supabase\.co',
        r'https?://[a-z0-9-]+\.supabase\.in',
        r'https?://db\.[a-z0-9-]+\.supabase\.co',
        # Auth0
        r'https?://[a-z0-9-]+\.auth0\.com',
        r'https?://[a-z0-9-]+\.us\.auth0\.com',
        r'https?://[a-z0-9-]+\.eu\.auth0\.com',
        r'https?://[a-z0-9-]+\.auth0\.com/api/',
        r'https?://login\.auth0\.com',
        # Clerk
        r'https?://[a-z0-9-]+\.clerk\.accounts\.dev',
        r'https?://[a-z0-9-]+\.clerk\.com',
        r'https?://api\.clerk\.com',
        # Okta
        r'https?://[a-z0-9-]+\.okta\.com',
        r'https?://[a-z0-9-]+\.oktapreview\.com',
        r'https?://[a-z0-9-]+\.okta-emea\.com',
        r'https?://login\.okta\.com',
        # Auth.js / NextAuth
        r'https?://[a-z0-9-]+\.authjs\.dev',
        # Supabase Auth
        r'https?://[a-z0-9-]+\.supabase\.co/auth/',
        # Firebase Auth
        r'https?://identitytoolkit\.googleapis\.com/v\d+/',
        # AWS Cognito
        r'https?://[a-z0-9-]+\.auth\.[a-z0-9-]+\.amazoncognito\.com',
        r'https?://cognito-idp\.[a-z0-9-]+\.amazonaws\.com',
        r'https?://cognito-identity\.[a-z0-9-]+\.amazonaws\.com',
        # Cloudflare
        r'https?://api\.cloudflare\.com',
        r'https?://[a-z0-9-]+\.cloudflare\.com',
        # Vercel
        r'https?://api\.vercel\.com',
        r'https?://[a-z0-9-]+\.vercel\.app/api/',
        # Netlify
        r'https?://api\.netlify\.com',
        r'https?://[a-z0-9-]+\.netlify\.(app|com)/api/',
        # Heroku
        r'https?://[a-z0-9-]+\.herokuapp\.com',
        # DigitalOcean
        r'https?://api\.digitalocean\.com',
        # Pulumi
        r'https?://api\.pulumi\.com',
        # HashiCorp Vault
        r'https?://[a-z0-9-]+\.vault\.(?:azure|aws|gcp)\.hashicorp\.cloud',
        # New Relic
        r'https?://[a-z0-9-]+\.newrelic\.com',
        r'https?://collector\.newrelic\.com',
        r'https?://trace-collector\.newrelic\.com',
        r'https?://log-api\.newrelic\.com',
        # Datadog
        r'https?://[a-z0-9-]+\.datadoghq\.com',
        r'https?://api\.datadoghq\.com',
        r'https?://trace\.agent\.datadoghq\.com',
        r'https?://browser-intake-datadoghq\.com',
        # Sentry
        r'https?://[a-z0-9-]+\.sentry\.io',
        r'https?://o[0-9]+\.ingest\.sentry\.io',
        r'https?://[a-z0-9-]+\.ingest\.sentry\.io',
        # LogRocket
        r'https?://[a-z0-9-]+\.logrocket\.io',
        r'https?://api\.logrocket\.com',
        # FullStory
        r'https?://[a-z0-9-]+\.fullstory\.com',
        # Heap
        r'https?://[a-z0-9-]+\.heap\.com',
        r'https?://heapanalytics\.com',
        # Mixpanel
        r'https?://api\.mixpanel\.com',
        r'https?://[a-z0-9-]+\.mixpanel\.com',
        # Amplitude
        r'https?://api2\.amplitude\.com',
        r'https?://api\.amplitude\.com',
        r'https?://analytics\.amplitude\.com',
        # Segment
        r'https?://api\.segment\.io',
        r'https?://[a-z0-9-]+\.segment\.io',
        r'https?://cdn\.segment\.io',
        # OpenReplay
        r'https?://[a-z0-9-]+\.openreplay\.com',
        r'https?://api\.openreplay\.io',
        # Hotjar
        r'https?://[a-z0-9-]+\.hotjar\.com',
        # Mapbox
        r'https?://api\.mapbox\.com',
        r'https?://[a-z0-9-]+\.tiles\.mapbox\.com',
        r'https?://events\.mapbox\.com',
        # Google Maps / Places
        r'https?://maps\.googleapis\.com',
        r'https?://places\.googleapis\.com',
        r'https?://routes\.googleapis\.com',
        r'https?://roads\.googleapis\.com',
        r'https?://maps\.gstatic\.com',
        # MapLibre
        # reCAPTCHA
        r'https?://www\.google\.com/recaptcha/',
        r'https?://recaptcha\.google\.com',
        r'https?://[a-z0-9-]+\.recaptcha\.net',
        r'https?://www\.gstatic\.com/recaptcha/',
        # hCaptcha
        r'https?://hcaptcha\.com',
        r'https?://api\.hcaptcha\.com',
        r'https?://newassets\.hcaptcha\.com',
        # Cloudflare Turnstile
        r'https?://challenges\.cloudflare\.com',
        r'https?://turnstile\.cloudflare\.com',
        # Arkose Labs
        r'https?://[a-z0-9-]+\.arkoselabs\.com',
        r'https?://api\.arkoselabs\.com',
        # Pusher
        r'https?://[a-z0-9-]+\.pusher\.com',
        r'https?://ws-[a-z0-9-]+\.pusher\.com',
        r'https?://api-[a-z0-9-]+\.pusher\.com',
        # Ably
        r'https?://[a-z0-9-]+\.ably\.io',
        r'https?://rest\.ably\.io',
        r'https?://realtime\.ably\.io',
        # Socket.io
        r'https?://[a-z0-9-]+\.socket\.io',
        r'https?://socket\.io',
        # WebSocket-specific patterns
        r'wss?://[^\s<>"\'{}|\\^`\[\]]+',
        # Stripe Connect
        r'https?://connect\.stripe\.com',
        # Square
        r'https?://connect\.squareup\.com',
        r'https?://api\.squareup\.com',
        r'https?://[a-z0-9-]+\.squareup\.com',
        # Braintree
        r'https?://api\.braintreegateway\.com',
        r'https?://[a-z0-9-]+\.braintreegateway\.com',
        # Adyen
        r'https?://[a-z0-9-]+\.adyen\.com',
        r'https?://checkout\.adyen\.com',
        r'https?://pal-[a-z0-9-]+\.adyen\.com',
        # Shopify
        r'https?://[a-z0-9-]+\.myshopify\.com',
        r'https?://[a-z0-9-]+\.shopify\.com',
        r'https?://admin\.shopify\.com',
        r'https?://api\.shopify\.com',
        # WooCommerce
        r'https?://[a-z0-9-]+\.wc\.com',
        # BigCommerce
        r'https?://api\.bigcommerce\.com',
        r'https?://[a-z0-9-]+\.bigcommerce\.com',
        # Magento
        r'https?://[a-z0-9-]+\.magento\.com',
        # OpenCart
        # HubSpot
        r'https?://api\.hubapi\.com',
        r'https?://[a-z0-9-]+\.hubapi\.com',
        r'https?://forms\.hubspot\.com',
        # Salesforce
        r'https?://[a-z0-9-]+\.salesforce\.com',
        r'https?://[a-z0-9-]+\.force\.com',
        r'https?://login\.salesforce\.com',
        r'https?://test\.salesforce\.com',
        r'https?://[a-z0-9-]+\.cloudforce\.com',
        # Zendesk
        r'https?://[a-z0-9-]+\.zendesk\.com',
        r'https?://api\.zendesk\.com',
        # Intercom
        r'https?://api\.intercom\.io',
        r'https?://[a-z0-9-]+\.intercom\.io',
        # Zoho
        r'https?://[a-z0-9-]+\.zoho\.com',
        r'https?://api\.zoho\.com',
        r'https?://accounts\.zoho\.com',
        # Freshdesk
        r'https?://[a-z0-9-]+\.freshdesk\.com',
        r'https?://api\.freshdesk\.com',
        # Pipedrive
        r'https?://[a-z0-9-]+\.pipedrive\.com',
        r'https?://api\.pipedrive\.com',
        # Monday.com
        r'https?://[a-z0-9-]+\.monday\.com',
        r'https?://api\.monday\.com',
        # Notion
        r'https?://api\.notion\.com',
        r'https?://[a-z0-9-]+\.notion\.com',
        # Airtable
        r'https?://api\.airtable\.com',
        r'https?://[a-z0-9-]+\.airtable\.com',
        # Asana
        r'https?://app\.asana\.com',
        r'https?://api\.asana\.com',
        # Trello
        r'https?://api\.trello\.com',
        r'https?://[a-z0-9-]+\.trello\.com',
        # Jira
        r'https?://[a-z0-9-]+\.atlassian\.net',
        r'https?://[a-z0-9-]+\.jira\.com',
        r'https?://api\.atlassian\.com',
        # GitLab
        r'https?://gitlab\.com/api/',
        r'https?://[a-z0-9-]+\.gitlab\.com/api/',
        # GitHub
        r'https?://api\.github\.com',
        r'https?://[a-z0-9-]+\.github\.com/api/',
        r'https?://raw\.githubusercontent\.com',
        # Bitbucket
        r'https?://api\.bitbucket\.org',
        r'https?://[a-z0-9-]+\.bitbucket\.org',
        # Cloudinary
        r'https?://api\.cloudinary\.com',
        r'https?://res\.cloudinary\.com',
        r'https?://[a-z0-9-]+\.cloudinary\.com',
        # imgix
        r'https?://[a-z0-9-]+\.imgix\.net',
        # Uploadcare
        r'https?://[a-z0-9-]+\.uploadcare\.com',
        r'https?://api\.uploadcare\.com',
        # Filestack
        r'https?://[a-z0-9-]+\.filestack\.io',
        r'https?://api\.filestack\.com',
        # Transloadit
        r'https?://api\.transloadit\.com',
        # Mux
        r'https?://api\.mux\.com',
        r'https?://[a-z0-9-]+\.mux\.com',
        # Cloudflare Stream
        r'https?://api\.cloudflare\.com/client/v4/stream',
        # Stream (getstream.io)
        r'https?://[a-z0-9-]+\.stream-io-api\.com',
        r'https?://api\.getstream\.io',
        # Video SDK / Daily.co
        r'https?://api\.daily\.co',
        r'https?://[a-z0-9-]+\.daily\.co',
        # Twilio Video / LiveKit
        r'https?://[a-z0-9-]+\.livekit\.cloud',
        r'https?://[a-z0-9-]+\.livekit\.io',
        # Agora
        r'https?://api\.agora\.io',
        r'https?://[a-z0-9-]+\.agora\.io',
    ]

    def _match_third_party_apis(self, content, source_label):
        endpoints = []
        if not content:
            return endpoints
        for pattern in self.THIRD_PARTY_API_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                url = match.group(0).rstrip('.,;:!?)"\'`>')
                if url not in self.visited_urls:
                    ep = {
                        'url': url, 'method': 'GET',
                        'source': f'{source_label} (third_party)',
                        'line': None, 'confidence': 'medium',
                    }
                    endpoints.append(ep)
                    self.endpoints_from_html.append(ep)
        return endpoints

    # ═══════════════════════════════════════════════════════════════
    # WAYBACK MACHINE
    # ═══════════════════════════════════════════════════════════════

    def fetch_wayback_urls(self):
        if not self.wayback:
            return []
        try:
            api_url = f'https://web.archive.org/cdx/search/cdx?url={self.base_url}/*&output=json&collapse=urlkey&limit=500'
            resp = requests.get(api_url, timeout=30)
            if resp.status_code != 200:
                return []
            data = resp.json()
            urls = [entry[2] for entry in data[1:]] if len(data) > 1 else []
            logger.debug(f'Wayback Machine returned {len(urls)} URLs')
            return urls[:self.max_pages]
        except Exception as e:
            logger.debug(f'Wayback Machine error: {e}')
            return []

    def crawl_wayback(self, urls):
        for url in urls:
            if len(self.visited_urls) >= self.max_pages:
                break
            normalized = self.normalize_url(url)
            if normalized in self.visited_urls:
                continue
            if not self._in_scope(url):
                continue
            self.visited_urls.add(normalized)
            self._rate_limit()
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            content_type = resp.headers.get('Content-Type', '')
            if 'javascript' in content_type or url.endswith('.js'):
                js_url = self.resolve_url(resp.url) or url
                if js_url not in [j['url'] for j in self.js_files]:
                    self.js_files.append({'url': js_url, 'content': resp.text})
                continue
            if 'text/html' in content_type or 'application/xhtml' in content_type:
                page_info = self._parse_page(resp)
                self.pages.append(page_info)

    # ═══════════════════════════════════════════════════════════════
    # MAIN CRAWL
    # ═══════════════════════════════════════════════════════════════

    def crawl(self):
        # Pre-crawl discovery
        if self.robots:
            self._fetch_robots_txt()
        if self.sitemap:
            self._fetch_sitemaps()

        # Wayback crawl
        if self.wayback:
            wayback_urls = self.fetch_wayback_urls()
            if wayback_urls:
                self.crawl_wayback(wayback_urls)

        # BFS crawl
        queue = deque([(self.base_url, 0)])

        while queue and len(self.visited_urls) < self.max_pages:
            url, depth = queue.popleft()
            normalized = self.normalize_url(url)

            if normalized in self.visited_urls:
                continue
            self.visited_urls.add(normalized)

            if depth > self.max_depth:
                continue
            if not self._in_scope(url):
                continue

            logger.debug(f'Crawling: {url} (depth={depth})')

            self._rate_limit()

            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                resp.raise_for_status()
            except requests.RequestException as e:
                logger.debug(f'Failed to fetch {url}: {e}')
                continue

            content_type = resp.headers.get('Content-Type', '')

            # Parse CSP header
            self._parse_csp_header(resp, url)

            # Parse Link header
            self._parse_link_header(resp, url)

            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                if 'javascript' in content_type or url.endswith('.js'):
                    js_url = self.resolve_url(resp.url) or url
                    if js_url not in [j['url'] for j in self.js_files]:
                        content = resp.text
                        if self.deobfuscate and len(content) > 10000:
                            content = self._deobfuscate_js(content)
                        self.js_files.append({'url': js_url, 'content': content})

                        # Also search JS content for third-party APIs
                        tps = self._match_third_party_apis(content, js_url)
                        for ep in tps:
                            self.endpoints_from_html.append(ep)
                            self.discovery_stats['third_party_endpoints'] = self.discovery_stats.get('third_party_endpoints', 0) + 1
                continue

            # Parse HTML page
            page_info = self._parse_page(resp)
            self.pages.append(page_info)

            # Mine HTML comments
            self._mine_html_comments(resp.text, url)

            # Extract endpoints from response body
            if self.deep or self.crawl_apis:
                body_eps = self._extract_endpoints_from_body(resp.text, content_type, url)
                for ep in body_eps:
                    self.endpoints_from_html.append(ep)
                    self.discovery_stats['response_body_endpoints'] += 1

            # Check for third-party APIs in the HTML
            tps = self._match_third_party_apis(resp.text, url)
            for ep in tps:
                self.discovery_stats['third_party_endpoints'] = self.discovery_stats.get('third_party_endpoints', 0) + 1

            if depth < self.max_depth:
                for link in page_info['links']:
                    if len(self.visited_urls) >= self.max_pages:
                        break
                    resolved = self.resolve_url(link)
                    if resolved and self._in_scope(resolved):
                        normalized_link = self.normalize_url(resolved)
                        if normalized_link not in self.visited_urls:
                            queue.append((resolved, depth + 1))

        # Post-crawl discovery (use short timeout for probes)
        saved_timeout = self.timeout
        self.timeout = (1, 2)  # 1s connect, 2s read for probe requests
        discovery_deadline = time.time() + 60  # Max 60 seconds total for discovery
        self._discover_api_specs()
        self._discover_graphql()
        if time.time() < discovery_deadline:
            self._discover_openapi()
        if time.time() < discovery_deadline:
            self._check_source_maps()
        if self.fuzz and time.time() < discovery_deadline:
            self._fuzz_paths()
        if self.well_known and time.time() < discovery_deadline:
            self._probe_well_known()
        if self.deep and time.time() < discovery_deadline:
            self._probe_cloud_storage()
        if time.time() < discovery_deadline:
            self._check_disclosure_paths()
        if time.time() < discovery_deadline:
            self._check_manifest()
        if time.time() < discovery_deadline:
            self._check_service_worker()
        if self.custom_paths and time.time() < discovery_deadline:
            self._probe_custom_paths()
        if self.dir_bust and time.time() < discovery_deadline:
            self._directory_api_busting()
        self.timeout = saved_timeout

        return {
            'pages': self.pages,
            'js_files': self.js_files,
            'html_endpoints': self.endpoints_from_html,
            'openapi_specs': self.openapi_specs,
            'discovery_stats': self.discovery_stats,
        }

    # ═══════════════════════════════════════════════════════════════
    # ORIGINAL METHODS (preserved / enhanced)
    # ═══════════════════════════════════════════════════════════════

    def _deobfuscate_js(self, content):
        try:
            import subprocess
            result = subprocess.run(
                ['node', '-e', '''
                    const code = process.argv[1];
                    try {
                        const acorn = require("acorn");
                        acorn.parse(code, {ecmaVersion: "latest"});
                        process.stdout.write("VALID");
                    } catch(e) {
                        try {
                            const escodegen = require("escodegen");
                            const esprima = require("esprima");
                            const ast = esprima.parseScript(code, {tolerant: true});
                            process.stdout.write(escodegen.generate(ast));
                        } catch(e2) {
                            process.stdout.write("PARSE_FAILED");
                        }
                    }
                ''', content],
                capture_output=True, text=True, timeout=15
            )
            output = result.stdout.strip()
            if output and output != 'VALID' and output != 'PARSE_FAILED':
                return output
            return content
        except Exception:
            return content

    def _discover_openapi(self):
        # Legacy method - now handled by _discover_api_specs
        pass

    def _parse_openapi_json(self, spec, source_url):
        endpoints = []
        paths = spec.get('paths', {}) or {}
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method in methods:
                if method.upper() in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'):
                    endpoints.append({
                        'url': path,
                        'method': method.upper(),
                        'source': f'{source_url} (openapi)',
                        'line': None,
                        'confidence': 'high',
                    })
        return endpoints

    def _parse_openapi_yaml(self, text, source_url):
        endpoints = []
        try:
            path_pattern = re.compile(r'^\s{2}(/[^\s]+):', re.MULTILINE)
            method_pattern = re.compile(r'^\s{4}(get|post|put|delete|patch|head|options):', re.MULTILINE | re.IGNORECASE)
            current_path = None
            for line in text.split('\n'):
                path_match = re.match(r'^\s{2}(/[^\s]+):', line)
                if path_match:
                    current_path = path_match.group(1)
                    continue
                if current_path:
                    method_match = re.match(r'^\s{4}(get|post|put|delete|patch|head|options):', line)
                    if method_match:
                        endpoints.append({
                            'url': current_path,
                            'method': method_match.group(1).upper(),
                            'source': f'{source_url} (openapi)',
                            'line': None,
                            'confidence': 'high',
                        })
        except Exception:
            pass
        return endpoints

    def _parse_page(self, resp):
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')
        page_url = resp.url

        scripts = []
        links = []
        forms = []
        api_patterns = []

        for script in soup.find_all('script'):
            src = script.get('src')
            if src:
                resolved = self.resolve_url(src)
                if resolved:
                    scripts.append(resolved)
                    norm = self.normalize_url(resolved)
                    if norm not in [js['url'] for js in self.js_files]:
                        try:
                            js_resp = self.session.get(resolved, timeout=self.timeout)
                            if 'javascript' in js_resp.headers.get('Content-Type', '') or resolved.endswith('.js'):
                                content = js_resp.text
                                if self.deobfuscate and len(content) > 10000:
                                    content = self._deobfuscate_js(content)
                                self.js_files.append({'url': resolved, 'content': content})
                                # Check for third-party APIs in JS
                                tps = self._match_third_party_apis(content, resolved)
                                for ep in tps:
                                    self.endpoints_from_html.append(ep)
                                    self.discovery_stats['third_party_endpoints'] = self.discovery_stats.get('third_party_endpoints', 0) + 1
                                # Check for source map references
                                if self.source_maps:
                                    sm_matches = re.findall(r'/[/#]\s*sourceMappingURL\s*=\s*([^\s]+)', content)
                                    for sm_match in sm_matches:
                                        sm_url = self.resolve_url(sm_match) if not sm_match.startswith('http') else sm_match
                                        if sm_url and sm_url not in self.visited_urls:
                                            self.visited_urls.add(sm_url)  # Track but don't count as page
                                            saved = self.timeout
                                            self.timeout = self.discovery_timeout
                                            self._check_source_maps()
                                            self.timeout = saved
                        except requests.RequestException:
                            pass
            else:
                inline_js = script.string
                if inline_js and inline_js.strip():
                    api_patterns.extend(self._extract_from_inline_js(inline_js, page_url))

        for link_tag in soup.find_all('link'):
            rel = (link_tag.get('rel') or [])
            as_attr = link_tag.get('as', '')
            href = link_tag.get('href', '')
            if href and ('script' in as_attr or 'modulepreload' in rel or 'preload' in rel and as_attr == 'script'):
                resolved = self.resolve_url(href)
                if resolved:
                    scripts.append(resolved)
                    norm = self.normalize_url(resolved)
                    if norm not in [js['url'] for js in self.js_files]:
                        try:
                            js_resp = self.session.get(resolved, timeout=self.timeout)
                            if 'javascript' in js_resp.headers.get('Content-Type', '') or resolved.endswith('.js'):
                                content = js_resp.text
                                if self.deobfuscate and len(content) > 10000:
                                    content = self._deobfuscate_js(content)
                                self.js_files.append({'url': resolved, 'content': content})
                        except requests.RequestException:
                            pass

        # Import map parsing
        importmap_script = soup.find('script', type='importmap')
        if importmap_script and importmap_script.string:
            try:
                importmap = json.loads(importmap_script.string)
                imports = importmap.get('imports', {}) or {}
                for url in imports.values():
                    resolved = self.resolve_url(url)
                    if resolved:
                        scripts.append(resolved)
                        norm = self.normalize_url(resolved)
                        if norm not in [js['url'] for js in self.js_files]:
                            try:
                                js_resp = self.session.get(resolved, timeout=self.timeout)
                                if 'javascript' in js_resp.headers.get('Content-Type', '') or resolved.endswith('.js'):
                                    content = js_resp.text
                                    if self.deobfuscate and len(content) > 10000:
                                        content = self._deobfuscate_js(content)
                                    self.js_files.append({'url': resolved, 'content': content})
                            except requests.RequestException:
                                pass
            except json.JSONDecodeError:
                pass

        # Link extraction + API pattern detection
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            resolved = self.resolve_url(href)
            if resolved:
                links.append(href)
                if self._is_api_like_path(href):
                    api_patterns.append({
                        'url': href,
                        'method': 'GET',
                        'source': f'{page_url} (link)',
                        'line': None,
                    })

        # Form extraction
        for form in soup.find_all('form', action=True):
            action = form['action'].strip()
            method = form.get('method', 'GET').upper() or 'GET'
            if action:
                resolved = self.resolve_url(action)
                if resolved:
                    forms.append({'action': action, 'method': method})
                    if self._is_api_like_path(action):
                        api_patterns.append({
                            'url': action,
                            'method': method,
                            'source': f'{page_url} (form)',
                            'line': None,
                        })

        # Meta refresh
        for meta in soup.find_all('meta'):
            http_equiv = meta.get('http-equiv', '')
            content = meta.get('content', '')
            if 'refresh' in http_equiv.lower() and 'url=' in content:
                redirect_url = content.split('url=')[-1].strip()
                resolved = self.resolve_url(redirect_url)
                if resolved:
                    links.append(resolved)

        # Modulepreload / preload link extraction (already handled above)

        # JSON-LD script extraction
        for script in soup.find_all('script', type='application/ld+json'):
            if script.string:
                try:
                    ld_data = json.loads(script.string)
                    ld_eps = self._hunt_json_for_apis(ld_data, f'{page_url} (jsonld)', page_url)
                    self.endpoints_from_html.extend(ld_eps)
                    api_patterns.extend(ld_eps)
                except json.JSONDecodeError:
                    pass

        return {
            'url': page_url,
            'title': soup.title.string if soup.title else '',
            'scripts': scripts,
            'links': links,
            'forms': forms,
            'api_patterns': api_patterns,
        }

    def _extract_from_inline_js(self, js_code, page_url):
        patterns = []
        api_re = re.compile(
            r"""['"`](https?://[^'"`\s]+)['"`]|
            ['"`](/[^'"`\s]*(?:/api/|/v[1-9]/|/graphql|/rest/|/swagger)[^'"`\s]*)['"`]|
            (?:fetch|axios|getJSON|ajax)\s*\(?\s*['"`]([^'"`\s]+)['"`]|
            (?:gql|graphql)\s*`([^`]+)`|
            (?:WebSocket|EventSource)\s*\(['"`]([^'"`\s]+)['"`]""",
            re.IGNORECASE
        )
        for match in api_re.finditer(js_code):
            url = next(g for g in match.groups() if g)
            if url and self._is_api_like_path(url):
                patterns.append({
                    'url': url,
                    'method': 'GET',
                    'source': f'{page_url} (inline)',
                    'line': None,
                })
        return patterns

    def _is_api_like_path(self, path):
        if not path or len(path) < 3:
            return False
        # Skip obvious non-API patterns
        skip_patterns = [
            r'\.(css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|mp4|mp3|ogg|webm|pdf|zip|tar|gz)$',
            r'^#', r'^mailto:', r'^tel:', r'^javascript:',
            r'^chrome-extension://', r'^moz-extension://',
            r'^blob:', r'^data:', r'^file:',
        ]
        for sp in skip_patterns:
            if re.search(sp, path, re.IGNORECASE):
                return False

        if re.match(r'^https?://', path, re.IGNORECASE):
            parsed = urlparse(path)
            return self._is_api_like_path(parsed.path) if parsed.path else True
        if re.match(r'^//', path):
            return True
        if re.match(r'^/', path) and API_KEYWORDS_PATTERN.search(path):
            return True
        if re.search(r'\.(json|php|aspx|ashx|do|action|jsp|rss|atom)$', path, re.IGNORECASE):
            return True
        # Additional patterns
        if re.search(r'/[a-z]+/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', path, re.IGNORECASE):
            return True  # UUID in path = likely API
        if re.search(r'/api/', path, re.IGNORECASE) or re.search(r'/v\d+/', path):
            return True
        if re.search(r'/graphql', path, re.IGNORECASE) or re.search(r'/gql', path, re.IGNORECASE):
            return True
        return False
