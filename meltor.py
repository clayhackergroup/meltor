#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MELTOR by spidey — API Endpoint Discovery & Validation Tool (Ultimate Edition)
Crawls websites, scans frontend JS, finds ALL API endpoints, tests & filters working ones.

Usage:
  python meltor.py https://example.com
  python meltor.py https://example.com --depth 5 --max-pages 50 -o results
  python meltor.py https://example.com --no-test --quiet
  python meltor.py https://example.com --cookie "session=abc123" --proxy http://127.0.0.1:8080
  python meltor.py https://example.com --scope strict --format html
  python meltor.py https://example.com --header "X-API-Key: secret" --ci
  python meltor.py https://example.com -o report --format all
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger('meltor')

BASE_DIR = Path(__file__).parent.absolute()
LIB_DIR = BASE_DIR / 'lib'


def check_python_deps():
    missing = []
    for mod in ['requests', 'bs4', 'colorama']:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        req_file = BASE_DIR / 'requirements.txt'
        sys.stderr.write(f'[~] Installing Python dependencies: {", ".join(missing)}...\n')
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def check_js_deps():
    node_modules = BASE_DIR / 'node_modules'
    if not (node_modules / 'acorn').exists():
        sys.stderr.write('[~] Installing JS dependencies (acorn)...\n')
        subprocess.check_call(
            ['npm', 'install', '--no-audit', '--no-fund'],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def parse_extra_headers(headers_list):
    if not headers_list:
        return None
    headers = {}
    for h in headers_list:
        if ':' in h:
            key, _, value = h.partition(':')
            headers[key.strip()] = value.strip()
    return headers if headers else None


def run_js_extractor(js_content, temp_dir, source_url=''):
    if not js_content or not js_content.strip():
        return []

    fd = None
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix='.js', dir=temp_dir)
        with os.fdopen(fd, 'w', encoding='utf-8', errors='replace') as f:
            f.write(js_content)
        fd = None

        extractor_path = LIB_DIR / 'extractor.js'
        cmd = ['node', str(extractor_path), temp_path]
        if source_url:
            cmd.append(source_url)
        result = subprocess.run(cmd,
            capture_output=True, text=True,
            timeout=60,
            cwd=str(BASE_DIR)
        )

        if result.returncode != 0:
            logger.debug(f'JS extractor error: {result.stderr[:200]}')
            return []

        output = result.stdout.strip()
        if not output:
            return []

        endpoints = json.loads(output)
        # Filter out any path that looks like it might have been truncated
        clean = []
        for ep in endpoints if isinstance(endpoints, list) else []:
            url = ep.get('url', '')
            # Remove trailing garbage from template literals
            if url and len(url) < 5000 and not any(skip in url for skip in ['function(', 'function ']):
                clean.append(ep)
        return clean

    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        logger.debug(f'JS extractor: {e}')
        return []
    except Exception as e:
        logger.debug(f'JS extractor error: {e}')
        return []
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def deduplicate_endpoints(endpoints):
    seen = set()
    unique = []
    for ep in endpoints:
        key = f"{ep.get('method', 'GET').upper()}:{ep.get('url', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(ep)
    return unique


def merge_endpoints(js_endpoints_list, html_endpoints):
    merged = []
    for ep in html_endpoints:
        merged.append({
            'url': ep.get('url', ''),
            'method': ep.get('method', 'GET').upper(),
            'confidence': ep.get('confidence', 'medium'),
            'source': ep.get('source', 'HTML'),
            'line': ep.get('line'),
            'info': ep.get('info', 'html'),
        })

    for eps in js_endpoints_list:
        for ep in eps:
            merged.append({
                'url': ep.get('url', ''),
                'method': ep.get('method', 'GET').upper(),
                'confidence': ep.get('confidence', 'medium'),
                'source': ep.get('source', 'JS'),
                'line': ep.get('line'),
                'info': ep.get('info', ''),
            })

    return deduplicate_endpoints(merged)


def print_discovery_stats(stats):
    from colorama import Fore, Style
    from lib.reporter import C_PRIMARY, C_INFO, C_OK, C_NAVY, C_DIM

    if not stats:
        return
    interesting = {
        'robots_endpoints': 'Robots.txt Endpoints',
        'sitemap_urls': 'Sitemap URLs',
        'well_known_endpoints': '.well-known Endpoints',
        'fuzzed_endpoints': 'Fuzzed Endpoints',
        'openapi_specs': 'OpenAPI/Swagger Specs',
        'openapi_endpoints': 'OpenAPI Endpoints',
        'source_map_endpoints': 'Source Map Endpoints',
        'csp_endpoints': 'CSP Header Endpoints',
        'link_header_endpoints': 'Link Header Endpoints',
        'hateoas_endpoints': 'HATEOAS Endpoints',
        'html_comment_endpoints': 'HTML Comment Endpoints',
        'manifest_endpoints': 'Manifest Endpoints',
        'service_worker_endpoints': 'Service Worker Endpoints',
        'response_body_endpoints': 'Response Body Endpoints',
        'third_party_endpoints': 'Third-Party APIs',
        'git_exposed': 'Git Exposed',
        'env_exposed': 'Env Exposed',
        'custom_endpoints': 'Custom Endpoints',
        'dir_bust_endpoints': 'Dir Bust Endpoints',
    }
    print(f"\n  {C_NAVY}{Style.BRIGHT}┌{'─' * 46}┐{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_PRIMARY}{Style.BRIGHT}DISCOVERY BREAKDOWN{' ' * 28}{C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}├{'─' * 46}┤{Style.RESET_ALL}")
    has_any = False
    for key, label in interesting.items():
        val = stats.get(key, 0)
        if val:
            has_any = True
            padding = 30 - len(label)
            print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_DIM}{label}{' ' * padding}{Style.RESET_ALL} {C_OK}{Style.BRIGHT}{val}{Style.RESET_ALL}  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    if not has_any:
        print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_DIM}(standard crawl only, use --deep --fuzz for more){' ' * 10}{C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}└{'─' * 46}┘{Style.RESET_ALL}")


def main():
    parser = argparse.ArgumentParser(
        description='MELTOR by spidey — API Endpoint Discovery & Validation Tool (Ultimate Edition)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
All discovery features are ON by default. Use individual flags only to confirm.
Examples:
  python meltor.py https://example.com
  python meltor.py https://example.com --depth 5 --max-pages 50 -o results
  python meltor.py https://example.com --no-test --quiet
  python meltor.py https://example.com --cookie "session=abc123" --proxy http://127.0.0.1:8080
  python meltor.py https://example.com --header "Authorization: Bearer token" --header "X-API-Key: key"
  python meltor.py https://example.com --scope strict --format html -o report
  python meltor.py https://example.com --include "/api" --exclude "admin" --delay 1 --jitter 0.5
  python meltor.py https://example.com --ci --format all -o output
        """
    )
    parser.add_argument('url', nargs='?', help='Target URL to scan')
    parser.add_argument('--depth', type=int, default=3, help='Crawl depth (default: 3)')
    parser.add_argument('--max-pages', type=int, default=30, help='Max pages to crawl (default: 30)')
    parser.add_argument('--concurrency', type=int, default=15, help='Concurrent requests for testing (default: 15)')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout in seconds (default: 10)')
    parser.add_argument('--output', '-o', help='Output file path (base name, without extension)')
    parser.add_argument('--format', choices=['json', 'csv', 'html', 'all'], default='json', help='Output format(s) (default: json)')
    parser.add_argument('--no-test', action='store_true', help='Skip endpoint testing (discovery only)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Less verbose output')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    parser.add_argument('--cookie', help='Cookie string to include in requests (e.g. "session=abc123")')
    parser.add_argument('--header', action='append', dest='headers', help='Custom header (can be used multiple times, e.g. --header "Key: Value")')
    parser.add_argument('--bearer', help='Bearer token for Authorization header (shorthand for --header "Authorization: Bearer <token>")')

    parser.add_argument('--proxy', help='Proxy URL (e.g. http://127.0.0.1:8080)')

    parser.add_argument('--scope', choices=['same-domain', 'strict'], default='same-domain', help='Crawl scope: same-domain (default) or strict (URL prefix)')
    parser.add_argument('--include', help='Only crawl URLs matching this regex pattern')
    parser.add_argument('--exclude', help='Skip URLs matching this regex pattern')

    parser.add_argument('--delay', type=float, default=0.2, help='Delay between requests in seconds (default: 0.2)')
    parser.add_argument('--jitter', type=float, default=0, help='Random jitter added to delay (default: 0)')

    parser.add_argument('--wayback', action='store_true', default=True, help='Fetch historical URLs from Wayback Machine (default: on)')
    parser.add_argument('--graphql', action='store_true', default=True, help='Test GraphQL introspection on discovered endpoints (default: on)')
    parser.add_argument('--deobfuscate', action='store_true', default=True, help='Attempt to deobfuscate/decompress JavaScript files (default: on)')
    parser.add_argument('--ci', action='store_true', help='CI mode: exit non-zero if endpoints are found')

    # Advanced discovery options
    parser.add_argument('--deep', action='store_true', default=True, help='Enable deep discovery (cloud storage probes, response body scanning, etc.) (default: on)')
    parser.add_argument('--fuzz', action='store_true', default=True, help='Fuzz common API paths (200+ paths) (default: on)')
    parser.add_argument('--crawl-apis', action='store_true', default=True, help='Also crawl discovered API endpoints for more links (default: on)')
    parser.add_argument('--all-sources', action='store_true', help='(default behavior, kept for backward compatibility)')
    parser.add_argument('--endpoints-file', help='Path to a .txt file with custom endpoint paths (one per line) to probe')
    parser.add_argument('--dir-bust', action='store_true', default=True, help='Discover dirs then probe API resources under them (default: on)')
    parser.add_argument('--dir-depth', type=int, default=2, help='Directory busting recursion depth (default: 2)')

    # Individual source toggles
    parser.add_argument('--robots', action='store_true', default=True, help='Parse robots.txt (default: on)')
    parser.add_argument('--sitemap', action='store_true', default=True, help='Parse sitemap.xml (default: on)')
    parser.add_argument('--well-known', action='store_true', default=True, help='Probe .well-known/ paths (default: on)')
    parser.add_argument('--source-maps', action='store_true', default=True, help='Analyze JS source maps for endpoints (default: on)')

    parser.add_argument('--all-formats', action='store_true', help='Shortcut for --format all')
    parser.add_argument('--discovery-stats', action='store_true', default=True, help='Show detailed discovery breakdown')

    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        print()
        print('  error: the following argument is required: url')
        sys.exit(1)

    # --all-sources is now the default (all features on); kept for backward compat
    if args.all_sources:
        pass  # everything is already on by default

    # --all-formats shortcut
    if args.all_formats:
        args.format = 'all'

    if args.debug:
        logging.getLogger('meltor').setLevel(logging.DEBUG)
        logging.getLogger('meltor.crawler').setLevel(logging.DEBUG)
        logging.getLogger('meltor.tester').setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger('meltor').setLevel(logging.WARNING)

    if args.bearer:
        if args.headers is None:
            args.headers = []
        args.headers.append(f'Authorization: Bearer {args.bearer}')

    extra_headers = parse_extra_headers(args.headers)

    check_python_deps()
    check_js_deps()

    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)

    from lib.reporter import Reporter, log_info, log_ok, log_warn, log_err, C_PRIMARY, C_NAVY, C_INFO, C_OK, C_ERR, C_WARN, C_DIM, C_URL
    from lib.crawler import Crawler
    from lib.tester import EndpointTester

    reporter = Reporter(quiet=args.quiet)
    reporter.print_banner()

    # Parse custom endpoints file
    custom_paths = []
    if args.endpoints_file:
        try:
            with open(args.endpoints_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        custom_paths.append(line)
            if custom_paths:
                log_info(f"Loaded {len(custom_paths)} custom paths from {args.endpoints_file}")
        except (FileNotFoundError, IOError) as e:
            log_err(f"Cannot read endpoints file: {e}")
            sys.exit(1)

    target_url = args.url.rstrip('/')
    scan_start = datetime.now()

    # ── Scan Configuration ──────────────────────────────────
    print(f"  {C_NAVY}{Style.BRIGHT}┌{'─' * 46}┐{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_PRIMARY}{Style.BRIGHT}SCAN CONFIGURATION{' ' * 28}{C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}├{'─' * 46}┤{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_DIM}Target{' ' * 27}{Style.RESET_ALL} {C_URL}{target_url}{Style.RESET_ALL}  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_DIM}Depth{' ' * 28}{Style.RESET_ALL} {C_INFO}{args.depth}{Style.RESET_ALL}    {C_DIM}Max Pages{Style.RESET_ALL} {C_INFO}{args.max_pages}{Style.RESET_ALL}  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {C_DIM}Concurrency{' ' * 22}{Style.RESET_ALL} {C_INFO}{args.concurrency}{Style.RESET_ALL}    {C_DIM}Timeout{Style.RESET_ALL} {C_INFO}{args.timeout}s{Style.RESET_ALL}  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")

    config_lines = []
    if args.delay != 0.2 or args.jitter > 0:
        config_lines.append(f"{C_DIM}Delay{Style.RESET_ALL} {C_INFO}{args.delay}s{Style.RESET_ALL}  {C_DIM}Jitter{Style.RESET_ALL} {C_INFO}{args.jitter}s{Style.RESET_ALL}")
    if args.scope != 'same-domain':
        config_lines.append(f"{C_DIM}Scope{Style.RESET_ALL} {C_INFO}{args.scope}{Style.RESET_ALL}")
    if args.include:
        config_lines.append(f"{C_DIM}Include{Style.RESET_ALL} {C_INFO}{args.include}{Style.RESET_ALL}")
    if args.exclude:
        config_lines.append(f"{C_DIM}Exclude{Style.RESET_ALL} {C_INFO}{args.exclude}{Style.RESET_ALL}")
    features = []
    if args.wayback: features.append('Wayback')
    if args.graphql: features.append('GraphQL')
    if args.deobfuscate: features.append('Deobfuscate')
    if args.fuzz: features.append('Fuzzing')
    if args.deep: features.append('Deep')
    if args.crawl_apis: features.append('CrawlAPIs')
    if args.source_maps: features.append('SourceMaps')
    if args.well_known: features.append('WellKnown')
    if args.dir_bust and args.dir_depth > 0: features.append(f'DirBust({args.dir_depth})')
    if args.proxy: features.append('Proxy')
    if args.cookie or args.bearer or args.headers: features.append('Auth')
    if args.endpoints_file:
        features.append(f'CustomPaths({len(custom_paths)})')
    if features:
        config_lines.append(f"{C_DIM}Features{Style.RESET_ALL} {C_INFO}{', '.join(features)}{Style.RESET_ALL}")

    for line in config_lines:
        print(f"  {C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}  {line}{' ' * (44 - len(line))}{C_NAVY}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {C_NAVY}{Style.BRIGHT}└{'─' * 46}┘{Style.RESET_ALL}")
    print()

    # ── Phase 1: Crawl ──────────────────────────────────────
    log_info(f"Starting crawl on {C_URL}{target_url}{C_INFO} ...")

    crawler = Crawler(
        base_url=target_url,
        max_depth=args.depth,
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay=args.delay,
        jitter=args.jitter,
        proxy=args.proxy,
        cookie=args.cookie,
        headers=extra_headers,
        scope=args.scope,
        include=args.include,
        exclude=args.exclude,
        wayback=args.wayback,
        deobfuscate=args.deobfuscate,
        fuzz=args.fuzz,
        deep=args.deep,
        crawl_apis=args.crawl_apis,
        sitemap=args.sitemap,
        robots=args.robots,
        well_known=args.well_known,
        source_maps=args.source_maps,
        custom_paths=custom_paths,
        dir_bust=args.dir_bust,
        dir_depth=args.dir_depth,
    )

    crawl_results = crawler.crawl()
    pages = crawl_results['pages']
    js_files = crawl_results['js_files']
    html_endpoints = crawl_results['html_endpoints']
    openapi_specs = crawl_results.get('openapi_specs', [])
    discovery_stats = crawl_results.get('discovery_stats', {})

    if not pages and not js_files and not openapi_specs:
        log_err(f"No pages could be crawled. Check the URL and try again.")
        sys.exit(1)

    log_ok(f"Crawled {C_URL}{len(pages)} pages{Style.RESET_ALL}{C_OK}, found {C_URL}{len(js_files)} JS files{Style.RESET_ALL}{C_OK}, {C_URL}{len(html_endpoints)} raw endpoints{Style.RESET_ALL}{C_OK}.")

    if openapi_specs:
        for spec in openapi_specs:
            ep_count = len(spec.get('endpoints', []))
            log_ok(f"API spec: {C_URL}{spec['url']}{Style.RESET_ALL}{C_OK} ({ep_count} endpoints)")

    if html_endpoints:
        log_ok(f"Found {C_URL}{len(html_endpoints)} API patterns{Style.RESET_ALL}{C_OK} from all sources.")

    # Print discovery stats breakdown
    if args.discovery_stats and discovery_stats:
        print_discovery_stats(discovery_stats)

    # ── Phase 2: JS Analysis ────────────────────────────────
    log_info(f"Analyzing JavaScript files for API endpoints ...")
    print()

    temp_dir = tempfile.mkdtemp(prefix='meltor_')
    try:
        all_js_endpoints = []
        total_js = len(js_files)
        for idx, js in enumerate(js_files, 1):
            content = js.get('content', '')
            js_url = js.get('url', 'unknown')
            if content.strip():
                log_info(f"  [{C_PRIMARY}{idx}{C_INFO}/{C_PRIMARY}{total_js}{C_INFO}] Analyzing: {C_DIM}{js_url}{C_INFO}")
                eps = run_js_extractor(content, temp_dir, js.get('url', ''))
                if eps:
                    all_js_endpoints.append(eps)
                    log_ok(f"    \u2192 {C_URL}{len(eps)} endpoints{Style.RESET_ALL}{C_OK} extracted.")
            else:
                log_warn(f"  [{C_PRIMARY}{idx}{C_WARN}/{C_PRIMARY}{total_js}{C_WARN}] Skipping empty: {C_DIM}{js_url}{C_WARN}")

        all_endpoints = merge_endpoints(all_js_endpoints, html_endpoints)

        results = {
            'target': target_url,
            'pages': pages,
            'js_files': js_files,
            'html_endpoints': html_endpoints,
            'js_endpoints': all_endpoints,
            'openapi_specs': openapi_specs,
        }

        total_unique = len(all_endpoints)
        log_ok(f"Total unique API endpoints discovered: {C_URL}{total_unique}{Style.RESET_ALL}{C_OK}.")
        print()

        # ── Phase 3: Testing ────────────────────────────────
        if not args.no_test and total_unique > 0:
            tester = EndpointTester(
                concurrency=args.concurrency,
                timeout=args.timeout,
                base_url=target_url,
                proxy=args.proxy,
                cookie=args.cookie,
                headers=extra_headers,
                graphql=args.graphql,
                extract_body_apis=args.deep or args.crawl_apis,
            )

            log_info(f"Testing {C_URL}{total_unique}{C_INFO} endpoints (concurrency={args.concurrency}) ...")
            print()

            tested = tester.test_all(all_endpoints)
            results['tested'] = tested

            # Incorporate newly discovered endpoints from response bodies
            if tester.discovered_from_responses:
                log_ok(f"Discovered {C_URL}{len(tester.discovered_from_responses)}{C_OK} additional endpoints from response bodies (HATEOAS).")
                deduped_new = deduplicate_endpoints(tester.discovered_from_responses)
                new_from_bodies = [e for e in deduped_new
                                   if f"{e.get('method', 'GET')}:{e.get('url', '')}" not in
                                   {f"{x.get('method','GET')}:{x.get('url','')}" for x in all_endpoints}]
                if new_from_bodies:
                    log_ok(f"  New unique endpoints: {C_URL}{len(new_from_bodies)}{C_OK}")
                    all_endpoints.extend(new_from_bodies)
                    # Also test these new endpoints
                    tested_new = tester.test_all(new_from_bodies)
                    tested.extend(tested_new)

            working = [e for e in tested if e.get('working')]

            bar_len = 40
            if total_unique > 0:
                pct = len(working) / total_unique if total_unique > 0 else 0
                filled = int(bar_len * pct)
                bar = f"{C_OK}{'█' * filled}{C_DIM}{'─' * (bar_len - filled)}{Style.RESET_ALL}"
                log_ok(f"Testing complete: {C_OK}{len(working)} working{Style.RESET_ALL}, {C_ERR}{len(tested) - len(working)} non-working{Style.RESET_ALL}")
                log_info(f"  Success rate: {C_OK}{pct*100:.1f}%{Style.RESET_ALL}  {bar}")
            else:
                log_warn("No endpoints to test.")

            print()
            reporter.print_results(results, target_url, scan_start)

        elif args.no_test:
            log_info("Discovery mode — skipping endpoint testing.")
            print()
            reporter.print_discovery_only(results, target_url, scan_start)
        else:
            log_warn("No endpoints found to test.")

        # ── Output ──────────────────────────────────────────
        if args.output:
            reporter.save_output(results, target_url, scan_start, args.output, args.format)
            ext_label = args.format if args.format != 'all' else '{json, csv, html}'
            log_ok(f"Results saved to {C_URL}{args.output}.{ext_label}{Style.RESET_ALL}{C_OK}.")

        if args.ci and total_unique > 0:
            log_warn(f"CI mode: {total_unique} endpoints discovered, exiting with code 1.")
            sys.exit(1)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ── Done ────────────────────────────────────────────────
    duration = (datetime.now() - scan_start).total_seconds()
    print()
    print(f"  {C_PRIMARY}{Style.BRIGHT}═══ MELTOR scan completed in {duration:.1f}s ═══{Style.RESET_ALL}")
    print()


if __name__ == '__main__':
    main()
