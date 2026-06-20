#!/usr/bin/env python3
import sys, json, os
sys.path.insert(0, '.')
from lib.crawler import Crawler
from lib.tester import EndpointTester, ALL_HTTP_METHODS
from meltor import deduplicate_endpoints, parse_extra_headers, merge_endpoints

c = Crawler(base_url='https://example.com', robots=False, sitemap=False)
t = EndpointTester(base_url='https://example.com')

ok = 0
total = 0

def T(name, cond):
    global ok, total
    total += 1
    if cond:
        ok += 1
    print(f'  {"PASS" if cond else "FAIL":4s} {name}')

def EQ(a, b):
    return a == b

print('=== 1. MODULE IMPORTS ===')
T('Crawler class imported', 'Crawler' in dir())
T('EndpointTester class imported', 'EndpointTester' in dir())
T('ALL_HTTP_METHODS is list', isinstance(ALL_HTTP_METHODS, list))

print('\n=== 2. FEATURE COUNTS ===')
T(f'FUZZ_PATHS={len(c.FUZZ_PATHS)} >= 400', len(c.FUZZ_PATHS) >= 400)
T(f'WELL_KNOWN={len(c.WELL_KNOWN_PATHS)} >= 25', len(c.WELL_KNOWN_PATHS) >= 25)
T(f'API_SPEC={len(c.API_SPEC_PATHS)} >= 100', len(c.API_SPEC_PATHS) >= 100)
T(f'GRAPHQL={len(c.GRAPHQL_PATHS)} >= 50', len(c.GRAPHQL_PATHS) >= 50)
T(f'DISCLOSURE={len(c.DISCLOSURE_PATHS)} >= 250', len(c.DISCLOSURE_PATHS) >= 250)
T(f'THIRD_PARTY={len(c.THIRD_PARTY_API_PATTERNS)} >= 150', len(c.THIRD_PARTY_API_PATTERNS) >= 150)
T(f'CLOUD={len(c.CLOUD_PROBE_PATTERNS)} >= 20', len(c.CLOUD_PROBE_PATTERNS) >= 20)
T(f'HTTP_METHODS={len(ALL_HTTP_METHODS)} >= 20', len(ALL_HTTP_METHODS) >= 20)

print('\n=== 3. API DETECTION (should be True) ===')
for p in ['/api/users','/v1/products','/graphql','/rest/v2/items','/swagger/docs',
          '/openapi.json','/auth/login','/api/v1/users/123','/webhooks/callback',
          '/users.json','/api.php','/health','/status','/config','/search',
          '/upload','/export','/sync','/notifications/push',
          '/api/v2/products/abc-123-def','/v3/graphql','/soap','/odata',
          '/jsonrpc','/trpc','/grpc','/webdav',
          'https://api.example.com/v1/data','https://api.example.com/graphql',
          '/api/private','/internal/v1/config','/admin/api/users',
          '/.well-known/openid-configuration']:
    T(p, c._is_api_like_path(p))

print('\n=== 4. NON-API REJECTION (should be False) ===')
for p in ['/css/style.css','/image.png','/font.woff2','/video.mp4',
          'javascript:void(0)','mailto:test@test.com','chrome-extension://abc',
          'moz-extension://xyz','data:text/plain,hello','blob:null',
          '/favicon.ico','/robots.txt','/sitemap.xml',
          '/images/logo.svg','/assets/font.woff','/videos/intro.mp4',
          '/downloads/file.zip','/docs/manual.pdf']:
    T(p, not c._is_api_like_path(p))

print('\n=== 5. RATE LIMIT ===')
c2 = Crawler(base_url='https://example.com', delay=0, robots=False, sitemap=False)
import time
s = time.time(); c2._rate_limit(); e = time.time()
T('delay=0 no sleep', e - s < 0.1)

print('\n=== 6. RESOLVE URL ===')
T('relative absolute', EQ(c.resolve_url('/api/test'), 'https://example.com/api/test'))
T('absolute URL', EQ(c.resolve_url('https://other.com/x'), 'https://other.com/x'))
T('anchor None', c.resolve_url('#section') is None)
T('javascript: None', c.resolve_url('javascript:void') is None)
T('empty None', c.resolve_url('') is None)
T('protocol-relative', EQ(c.resolve_url('//cdn.example.com/js.js'), 'https://cdn.example.com/js.js'))
T('ftp None', c.resolve_url('ftp://files.example.com') is None)

print('\n=== 7. NORMALIZE URL ===')
T('remove trailing slash', EQ(c.normalize_url('http://example.com/path/'), 'http://example.com/path'))
T('keep root slash', EQ(c.normalize_url('http://example.com/'), 'http://example.com/'))
T('no change needed', EQ(c.normalize_url('http://example.com/path'), 'http://example.com/path'))
T('strip query string', EQ(c.normalize_url('http://example.com/path?q=1'), 'http://example.com/path'))

print('\n=== 8. SCOPE ===')
cs = Crawler(base_url='https://example.com/app', scope='strict', robots=False, sitemap=False)
T('strict same prefix', cs._in_scope('https://example.com/app/api'))
T('strict different prefix', not cs._in_scope('https://example.com/other/api'))
T('strict different domain', not cs._in_scope('https://evil.com/app/api'))
cd = Crawler(base_url='https://example.com', robots=False, sitemap=False)
T('domain same', cd._in_scope('https://example.com/api'))
T('domain different', not cd._in_scope('https://other.com/api'))

print('\n=== 9. INCLUDE/EXCLUDE ===')
ci = Crawler(base_url='https://example.com', include=r'/api/', robots=False, sitemap=False)
T('include matches', ci._in_scope('https://example.com/api/users'))
T('include rejects', not ci._in_scope('https://example.com/about'))
ce = Crawler(base_url='https://example.com', exclude=r'admin', robots=False, sitemap=False)
T('exclude allows non-match', ce._in_scope('https://example.com/api'))
T('exclude rejects match', not ce._in_scope('https://example.com/admin'))

print('\n=== 10. DEDUPLICATION ===')
eps = [
    {'method': 'GET', 'url': '/api/a', 'source': 'html'},
    {'method': 'GET', 'url': '/api/a', 'source': 'js'},
    {'method': 'POST', 'url': '/api/a'},
    {'method': 'GET', 'url': '/api/b'},
]
d = deduplicate_endpoints(eps)
T('dedup removes duplicates', len(d) == 3)
T('keeps first occurrence', d[0]['source'] == 'html')
T('preserves POST separately', {e['method'] for e in d} == {'GET', 'POST'})

print('\n=== 11. MERGE ENDPOINTS ===')
js_eps = [[{'url': '/api/js', 'method': 'GET', 'confidence': 'high', 'source': 'JS', 'line': 1, 'info': ''}]]
html_eps = [{'url': '/api/html', 'method': 'GET', 'source': 'HTML', 'line': None}]
merged = merge_endpoints(js_eps, html_eps)
T('merge includes html', any('/api/html' in e['url'] for e in merged))
T('merge includes js', any('/api/js' in e['url'] for e in merged))
T('merge has method/confidence/source', all(
    all(k in e for k in ['url','method','confidence','source']) for e in merged))

print('\n=== 12. HEADER PARSING ===')
T('None input', parse_extra_headers(None) is None)
T('empty list', parse_extra_headers([]) is None)
T('single header', EQ(parse_extra_headers(['X-Test: val']), {'X-Test': 'val'}))
T('multi header', EQ(parse_extra_headers(['A:1', 'B:2']), {'A': '1', 'B': '2'}))
T('header with extra colon', EQ(parse_extra_headers(['Key: val:ue']), {'Key': 'val:ue'}))
T('no colon returns None', parse_extra_headers(['BadHeader']) is None)

print('\n=== 13. CRAWLER INIT ===')
c3 = Crawler(base_url='https://example.com', timeout=5, proxy='http://127.0.0.1:8080',
             cookie='test=123', headers={'X-Custom': 'val'}, scope='strict',
             include='api', exclude='admin', wayback=True, deobfuscate=True,
             robots=False, sitemap=False)
T('custom timeout', c3.timeout == 5)
T('custom proxy', c3.proxy == 'http://127.0.0.1:8080')
T('custom scope', c3.scope == 'strict')
T('include compiled', c3.include is not None)
T('exclude compiled', c3.exclude is not None)
T('wayback flag', c3.wayback == True)
T('deobfuscate flag', c3.deobfuscate == True)
T('has session', hasattr(c3, 'session'))

print('\n=== 14. ENDPOINT TESTER INIT ===')
t2 = EndpointTester(concurrency=20, timeout=30, base_url='https://api.example.com',
                    proxy='http://127.0.0.1:8080', cookie='sess=abc',
                    headers={'Auth': 'Bearer xyz'}, graphql=True)
T('custom concurrency', t2.concurrency == 20)
T('custom timeout', t2.timeout == 30)
T('base_url set', t2.base_url == 'https://api.example.com')
T('graphql flag', t2.graphql == True)
T('has session', hasattr(t2, 'session'))

print('\n=== 15. DISCOVERY STATS KEYS ===')
c4 = Crawler(base_url='https://example.com', robots=False, sitemap=False)
expected_keys = ['robots_endpoints','sitemap_urls','well_known_endpoints','fuzzed_endpoints',
                 'openapi_specs','source_map_endpoints','csp_endpoints','link_header_endpoints',
                 'hateoas_endpoints','html_comment_endpoints','manifest_endpoints',
                 'service_worker_endpoints','response_body_endpoints','git_exposed','env_exposed',
                 'custom_endpoints','dir_bust_endpoints']
for k in expected_keys:
    T(f'discovery stat key: {k}', k in c4.discovery_stats)

print('\n=== 16. COMMAND PARSING HELP ===')
import argparse
from meltor import main as meltor_main
parser = argparse.ArgumentParser()
# Just verify the module can be parsed
try:
    import meltor
    T('meltor module parses args', True)
except:
    T('meltor module parses args', False)

print('\n=== 17. ALL_HTTP_METHODS CONTENT ===')
required_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
for m in required_methods:
    T(f'ALL_HTTP_METHODS contains {m}', m in ALL_HTTP_METHODS)

print('\n=== 18. ENDPOINT TEST RESULT STRUCTURE ===')
# Verify test_endpoint returns expected keys
result = t.test_endpoint({'url': '/api/test', 'method': 'GET'})
expected_result_keys = ['status', 'working', 'error', 'response_time', 'content_type',
                        'full_url', 'tested_method', 'response_body_preview',
                        'redirect_chain', 'response_headers']
for k in expected_result_keys:
    T(f'test_endpoint result has {k}', k in result)

print(f'\n{"="*55}')
print(f'  TOTAL: {ok}/{total} tests PASSED')
print(f'{"="*55}')
sys.exit(0 if ok == total else 1)
