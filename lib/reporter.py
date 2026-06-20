# -*- coding: utf-8 -*-
import json
import csv
import io
import logging
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

try:
    from colorama import init, Fore, Back, Style
    init()
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
        LIGHTRED_EX = LIGHTGREEN_EX = LIGHTYELLOW_EX = LIGHTBLUE_EX = LIGHTCYAN_EX = LIGHTMAGENTA_EX = LIGHTWHITE_EX = ''
    class Back:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
        LIGHTBLACK_EX = LIGHTRED_EX = LIGHTGREEN_EX = LIGHTYELLOW_EX = LIGHTBLUE_EX = LIGHTCYAN_EX = LIGHTMAGENTA_EX = LIGHTWHITE_EX = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''

# Professional color palette
C_PRIMARY = Fore.LIGHTCYAN_EX
C_NAVY = Fore.BLUE
C_INFO = Fore.LIGHTMAGENTA_EX
C_OK = Fore.GREEN
C_ERR = Fore.RED
C_WARN = Fore.YELLOW
C_DIM = Fore.LIGHTBLACK_EX
C_URL = Fore.LIGHTWHITE_EX
C_METH = Fore.LIGHTCYAN_EX

logger = logging.getLogger('meltor.reporter')


def log_info(msg):
    print(f"  {C_INFO}{Style.BRIGHT}[~]{Style.RESET_ALL} {C_INFO}{msg}{Style.RESET_ALL}")


def log_ok(msg):
    print(f"  {C_OK}{Style.BRIGHT}[+]{Style.RESET_ALL} {C_OK}{msg}{Style.RESET_ALL}")


def log_warn(msg):
    print(f"  {C_WARN}{Style.BRIGHT}[!]{Style.RESET_ALL} {C_WARN}{msg}{Style.RESET_ALL}")


def log_err(msg):
    print(f"  {C_ERR}{Style.BRIGHT}[x]{Style.RESET_ALL} {C_ERR}{msg}{Style.RESET_ALL}")


def log_raw(msg):
    print(msg)


class Reporter:
    def __init__(self, quiet=False):
        self.quiet = quiet

    def banner(self):
        return f"""{C_NAVY}{Style.BRIGHT}
    {C_PRIMARY}███    ███ {C_NAVY}███████ {C_PRIMARY}██      {C_NAVY}████████ {C_PRIMARY}██████  {C_NAVY}██████{Style.RESET_ALL}
    {C_PRIMARY}████  ████ {C_NAVY}██      {C_PRIMARY}██         {C_NAVY}██    {C_PRIMARY}██    ██ {C_NAVY}██   ██{Style.RESET_ALL}
    {C_PRIMARY}██ ████ ██ {C_NAVY}█████   {C_PRIMARY}██         {C_NAVY}██    {C_PRIMARY}██    ██ {C_NAVY}██████{Style.RESET_ALL}
    {C_PRIMARY}██  ██  ██ {C_NAVY}██      {C_PRIMARY}██         {C_NAVY}██    {C_PRIMARY}██    ██ {C_NAVY}██   ██{Style.RESET_ALL}
    {C_PRIMARY}██      ██ {C_NAVY}███████ {C_PRIMARY}███████    {C_NAVY}██     {C_PRIMARY}██████  {C_NAVY}██   ██{Style.RESET_ALL}
    {C_WARN}+--------------------------------------------------+
    |    {C_PRIMARY}MELTOR{Style.RESET_ALL} {C_WARN}by spidey — API Endpoint Discovery Engine    |
    |  {C_DIM}Web Crawler + JS Analyzer + Endpoint Validator{Style.RESET_ALL} {C_WARN}|
    |  {C_DIM}Ultimate Edition — 50+ Discovery Techniques{Style.RESET_ALL}  {C_WARN}|
    +--------------------------------------------------+{Style.RESET_ALL}
        """

    def print_banner(self):
        print(self.banner())

    def print_header(self, text, count=None):
        suffix = f'  [{count}]' if count is not None else ''
        print(f"\n  {C_PRIMARY}{Style.BRIGHT}\u258c {text.upper()}{suffix}{Style.RESET_ALL}")

    def print_subheader(self, text):
        print(f"  {C_NAVY}{Style.BRIGHT}\u2514\u2500 {text}{Style.RESET_ALL}")

    def print_result(self, endpoint):
        working = endpoint.get('working', False)
        status = endpoint.get('status')
        method = endpoint.get('tested_method', endpoint.get('method', 'GET'))
        url = endpoint.get('full_url', endpoint.get('url', ''))
        confidence = endpoint.get('confidence', '')
        source = endpoint.get('source', '')
        resp_time = endpoint.get('response_time')
        error = endpoint.get('error', '')
        info = endpoint.get('info', '')

        if working:
            badge = f"{C_OK}{Style.BRIGHT}\u2714{Style.RESET_ALL}"
            status_color = C_OK
        elif status is None or status == 0:
            badge = f"{C_ERR}{Style.BRIGHT}\u2718{Style.RESET_ALL}"
            status_color = C_ERR
        elif 300 <= status < 400:
            badge = f"{C_WARN}{Style.BRIGHT}\u27a0{Style.RESET_ALL}"
            status_color = C_WARN
        elif 400 <= status < 500:
            badge = f"{C_ERR}{Style.BRIGHT}\u2718{Style.RESET_ALL}"
            status_color = C_ERR
        elif 500 <= status < 600:
            badge = f"{C_ERR}{Style.BRIGHT}\u2718{Style.RESET_ALL}"
            status_color = C_ERR
        else:
            badge = f"{C_WARN}{Style.BRIGHT}?{Style.RESET_ALL}"
            status_color = C_WARN

        status_str = f"{status}" if status else '---'
        time_str = f" [{resp_time:.2f}s]" if resp_time else ""
        conf_str = f" [{confidence}]" if confidence else ""
        src_str = f" ({source})" if source else ""
        info_str = f" |{info}|" if info else ""

        method_colored = f"{C_METH}{Style.BRIGHT}{method:<6}{Style.RESET_ALL}"

        if error:
            print(f"  {badge} {status_color}{status_str}{Style.RESET_ALL} {method_colored} {C_URL}{url}{Style.RESET_ALL}{conf_str} {C_ERR}[{error}]{Style.RESET_ALL}")
        else:
            print(f"  {badge} {status_color}{status_str}{Style.RESET_ALL} {method_colored} {C_URL}{url}{Style.RESET_ALL}{conf_str}{C_DIM}{time_str}{Style.RESET_ALL}{C_DIM}{src_str}{Style.RESET_ALL}{C_DIM}{info_str}{Style.RESET_ALL}")

    def print_scan_summary(self, scan_info):
        print(f"\n  {C_NAVY}{Style.BRIGHT}\u250c{'\u2500' * 46}\u2510{Style.RESET_ALL}")
        print(f"  {C_NAVY}{Style.BRIGHT}\u2502{Style.RESET_ALL}  {C_PRIMARY}{Style.BRIGHT}SCAN SUMMARY{' ' * 33}{C_NAVY}{Style.BRIGHT}\u2502{Style.RESET_ALL}")
        print(f"  {C_NAVY}{Style.BRIGHT}\u251c{'\u2500' * 46}\u2524{Style.RESET_ALL}")
        for key, value in scan_info.items():
            label = key.replace('_', ' ').title()
            padding = 32 - len(label)
            print(f"  {C_NAVY}{Style.BRIGHT}\u2502{Style.RESET_ALL}  {C_DIM}{label}{' ' * padding}{Style.RESET_ALL} {C_OK}{Style.BRIGHT}{value}{Style.RESET_ALL}  {C_NAVY}{Style.BRIGHT}\u2502{Style.RESET_ALL}")
        print(f"  {C_NAVY}{Style.BRIGHT}\u2514{'\u2500' * 46}\u2518{Style.RESET_ALL}")

    def print_results(self, results, target_url, scan_start):
        pages = results.get('pages', [])
        js_files = results.get('js_files', [])
        tested = results.get('tested', [])
        openapi_specs = results.get('openapi_specs', [])

        duration = (datetime.now() - scan_start).total_seconds()

        working = [e for e in tested if e.get('working')]
        redirects = [e for e in tested if e.get('status') and 300 <= e['status'] < 400]
        client_errors = [e for e in tested if e.get('status') and 400 <= e['status'] < 500]
        server_errors = [e for e in tested if e.get('status') and 500 <= e['status'] < 600]
        failed = [e for e in tested if e.get('error') or not e.get('status')]

        total = len(tested)

        scan_info = {
            'Target': target_url,
            'Pages Crawled': len(pages),
            'JS Files Analyzed': len(js_files),
            'API Specs Found': len(openapi_specs),
            'Endpoints Tested': total,
            'Working (2xx)': len(working),
            'Redirects (3xx)': len(redirects),
            'Client Errors (4xx)': len(client_errors),
            'Server Errors (5xx)': len(server_errors),
            'Failed/Timeout': len(failed),
            'Duration': f'{duration:.1f}s',
        }

        self.print_scan_summary(scan_info)

        if working:
            self.print_header(f'Working Endpoints (2xx)', len(working))
            for ep in working:
                self.print_result(ep)

        redirects_only = [e for e in tested if 300 <= (e.get('status') or 0) < 400]
        if redirects_only:
            self.print_header(f'Redirects (3xx)', len(redirects_only))
            for ep in redirects_only:
                self.print_result(ep)

        client_only = [e for e in tested if 400 <= (e.get('status') or 0) < 500]
        if client_only:
            self.print_header(f'Client Errors (4xx)', len(client_only))
            for ep in client_only:
                self.print_result(ep)

        server_only = [e for e in tested if 500 <= (e.get('status') or 0) < 600]
        if server_only:
            self.print_header(f'Server Errors (5xx)', len(server_only))
            for ep in server_only:
                self.print_result(ep)

        failed_only = [e for e in tested if e.get('error') and not e.get('status')]
        if failed_only:
            self.print_header(f'Failed / Unreachable', len(failed_only))
            for ep in failed_only:
                self.print_result(ep)

    def print_discovery_only(self, results, target_url, scan_start):
        pages = results.get('pages', [])
        js_files = results.get('js_files', [])
        html_endpoints = results.get('html_endpoints', [])
        endpoints_from_js = []
        if 'js_endpoints' in results:
            for ep in results['js_endpoints']:
                endpoints_from_js.append(ep)
        openapi_specs = results.get('openapi_specs', [])

        duration = (datetime.now() - scan_start).total_seconds()

        combined = html_endpoints + endpoints_from_js
        unique_urls = {}
        for ep in combined:
            url = ep.get('url', '')
            if url not in unique_urls:
                unique_urls[url] = ep
        unique = list(unique_urls.values())

        scan_info = {
            'Target': target_url,
            'Pages Crawled': len(pages),
            'JS Files Analyzed': len(js_files),
            'API Specs Found': len(openapi_specs),
            'HTML Endpoints': len(html_endpoints),
            'JS Endpoints': len(endpoints_from_js),
            'Total Unique': len(unique),
            'Duration': f'{duration:.1f}s',
        }

        self.print_scan_summary(scan_info)

        if unique:
            self.print_header(f'Discovered Endpoints', len(unique))
            for ep in unique:
                method = ep.get('method', 'GET')
                url = ep.get('url', '')
                confidence = ep.get('confidence', '')
                source = ep.get('source', '')
                info = ep.get('info', '')

                cn = C_OK if confidence == 'high' else C_WARN if confidence == 'medium' else C_DIM
                method_colored = f"{C_METH}{Style.BRIGHT}{method:<6}{Style.RESET_ALL}"
                info_str = f" |{info}|" if info else ""
                print(f"  {method_colored} {C_URL}{url}{Style.RESET_ALL} {cn}[{confidence}]{Style.RESET_ALL} {C_DIM}({source}){Style.RESET_ALL}{C_DIM}{info_str}{Style.RESET_ALL}")

    def to_json(self, results, target_url):
        pages = results.get('pages', [])
        js_files = results.get('js_files', [])
        html_endpoints = results.get('html_endpoints', [])
        js_endpoints = results.get('js_endpoints', [])
        tested = results.get('tested', [])
        openapi_specs = results.get('openapi_specs', [])
        discovery_stats = results.get('discovery_stats', {})

        output = {
            'tool': 'MELTOR by spidey (Ultimate Edition)',
            'target': target_url,
            'scan_time': datetime.now().isoformat(),
            'summary': {
                'pages_crawled': len(pages),
                'js_files_analyzed': len(js_files),
                'openapi_specs_found': len(openapi_specs),
                'endpoints_discovered': len(html_endpoints) + len(js_endpoints),
                'endpoints_tested': len(tested),
                'working_2xx': len([e for e in tested if e.get('working')]),
                'redirects_3xx': len([e for e in tested if e.get('status') and 300 <= e['status'] < 400]),
                'client_errors_4xx': len([e for e in tested if e.get('status') and 400 <= e['status'] < 500]),
                'server_errors_5xx': len([e for e in tested if e.get('status') and 500 <= e['status'] < 600]),
                'failed': len([e for e in tested if e.get('error')]),
            },
            'discovery_stats': discovery_stats,
            'pages': [{'url': p.get('url', ''), 'title': p.get('title', '')} for p in pages],
            'js_files': [{'url': js['url']} for js in js_files],
            'openapi_specs': [{'url': s['url'], 'endpoints_count': len(s.get('endpoints', []))} for s in openapi_specs],
            'endpoints': {
                'from_html': html_endpoints,
                'from_js': js_endpoints,
                'tested': [
                    {
                        'url': e.get('full_url', e.get('url', '')),
                        'method': e.get('tested_method', e.get('method', 'GET')),
                        'status': e.get('status'),
                        'working': e.get('working', False),
                        'response_time': e.get('response_time'),
                        'content_type': e.get('content_type'),
                        'error': e.get('error'),
                        'confidence': e.get('confidence', ''),
                        'source': e.get('source', ''),
                        'info': e.get('info', ''),
                    }
                    for e in tested
                ],
            },
        }
        return output

    def to_csv(self, results, target_url):
        tested = results.get('tested', [])
        if not tested:
            return ''

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Method', 'URL', 'Status', 'Working', 'ResponseTime(s)', 'ContentType', 'Error', 'Confidence', 'Source', 'Info'])
        for ep in tested:
            writer.writerow([
                ep.get('tested_method', ep.get('method', 'GET')),
                ep.get('full_url', ep.get('url', '')),
                ep.get('status', ''),
                'Yes' if ep.get('working') else 'No',
                f"{ep.get('response_time', ''):.2f}" if ep.get('response_time') else '',
                ep.get('content_type', ''),
                ep.get('error', ''),
                ep.get('confidence', ''),
                ep.get('source', ''),
                ep.get('info', ''),
            ])
        return output.getvalue()

    def to_html(self, results, target_url, scan_start):
        tested = results.get('tested', [])
        pages = results.get('pages', [])
        js_files = results.get('js_files', [])
        openapi_specs = results.get('openapi_specs', [])
        discovery_stats = results.get('discovery_stats', {})
        duration = (datetime.now() - scan_start).total_seconds()
        working = [e for e in tested if e.get('working')]
        failed = [e for e in tested if not e.get('working')]

        rows_html = ''
        for ep in tested:
            status = ep.get('status', '')
            method = ep.get('tested_method', ep.get('method', 'GET'))
            url = ep.get('full_url', ep.get('url', ''))
            working_flag = ep.get('working', False)
            resp_time = ep.get('response_time')
            error = ep.get('error', '')
            confidence = ep.get('confidence', '')
            source = ep.get('source', '')
            info = ep.get('info', '')

            status_class = 'success' if working_flag else ('error' if error else 'warning')
            info_cell = f'<td>{info}</td>' if info else '<td>-</td>'
            rows_html += f'''<tr class="{status_class}">
                <td><span class="method method-{method.lower()}">{method}</span></td>
                <td>{url}</td>
                <td>{status}</td>
                <td>{'Yes' if working_flag else 'No'}</td>
                <td>{f"{resp_time:.2f}s" if resp_time else '-'}</td>
                <td>{error if error else '-'}</td>
                <td>{confidence}</td>
                <td>{source}</td>
                {info_cell}
            </tr>'''

        discovery_rows = ''
        html_endpoints = results.get('html_endpoints', [])
        js_endpoints = results.get('js_endpoints', [])
        all_discovered = html_endpoints + js_endpoints
        seen_urls = {}
        for ep in all_discovered:
            url = ep.get('url', '')
            if url not in seen_urls:
                seen_urls[url] = ep
        for ep in seen_urls.values():
            method = ep.get('method', 'GET')
            url = ep.get('url', '')
            confidence = ep.get('confidence', '')
            source = ep.get('source', '')
            info = ep.get('info', '')
            info_cell = f'<td>{info}</td>' if info else '<td>-</td>'
            discovery_rows += f'''<tr>
                <td><span class="method method-{method.lower()}">{method}</span></td>
                <td>{url}</td>
                <td>{confidence}</td>
                <td>{source}</td>
                {info_cell}
            </tr>'''

        # Discovery stats HTML
        stats_rows = ''
        for key, label in [
            ('robots_endpoints', 'Robots.txt'),
            ('sitemap_urls', 'Sitemap'),
            ('well_known_endpoints', '.well-known'),
            ('fuzzed_endpoints', 'Fuzzing'),
            ('openapi_specs', 'API Specs'),
            ('source_map_endpoints', 'Source Maps'),
            ('csp_endpoints', 'CSP Headers'),
            ('link_header_endpoints', 'Link Headers'),
            ('hateoas_endpoints', 'HATEOAS'),
            ('html_comment_endpoints', 'HTML Comments'),
            ('manifest_endpoints', 'Manifest'),
            ('service_worker_endpoints', 'Service Workers'),
            ('response_body_endpoints', 'Response Bodies'),
            ('third_party_endpoints', 'Third-Party APIs'),
            ('git_exposed', 'Git Exposure'),
            ('env_exposed', 'Env Exposure'),
        ]:
            val = discovery_stats.get(key, 0)
            if val:
                stats_rows += f'<div class="card"><div class="label">{label}</div><div class="value">{val}</div></div>\n'

        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MELTOR Scan Report - {target_url}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e14; color: #e6e1cf; padding: 20px; }}
h1 {{ color: #7dcfff; margin-bottom: 5px; }}
h2 {{ color: #ff9e64; margin: 20px 0 10px; }}
.subtitle {{ color: #565b66; margin-bottom: 20px; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 20px 0; }}
.card {{ background: #131721; border: 1px solid #2a2f3a; border-radius: 8px; padding: 15px; }}
.card .label {{ color: #565b66; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
.card .value {{ color: #e6e1cf; font-size: 24px; font-weight: bold; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0 20px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #1d212e; font-size: 13px; }}
th {{ background: #131721; color: #565b66; font-weight: 600; position: sticky; top: 0; }}
tr:hover {{ background: #1a1e2b; }}
tr.success {{ border-left: 3px solid #7eca9c; }}
tr.warning {{ border-left: 3px solid #e1c07e; }}
tr.error {{ border-left: 3px solid #ea6962; }}
.method {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; color: #fff; }}
.method-get {{ background: #418a4f; }}
.method-post {{ background: #3d7eb8; }}
.method-put {{ background: #b8883a; }}
.method-patch {{ background: #7f6bb5; }}
.method-delete {{ background: #c74440; }}
.method-head {{ background: #565b66; }}
.method-options {{ background: #565b66; }}
.tab-nav {{ display: flex; gap: 4px; margin: 20px 0 0; }}
.tab-btn {{ padding: 8px 16px; background: #131721; border: 1px solid #2a2f3a; border-radius: 6px 6px 0 0; color: #565b66; cursor: pointer; font-size: 13px; }}
.tab-btn.active {{ background: #1a1e2b; border-bottom-color: #1a1e2b; color: #e6e1cf; }}
.tab-content {{ display: none; background: #1a1e2b; border: 1px solid #2a2f3a; border-radius: 0 6px 6px 6px; padding: 16px; }}
.tab-content.active {{ display: block; }}
a {{ color: #7dcfff; }}
.footer {{ text-align: center; color: #3d424d; font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<h1>MELTOR Scan Report</h1>
<p class="subtitle">Target: <strong>{target_url}</strong> | Duration: {duration:.1f}s | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="summary">
<div class="card"><div class="label">Pages Crawled</div><div class="value">{len(pages)}</div></div>
<div class="card"><div class="label">JS Files</div><div class="value">{len(js_files)}</div></div>
<div class="card"><div class="label">API Specs</div><div class="value">{len(openapi_specs)}</div></div>
<div class="card"><div class="label">Endpoints Found</div><div class="value">{len(tested)}</div></div>
<div class="card"><div class="label">Working (2xx)</div><div class="value" style="color:#7eca9c">{len(working)}</div></div>
<div class="card"><div class="label">Failed</div><div class="value" style="color:#ea6962">{len(failed)}</div></div>
</div>

{ f'<h2>Discovery Breakdown</h2><div class="summary">{stats_rows}</div>' if stats_rows else '' }

<div class="tab-nav">
<button class="tab-btn active" onclick="switchTab('tested')">Tested Endpoints ({len(tested)})</button>
<button class="tab-btn" onclick="switchTab('discovered')">Discovered Endpoints ({len(seen_urls)})</button>
</div>

<div id="tab-tested" class="tab-content active">
<table>
<thead><tr><th>Method</th><th>URL</th><th>Status</th><th>Working</th><th>Response</th><th>Error</th><th>Confidence</th><th>Source</th><th>Info</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</div>

<div id="tab-discovered" class="tab-content">
<table>
<thead><tr><th>Method</th><th>URL</th><th>Confidence</th><th>Source</th><th>Info</th></tr></thead>
<tbody>{discovery_rows}</tbody>
</table>
</div>

<div class="footer">Generated by MELTOR Ultimate Edition — API Endpoint Discovery & Validation Tool</div>

<script>
function switchTab(name) {{
document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
document.getElementById('tab-' + name).classList.add('active');
document.querySelector(`.tab-btn[onclick*="'${{name}}'"]`).classList.add('active');
}}
</script>
</body>
</html>'''
        return html

    def save_output(self, results, target_url, scan_start, output_path, fmt='json'):
        output_path = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
        if fmt == 'json':
            path = f'{output_path}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.to_json(results, target_url), f, indent=2, default=str)
        elif fmt == 'csv':
            path = f'{output_path}.csv'
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(self.to_csv(results, target_url))
        elif fmt == 'html':
            path = f'{output_path}.html'
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.to_html(results, target_url, scan_start))
        elif fmt == 'all':
            for f in ['json', 'csv', 'html']:
                self.save_output(results, target_url, scan_start, output_path, fmt=f)
            return
        else:
            path = f'{output_path}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.to_json(results, target_url), f, indent=2, default=str)
        return path
