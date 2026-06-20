<p align="center">
  <pre>
    ███    ███ ███████ ██      ████████ ██████  ██████
    ████  ████ ██      ██         ██    ██    ██ ██   ██
    ██ ████ ██ █████   ██         ██    ██    ██ ██████
    ██  ██  ██ ██      ██         ██    ██    ██ ██   ██
    ██      ██ ███████ ███████    ██     ██████  ██   ██
  </pre>
</p>

<h1 align="center">🔥 MELTOR — API Endpoint Discovery & Validation Engine</h1>

<p align="center">
  <b>by spidey</b>
</p>

<p align="center">
  <i>Ultimate Edition — 50+ Discovery Techniques • Web Crawler • JS AST Analyzer • Endpoint Validator</i>
</p>

<p align="center">
  <a href="#-features"><img src="https://img.shields.io/badge/50%2B-Discovery%20Techniques-blueviolet?style=for-the-badge"/></a>
  <a href="#-installation"><img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python"/></a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick-Start-success?style=for-the-badge"/></a>
  <a href="#-comparison-vs-other-tools"><img src="https://img.shields.io/badge/vs-Other%20Tools-orange?style=for-the-badge"/></a>
  <br/>
  <a href="https://www.instagram.com/exp1oit"><img src="https://img.shields.io/badge/Instagram-%40exp1oit-E4405F?style=flat-square&logo=instagram"/></a>
  <a href="https://www.instagram.com/h4cker.in"><img src="https://img.shields.io/badge/Instagram-%40h4cker.in-E4405F?style=flat-square&logo=instagram"/></a>
  <a href="https://t.me/MeMrDefault"><img src="https://img.shields.io/badge/Telegram-%40MeMrDefault-2CA5E0?style=flat-square&logo=telegram"/></a>
</p>

---

## 📋 Table of Contents

- [What is MELTOR?](#-what-is-meltor)
- [Why MELTOR? (The Power)](#-why-meltor-the-power)
- [Features](#-features)
- [Comparison vs Other Tools](#-comparison-vs-other-tools)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [CLI Reference](#-cli-reference)
- [Discovery Techniques Deep Dive](#-discovery-techniques-deep-dive)
- [Use Cases](#-use-cases)
- [Output Formats](#-output-formats)
- [Examples](#-examples)
- [Contributing](#-contributing)
- [Follow & Support](#-follow--support)
- [License](#-license)

---

## 🚀 What is MELTOR?

**MELTOR** is an **all-in-one API endpoint discovery and validation engine** designed for security researchers, penetration testers, and developers. It combines a high-performance web crawler, a JavaScript AST parser, an intelligent fuzzer, and a concurrent endpoint validator into a single powerful tool.

Unlike traditional API discovery tools that focus on just one technique (like fuzzing or crawling), MELTOR uses **50+ discovery techniques simultaneously** to uncover every possible API endpoint on a target web application.

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT                                 │
│              https://target.com                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌─────────┐ │
│  │  CRAWLER │  │ JS PARSER │  │  FUZZER  │  │ TESTER  │ │
│  │          │  │           │  │          │  │         │ │
│  │ • BFS    │  │ • AST     │  │ • 400+   │  │ • HTTP  │ │
│  │ • Robots │  │ • SDK     │  │   paths  │  │   tests │ │
│  │ • Sitemap│  │ • Source  │  │ • Dir    │  │ • Graph │ │
│  │ • .well  │  │   maps    │  │   bust   │  │   QL    │ │
│  │ • HATEOAS│  │ • Deobf   │  │ • Custom │  │ • Multi │ │
│  │ • CSP    │  │ • Regex   │  │ • Cloud  │  │   meth  │ │
│  │ • Comments│  │ • tRPC    │  │ • Disc.  │  │ • HATE  │ │
│  │ • Manif. │  │ • Apollo  │  │ • Graph  │  │   OAS   │ │
│  │ • SW     │  │ • tRPC    │  │   QL     │  │         │ │
│  └────┬─────┘  └─────┬─────┘  └────┬────┘  └────┬────┘ │
│       │              │             │             │      │
│       └──────────────┴─────────────┴─────────────┘      │
│                          ▼                              │
│              ┌──────────────────────┐                   │
│              │    ALL ENDPOINTS     │                   │
│              │   Deduplicated +     │                   │
│              │   Confidence Scored  │                   │
│              └──────────┬───────────┘                   │
│                         ▼                               │
│              ┌──────────────────────┐                   │
│              │   ENDPOINT TESTER    │                   │
│              │   200 / 300 / 400 /  │                   │
│              │   500 categorization │                   │
│              └──────────┬───────────┘                   │
└─────────────────────────┼──────────────────────────────┘
                          ▼
           ┌─────────────────────────────┐
           │  JSON │ CSV │ HTML Report   │
           │  + Console Summary          │
           └─────────────────────────────┘
```

---

## ⚡ Why MELTOR? (The Power)

### What makes MELTOR different?

| Aspect | MELTOR |
|--------|--------|
| **Discovery techniques** | **50+** simultaneous techniques |
| **JS Analysis** | Full **AST-based** parsing (acorn) + 170+ SDK patterns + regex fallback |
| **Default behavior** | **All features ON** — just provide a URL |
| **Directory busting** | Recursive — discovers dirs THEN probes APIs under them |
| **Custom paths** | Load from a `.txt` file |
| **Scope** | 3 levels of API detection + HATEOAS + response body scanning |
| **Speed** | Fully concurrent (configurable, default 15 workers) |
| **Reporting** | JSON + CSV + **Dark-themed HTML report** |
| **GraphQL** | Path discovery + introspection query testing |
| **Wayback Machine** | Fetches historical URLs for older API findings |
| **Third-party APIs** | 300+ regex patterns for Firebase, AWS, Stripe, etc. |

### What can MELTOR find?

```
🔍 API Endpoints         → /api/v1/users, /graphql, /rest/v2, /trpc, /grpc, /soap ...
🔍 Hidden Dirs           → /internal, /private, /admin, /management, /v1 ...
🔍 Exposed Git           → /.git/config, /.git/HEAD, /.git/index ...
🔍 Exposed Env Files     → /.env, /.env.production, /env.json ...
🔍 CI/CD Secrets         → Jenkinsfile, .gitlab-ci.yml, cloudbuild.yaml ...
🔍 Cloud Credentials     → AWS, Azure, GCP, Stripe, Firebase, Twilio ...
🔍 Database Dumps        → /dump.sql, /backup.sql, /db.sql.gz ...
🔍 OpenAPI Specs         → /openapi.json, /swagger.json, /api.raml ...
🔍 Source Maps           → .js.map files with API endpoint references
🔍 .well-known           → security.txt, openid-configuration, webfinger ...
🔍 JS SDK APIs           → Firebase, AWS Amplify, Stripe, PayPal, Apollo ...
🔍 Cloud Storage         → S3 buckets, GCS, Azure Blob, Firebase Hosting ...
🔍 Wayback Machine       → Historical API endpoints from archived pages
🔍 HATEOAS Links         → API links embedded in JSON/HTML responses
```

---

## 🎯 Features

### 🌐 Web Crawling Engine
- **BFS crawl** with configurable depth (default: 3) and page limit (default: 30)
- **Scope control**: `same-domain` or `strict` prefix matching
- **Include/exclude** URL regex filters
- **Rate limiting** with configurable delay (0.2s default) + random jitter
- **Cookie + custom header + Bearer token** support
- **HTTP proxy** support (HTTP/HTTPS)
- **User-Agent rotation** (spoofs Chrome 125)

### 📜 JavaScript Analysis (AST-Based)
- **Full AST parsing** using `acorn` (tries ES2023 → ES2018)
- **170+ SDK patterns**: Firebase, AWS Amplify, Stripe, PayPal, Apollo, tRPC, GraphQL, Axios, Fetch, jQuery, WebSocket, and more
- **Source map analysis**: parses `sourceMappingURL` and `.js.map` files
- **Template literal extraction**: extracts endpoints from JS template strings
- **Deobfuscation**: attempts to beautify minified JS via Node.js
- **Regex fallback**: catches what AST misses
- **Import map & JSON-LD** parsing

### 🚀 API Fuzzing & Discovery
- **443+ fuzz paths** covering REST, GraphQL, SOAP, gRPC, WebDAV, OData, JSON-RPC, XML-RPC, tRPC, and more
- **Recursive directory busting** — finds dirs, probes resources under them, recurses
- **Custom endpoint file** — provide your own paths via `.txt` file
- **Cloud storage probing** — S3, Google Cloud Storage, Azure Blob, Firebase
- **308+ disclosure paths** — Git, Env, CI/CD, database, secrets, configs
- **Third-party API detection** — 300+ regex patterns for 80+ services

### 🔬 Endpoint Validation & Testing
- **Concurrent testing** (configurable, default 15 workers)
- **23 HTTP methods** including PROPFIND, MKCOL, COPY, MOVE, LOCK, UNLOCK, SEARCH, SUBSCRIBE
- **Response classification**: 2xx working, 3xx redirect, 4xx client error, 5xx server error
- **Response time** measurement
- **Redirect chain** tracking
- **Response body preview** with HATEOAS extraction
- **GraphQL introspection** testing

### 📊 Reporting & Output
- **JSON** output — machine-readable, easy to parse
- **CSV** output — spreadsheet-friendly
- **HTML report** — dark-themed, tabbed interface, professional design
- **Colorized console** output with status indicators
- **CI mode** — exits non-zero if endpoints are found
- **Discovery breakdown** — per-technique stats

### 🔒 Security Checks
- **Git exposure** (`.git/config`, `.git/HEAD`, `.git/index`, etc.)
- **Environment file exposure** (`.env`, `.env.prod`, etc.)
- **CI/CD pipeline leakage** (GitHub Actions, GitLab CI, Jenkins, CircleCI, Travis, Drone, Buildkite)
- **Database dump exposure** (SQL, PSQL, MySQL, backups)
- **Cloud credentials** (AWS, Azure, GCP, Stripe, Firebase, Twilio, SendGrid, Mailgun, etc.)
- **Server configuration** (nginx, Apache, Caddy, web.config, .htaccess)
- **Package manifests** (package.json, composer.json, Gemfile, go.mod, Cargo.toml)
- **Build artifacts** (`.next/`, `.nuxt/`, `dist/`, `build/`, `target/`)
- **Kubernetes/Terraform/Serverless** config exposure

---

## 🆚 Comparison vs Other Tools

| Feature | **MELTOR** | ffuf | dirsearch | katana | gospider | nuclei | arjun |
|---------|:----------:|:----:|:---------:|:------:|:--------:|:------:|:-----:|
| **Techniques** | **50+** | 1 | 1 | 2 | 3 | 5+ | 1 |
| **JS AST Analysis** | ✅ Full AST (acorn) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SDK Pattern Detection** | ✅ 170+ patterns | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Web Crawler** | ✅ BFS + scope + rate-limit | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **API Fuzzing** | ✅ 443+ paths | ✅ (custom) | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Directory Busting** | ✅ Recursive | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Disclosure Checks** | ✅ 308+ paths | ❌ | ❌ | ❌ | ❌ | ✅ (templates) | ❌ |
| **GraphQL Discovery** | ✅ Path + Introspection | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Source Map Analysis** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **.well-known Probing** | ✅ 40+ paths | ❌ | ❌ | ❌ | ❌ | ✅ (templates) | ❌ |
| **Wayback Machine** | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Cloud Storage Probe** | ✅ 25+ patterns | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Third-party API Match** | ✅ 300+ regex | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **HATEOAS Extraction** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OpenAPI/Swagger Parse** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Postman Collection** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **WSDL Parsing** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Endpoint Testing** | ✅ 23 methods | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Custom Headers/Auth** | ✅ Cookie/Bearer/Header | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **HTML Report** | ✅ Dark-themed | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **CI Mode** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Custom Endpoints File** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **All Features ON by Default** | ✅ | N/A | N/A | N/A | N/A | N/A | N/A |

### Why MELTOR wins:

> **MELTOR combines the power of 7+ individual tools** into one unified pipeline. Instead of running ffuf, then dirsearch, then katana, then gospider, then nuclei — you run **one command** and get **everything** with **deduplication**, **confidence scoring**, and a **professional HTML report**.

---

## 📦 Installation

### Prerequisites
- **Python 3.8+**
- **Node.js 16+** (for JS AST analysis)
- **pip** (Python package manager)

### Option 1: Quick Install

```bash
# Clone the repository
git clone https://github.com/spidey/meltor.git
cd meltor

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Run it
python meltor.py https://target.com
```

### Option 2: Using pip

```bash
# Coming soon — package is being prepared for PyPI
```

### Dependencies

**Python (requirements.txt):**
| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | >=2.28.0 | HTTP client |
| `beautifulsoup4` | >=4.11.0 | HTML/XML parsing |
| `colorama` | >=0.4.6 | Colored terminal output |
| `jinja2` | >=3.1.0 | HTML report templating |

**Node.js (package.json):**
| Package | Version | Purpose |
|---------|---------|---------|
| `acorn` | ^8.11.0 | JavaScript AST parser |
| `acorn-walk` | ^8.3.0 | AST tree walker |

### Verify Installation

```bash
python meltor.py --help
python test_all.py    # Run 140+ tests to verify everything works
```

---

## 🚀 Quick Start

```bash
# Scan a target with ALL features enabled (default)
python meltor.py https://example.com

# Fast scan — discovery only, no endpoint testing
python meltor.py https://example.com --no-test --quiet

# Deep scan with output report
python meltor.py https://example.com --depth 5 --max-pages 100 -o report --format all

# Authenticated scan
python meltor.py https://example.com --cookie "session=abc123" --bearer "your_token"

# Proxy through Burp Suite
python meltor.py https://example.com --proxy http://127.0.0.1:8080

# Custom scope with include/exclude filters
python meltor.py https://example.com --scope strict --include "/api" --exclude "admin"

# Load custom endpoint paths from file
python meltor.py https://example.com --endpoints-file my_paths.txt

# CI mode — exits with non-zero if endpoints are found
python meltor.py https://example.com --ci --format json -o report
```

### Custom Endpoints File Format

Create a `.txt` file with one path per line. Lines starting with `#` are ignored.

```text
# My custom API paths
/api/v1/my-private-resource
/api/v2/internal/endpoint
/internal/health/check
/admin/panel/hidden
```

---

## 📖 CLI Reference

### Arguments

| Argument | Default | Description |
|----------|:-------:|-------------|
| `url` | — | Target URL to scan |
| `--depth` | `3` | Crawl depth |
| `--max-pages` | `30` | Max pages to crawl |
| `--concurrency` | `15` | Concurrent requests for testing |
| `--timeout` | `10` | Request timeout in seconds |
| `--output, -o` | — | Output file base path |
| `--format` | `json` | Output format: `json`, `csv`, `html`, `all` |
| `--no-test` | off | Skip endpoint testing |
| `--quiet, -q` | off | Less verbose output |
| `--debug` | off | Enable debug logging |
| `--cookie` | — | Cookie string (e.g. `"session=abc123"`) |
| `--header` | — | Custom header (repeatable) |
| `--bearer` | — | Bearer token shorthand |
| `--proxy` | — | Proxy URL (e.g. `http://127.0.0.1:8080`) |
| `--scope` | `same-domain` | `same-domain` or `strict` |
| `--include` | — | Regex include filter |
| `--exclude` | — | Regex exclude filter |
| `--delay` | `0.2` | Delay between requests (seconds) |
| `--jitter` | `0` | Random jitter added to delay |
| `--endpoints-file` | — | Path to custom endpoints `.txt` file |
| `--dir-depth` | `2` | Directory busting recursion depth |
| `--ci` | off | CI mode (exit non-zero if endpoints found) |
| `--all-formats` | off | Shortcut for `--format all` |

### Feature Toggles (all ON by default)

| Flag | Description |
|------|-------------|
| `--wayback` | Fetch historical URLs from Wayback Machine |
| `--graphql` | Test GraphQL introspection |
| `--deobfuscate` | Deobfuscate JavaScript files |
| `--deep` | Deep discovery (cloud storage, body scanning) |
| `--fuzz` | Fuzz 443+ common API paths |
| `--crawl-apis` | Crawl discovered API endpoints |
| `--dir-bust` | Directory busting with resource probing |
| `--robots` | Parse robots.txt |
| `--sitemap` | Parse sitemap.xml |
| `--well-known` | Probe .well-known/ paths |
| `--source-maps` | Analyze JS source maps |

---

## 🔬 Discovery Techniques Deep Dive

### Phase 1: Pre-Crawl Discovery
Techniques that run before the main crawl begins:

```
┌─────────────────────────────────────────────────────┐
│ ● robots.txt parsing                                │
│ ● Sitemap.xml parsing (7 common paths)              │
│ ● Wayback Machine history fetch (up to 500 URLs)    │
│ ● API spec discovery (50+ openapi/swagger paths)    │
└─────────────────────────────────────────────────────┘
```

### Phase 2: BFS Web Crawling
The main crawl discovers pages, JS files, and embedded endpoints:

```
┌─────────────────────────────────────────────────────┐
│ ● BFS crawl up to --depth levels                    │
│ ● CSP header parsing for API domains                │
│ ● Link header parsing for service endpoints         │
│ ● HTML comment mining for API hints                 │
│ ● Form action extraction                            │
│ ● Inline JS extraction                              │
│ ● Import map parsing                                │
│ ● JSON-LD extraction                                │
│ ● JS file collection (for later analysis)           │
└─────────────────────────────────────────────────────┘
```

### Phase 3: Post-Crawl Discovery
After crawling, intensive probing techniques run:

```
┌─────────────────────────────────────────────────────┐
│ ● OpenAPI spec discovery & parsing                  │
│ ● GraphQL path probing (70+ paths)                  │
│ ● Source map analysis (sm + .js.map)                │
│ ● API path fuzzing (443+ paths)                     │
│ ● .well-known probing (36 paths)                    │
│ ● Cloud storage probing (25+ patterns)              │
│ ● Disclosure path probing (308+ paths)              │
│ ● Manifest file analysis                            │
│ ● Service worker analysis                           │
│ ● Third-party API detection (300+ patterns)         │
│ ● Custom endpoint probing                           │
│ ● Recursive directory busting                       │
└─────────────────────────────────────────────────────┘
```

### Phase 4: JavaScript Analysis
All collected JS files go through deep analysis:

```
┌─────────────────────────────────────────────────────┐
│  Each JS file:                                      │
│  ├─ Deobfuscation (if enabled)                     │
│  ├─ AST parsing (acorn, ES2023 → ES2018)           │
│  ├─ AST walk for:                                   │
│  │  ├─ fetch() / XMLHttpRequest                     │
│  │  ├─ axios / $.ajax / ky / got / superagent       │
│  │  ├─ WebSocket / Socket.io / SignalR              │
│  │  ├─ Express / Fastify route definitions          │
│  │  ├─ tRPC router definitions                      │
│  │  ├─ Apollo Client / React Query / SWR hooks      │
│  │  ├─ gql tagged template literals                 │
│  │  └─ Template literals with URLs                  │
│  ├─ SDK pattern matching (170+ patterns):           │
│  │  ├─ Firebase (auth, firestore, functions)        │
│  │  ├─ AWS Amplify / API Gateway / Lambda           │
│  │  ├─ Stripe / PayPal / Square / Braintree         │
│  │  ├─ Apollo / GraphQL Yoga / Mercurius            │
│  │  ├─ Supabase / PocketBase / Appwrite             │
│  │  ├─ Algolia / Meilisearch / Elastic              │
│  │  ├─ Contentful / Strapi / Sanity / Prismic       │
│  │  ├─ Clerk / Auth0 / NextAuth / Lucia             │
│  │  ├─ UploadThing / Filestack / Transloadit        │
│  │  ├─ LiveKit / Daily.co / Stream / Agora          │
│  │  └─ 60+ more services...                         │
│  └─ Regex fallback extraction                       │
└─────────────────────────────────────────────────────┘
```

### Phase 5: Endpoint Validation
Every unique endpoint is tested:

```
┌─────────────────────────────────────────────────────┐
│  Each endpoint:                                     │
│  ├─ HTTP request with configured method             │
│  ├─ Response classification:                        │
│  │  ├─ ✅ 2xx → WORKING                             │
│  │  ├─ 🔄 3xx → Redirect (chain tracked)            │
│  │  ├─ ❌ 4xx → Client Error                        │
│  │  ├─ 💥 5xx → Server Error                        │
│  │  └─ ⏱ Timeout → Failed                          │
│  ├─ Response time measurement                       │
│  ├─ Response body preview                           │
│  ├─ HATEOAS link extraction from response           │
│  └─ GraphQL introspection (if GraphQL endpoint)     │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Use Cases

### 🔴 Security Researchers & Penetration Testers
- **Bug bounty hunting** — discover hidden API endpoints for potential vulnerabilities
- **Attack surface mapping** — understand the full API landscape of a target
- **API security assessment** — find exposed endpoints, debug routes, admin panels
- **Disclosure detection** — uncover accidentally exposed secrets, credentials, configs

### 🔵 Developers & DevOps
- **API documentation drift detection** — find undocumented endpoints
- **Security audit** — ensure no debug/test endpoints are exposed in production
- **CI/CD integration** — use `--ci` mode to fail builds when unexpected endpoints appear

### 🟢 Red Teams
- **Reconnaissance automation** — integrate into larger red teaming workflows
- **External attack surface discovery** — understand what's exposed to the internet
- **Cloud misconfiguration discovery** — find exposed S3 buckets, cloud credentials

---

## 📄 Output Formats

### JSON Output
Machine-readable, perfect for integration with other tools:

```json
{
  "target": "https://example.com",
  "scan_date": "2025-06-20T12:00:00",
  "duration": 120.5,
  "stats": {
    "pages_crawled": 5,
    "js_files_analyzed": 12,
    "total_endpoints": 250,
    "working": 180,
    "errors": 70
  },
  "endpoints": [
    {
      "url": "/api/v1/users",
      "method": "GET",
      "status": 200,
      "confidence": "high",
      "source": "fuzzing",
      "response_time": 0.45,
      "working": true
    }
  ]
}
```

### CSV Output
Spreadsheet-ready for analysis in Excel/Google Sheets:
```
url,method,status,confidence,source,response_time,working
/api/v1/users,GET,200,high,fuzzing,0.45,true
```

### HTML Report
A professional dark-themed HTML report with:
- Tabbed interface (All / Working / Client Errors / Server Errors)
- Scan summary with key metrics
- Color-coded status indicators (green working, red errors)
- Responsive design for desktop and mobile
- Search/filter capabilities
- Per-endpoint details (response time, content type, source)

---

## 💡 Examples

### Bug Bounty Recon

```bash
# Full recon on a bug bounty target
python meltor.py https://target.com \
  --depth 3 \
  --max-pages 50 \
  --cookie "session=YOUR_SESSION" \
  --header "X-Bug-Bounty: 1" \
  --format all \
  -o target_recon
```

### CI/CD Pipeline Integration

```yaml
# .github/workflows/api-audit.yml
name: API Endpoint Audit
on: [push]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run MELTOR
        run: |
          pip install -r requirements.txt
          python meltor.py https://staging.example.com \
            --ci \
            --format json \
            -o audit_report
```

### Quick Internal Scan

```bash
# Fast scan of internal API server
python meltor.py https://api.internal.company.com \
  --no-test \
  --quiet \
  --depth 1 \
  --max-pages 5
```

### Deep OSINT Gathering

```bash
# Maximum discovery with all sources
python meltor.py https://target.com \
  --deep \
  --dir-depth 3 \
  --wayback \
  --deobfuscate \
  --endpoints-file custom_paths.txt \
  -o full_recon \
  --format all
```

---

## 🤝 Contributing

MELTOR is an open-source project and **we welcome contributors of all skill levels!**

### Ways to Contribute
- 🐛 **Report bugs** — Open an issue with detailed reproduction steps
- 💡 **Suggest features** — Have an idea? We want to hear it!
- 📝 **Improve documentation** — Fix typos, add examples, translate
- 🔧 **Submit PRs** — Code contributions, new discovery techniques, bug fixes
- ⭐ **Star the repo** — Helps others discover the project

### Development Setup

```bash
git clone https://github.com/spidey/meltor.git
cd meltor
pip install -r requirements.txt
npm install

# Run tests
python test_all.py

# Add your feature or fix
# ...
# Submit a Pull Request!
```

### Code Structure

```
meltor/
├── meltor.py              # Main entry point & CLI
├── lib/
│   ├── crawler.py         # Web crawler & discovery engine
│   ├── tester.py          # Endpoint validation & testing
│   ├── reporter.py        # Output formatting & HTML reports
│   ├── extractor.js       # JS AST analysis (Node.js)
│   └── __init__.py
├── test_all.py            # 140+ unit tests
├── requirements.txt       # Python dependencies
├── package.json           # Node.js dependencies
├── custom_eps.txt         # Example custom endpoints file
└── README.md              # This file
```

---

## 📬 Follow & Support

Stay connected, get updates, and join the community!

<p align="center">
  <a href="https://www.instagram.com/exp1oit">
    <img src="https://img.shields.io/badge/Instagram-%40exp1oit-E4405F?style=for-the-badge&logo=instagram&logoColor=white"/>
  </a>
  <a href="https://www.instagram.com/h4cker.in">
    <img src="https://img.shields.io/badge/Instagram-%40h4cker.in-E4405F?style=for-the-badge&logo=instagram&logoColor=white"/>
  </a>
  <a href="https://t.me/MeMrDefault">
    <img src="https://img.shields.io/badge/Telegram-%40MeMrDefault-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white"/>
  </a>
</p>

<p align="center">
  <b>Follow for:</b><br/>
  🔥 Latest updates on MELTOR<br/>
  🛡️ Cybersecurity tools & techniques<br/>
  💻 Hacking tutorials & writeups<br/>
  🎯 Bug bounty tips & resources<br/>
</p>

---

## 📜 License

MELTOR is released under the **MIT License**.

```
MIT License

Copyright (c) 2025 spidey

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

<p align="center">
  <i>Built with ❤️ by spidey</i><br/>
  <i>MELTOR — More than a scanner. It's a discovery engine.</i>
</p>

<p align="center">
  <a href="https://www.instagram.com/exp1oit">@exp1oit</a> •
  <a href="https://www.instagram.com/h4cker.in">@h4cker.in</a> •
  <a href="https://t.me/MeMrDefault">@MeMrDefault</a>
</p>
