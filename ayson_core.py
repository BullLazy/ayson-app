import base64
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.cookiejar import CookieJar

try:
    import certifi
except Exception:
    certifi = None


VERSION = "V2.2-expanded-safe-redirect"

SUPPORTED_HOSTS = {
    "ay.live",
    "aylink.co",
    "cpmlink.co",
    "cpmlink.pro",
    "bildirim.online",
    "bildirim.vip",
    "ouo.io",
    "ouo.press",
}

TRLINK_HOSTS = {"ay.live", "aylink.co", "cpmlink.co", "cpmlink.pro"}
BILDIRIM_HOSTS = {"bildirim.online", "bildirim.vip"}
OUO_HOSTS = {"ouo.io", "ouo.press"}

GENERIC_REDIRECT_HOSTS = {
    "bit.ly",
    "bitly.com",
    "tinyurl.com",
    "is.gd",
    "v.gd",
    "t.co",
    "lnkd.in",
    "goo.gl",
    "ow.ly",
    "buff.ly",
    "rebrand.ly",
    "rb.gy",
    "shorturl.at",
    "cutt.ly",
    "s.id",
    "tiny.cc",
    "short.io",
    "lnk.news",
    "tulink.fun",
    "adf.ly",
    "bc.vc",
    "shorte.st",
    "clk.sh",
    "shrinke.me",
    "exe.io",
    "exey.io",
    "fc.lc",
    "fc-lc.xyz",
    "linkvertise.com",
}

SUPPORTED_HOSTS.update(GENERIC_REDIRECT_HOSTS)

URL_RE = re.compile(r"https?://[^\s'\"<>`\\]+", re.I)

NOISE_HOSTS = {
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com",
    "code.jquery.com",
    "ajax.googleapis.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "unpkg.com",
    "cdn.datatables.net",
    "loremflickr.com",
    "picsum.photos",
    "placehold.co",
    "placeholder.com",
    "via.placeholder.com",
    "dummyimage.com",
    "placeimg.com",
}

NOISE_EXTS = (
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
)

NOISE_WORDS = (
    "bootstrap",
    "jquery",
    "fontawesome",
    "popper",
    "datatables",
    "sweetalert",
    "cloudflare",
    "jsdelivr",
    "googleapis",
    "gstatic",
    "analytics",
    "doubleclick",
    "googletagmanager",
)


def clean_url(value):
    if value is None:
        return ""

    s = html.unescape(str(value)).strip()
    s = s.replace("\\/", "/")
    s = s.strip().strip(".,;)'\"`]}")

    for _ in range(2):
        low = s.lower()
        if low.startswith("http%") or "%3a%2f%2f" in low:
            s = urllib.parse.unquote(s)
            s = html.unescape(s).strip().strip(".,;)'\"`]}")
        else:
            break

    return s


def absolutize_url(value, base_url=""):
    u = clean_url(value)
    if not u:
        return ""
    if u.startswith("//"):
        u = "https:" + u
    elif base_url and not u.lower().startswith(("http://", "https://")):
        u = urllib.parse.urljoin(base_url, u)
    return clean_url(u)


def host_of(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        host = host.split("@")[-1].split(":")[0]
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def is_http_url(url):
    return clean_url(url).lower().startswith(("http://", "https://"))


def is_noise_url(url, from_page=True):
    u = clean_url(url)
    h = host_of(u)
    path = urllib.parse.urlparse(u).path.lower()
    low = u.lower()

    if not h:
        return True
    if h in NOISE_HOSTS:
        return True
    if from_page and path.endswith(NOISE_EXTS):
        return True
    if from_page and any(word in low for word in NOISE_WORDS):
        return True
    return False


def is_valid_final_candidate(url, from_page=True):
    u = clean_url(url)
    h = host_of(u)

    if not is_http_url(u):
        return False
    if not h:
        return False
    if h in SUPPORTED_HOSTS:
        return False
    if is_noise_url(u, from_page=from_page):
        return False
    return True


def extract_target_from_query(url):
    keys = (
        "url",
        "u",
        "to",
        "target",
        "dest",
        "destination",
        "redirect",
        "redirect_url",
        "redirect_uri",
        "r",
        "link",
        "go",
        "site",
    )

    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    except Exception:
        return ""

    for key in keys:
        values = qs.get(key) or qs.get(key.upper())
        if not values:
            continue
        val = html.unescape(urllib.parse.unquote(values[0])).strip()
        val = clean_url(val)
        if is_http_url(val):
            return val

    return ""


def b64_try_decode(value):
    raw = str(value or "").strip()
    if not raw:
        return ""

    attempts = [raw, urllib.parse.unquote(raw)]

    for item in attempts:
        item = item.strip()
        item += "=" * (-len(item) % 4)
        for decoder in (base64.urlsafe_b64decode, base64.b64decode):
            try:
                decoded = decoder(item.encode("utf-8")).decode("utf-8", "ignore").strip()
                if decoded:
                    return decoded
            except Exception:
                pass

    return ""


def dedupe(items):
    out = []
    seen = set()
    for item in items:
        item = clean_url(item)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def parse_json_maybe(text):
    if text is None:
        return None

    s = str(text).strip()
    if not s:
        return None

    try:
        return json.loads(s)
    except Exception:
        pass

    m = re.search(r"(\{[\s\S]*\})", s)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    return None

def json_candidate_values(obj):
    keys = {
        "url",
        "href",
        "link",
        "target",
        "destination",
        "redirect",
        "redirect_url",
        "location",
        "uri",
        "uri_full",
        "real_url",
        "realUrl",
        "download_url",
        "downloadUrl",
    }

    out = []

    def walk(value, key_hint=""):
        if isinstance(value, dict):
            for k, v in value.items():
                if str(k) in keys and isinstance(v, str):
                    out.append(v)
                walk(v, str(k))
        elif isinstance(value, list):
            for item in value:
                walk(item, key_hint)
        elif isinstance(value, str):
            if key_hint in keys or "http://" in value.lower() or "https://" in value.lower():
                out.append(value)

    walk(obj)
    return dedupe(out)


def compact_dict(d):
    return {k: v for k, v in d.items() if v is not None and str(v) != ""}


def contains_human_challenge(body):
    low = (body or "").lower()
    markers = (
        "cf-turnstile",
        "turnstile-form",
        "g-recaptcha",
        "recaptcha/api",
        "h-captcha",
        "hcaptcha",
        "cf-challenge",
        "just a moment",
        "checking your browser",
    )
    return any(marker in low for marker in markers)


class InputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = {str(k).lower(): (v or "") for k, v in attrs}

        if tag.lower() == "input":
            self.inputs.append(attrs_dict)

        for attr_name in (
            "data-url",
            "data-href",
            "data-target",
            "data-redirect",
            "data-link",
            "data-destination",
        ):
            if attrs_dict.get(attr_name):
                self.candidates.append(attrs_dict[attr_name])

        if tag.lower() == "meta":
            http_equiv = attrs_dict.get("http-equiv", "").lower()
            content = attrs_dict.get("content", "")
            if http_equiv == "refresh" and "url=" in content.lower():
                self.candidates.append(content.split("=", 1)[1])

        if tag.lower() == "a":
            href = attrs_dict.get("href", "")
            meta = " ".join(
                attrs_dict.get(k, "")
                for k in ("id", "class", "name", "rel", "data-action", "aria-label", "title")
            )
            if href and re.search(
                r"(continue|go|git|link|redirect|download|skip|devam|hedef|target)",
                meta,
                re.I,
            ):
                self.candidates.append(href)


def parse_inputs(body):
    parser = InputParser()
    try:
        parser.feed(body or "")
    except Exception:
        pass
    return parser.inputs, parser.candidates


def get_input_value(body, *names):
    names_l = {n.lower() for n in names}

    inputs, _ = parse_inputs(body)
    for item in inputs:
        if item.get("name", "").lower() in names_l:
            val = item.get("value", "")
            if val != "":
                return html.unescape(val)

    for name in names:
        patterns = [
            rf"""name=["']{re.escape(name)}["'][^>]*value=["']([^"']*)["']""",
            rf"""value=["']([^"']*)["'][^>]*name=["']{re.escape(name)}["']""",
        ]
        for pat in patterns:
            m = re.search(pat, body or "", re.I)
            if m:
                return html.unescape(m.group(1))

    return ""


def find_one(body, patterns):
    for pat in patterns:
        m = re.search(pat, body or "", re.I)
        if m:
            return html.unescape(m.group(1))
    return ""


def extract_atd_values(body):
    m = re.search(
        r"""_a\s*=\s*['"]([^'"]+)['"]\s*,\s*_t\s*=\s*['"]([^'"]+)['"]\s*,\s*_d\s*=\s*['"]([^'"]+)['"]""",
        body or "",
        re.I,
    )
    if m:
        return m.group(1), m.group(2), m.group(3)

    a_val = get_input_value(body, "_a") or find_one(body, [r"""_a\s*[:=]\s*['"]([^'"]+)['"]"""])
    t_val = get_input_value(body, "_t") or find_one(body, [r"""_t\s*[:=]\s*['"]([^'"]+)['"]"""])
    d_val = get_input_value(body, "_d") or find_one(body, [r"""_d\s*[:=]\s*['"]([^'"]+)['"]"""])

    return a_val, t_val, d_val


def extract_alias(body, page_url):
    return (
        get_input_value(body, "alias")
        or find_one(
            body,
            [
                r"""alias\s*[:=]\s*['"]([^'"]+)['"]""",
                r"""['"]alias['"]\s*:\s*['"]([^'"]+)['"]""",
                r"""data-alias=["']([^"']+)["']""",
            ],
        )
        or urllib.parse.urlparse(page_url).path.strip("/").split("/")[-1]
    )


def extract_csrf(body):
    return (
        get_input_value(body, "csrf", "_csrfToken", "csrfToken", "csrf_token")
        or find_one(
            body,
            [
                r"""csrfToken\s*[:=]\s*['"]([^'"]+)['"]""",
                r"""csrf_token\s*[:=]\s*['"]([^'"]+)['"]""",
                r"""csrf\s*[:=]\s*['"]([^'"]+)['"]""",
                r"""name=["']csrf-token["']\s+content=["']([^"']+)["']""",
                r"""content=["']([^"']+)["']\s+name=["']csrf-token["']""",
            ],
        )
    )


def extract_form_tokens(body):
    inputs, _ = parse_inputs(body)
    data = {}

    for item in inputs:
        name = item.get("name", "")
        value = item.get("value", "")
        if not name:
            continue
        if (
            name.lower().endswith("token")
            or name.lower() in {"_token", "token", "x-token", "cf-turnstile-response"}
        ):
            data[name] = value

    return compact_dict(data)


def high_confidence_urls_from_text(text, base_url=""):
    text = text or ""
    candidates = []

    patterns = [
        r"""url\s*=\s*['"]([^'"]+)['"]""",
        r"""uri_full\s*:\s*['"]([^'"]+)['"]""",
        r"""(?:go_url|target|destination|redirect|redirect_url|real_url|realUrl|download_url|downloadUrl|link)\s*[:=]\s*['"]([^'"]+)['"]""",
        r"""(?:window\.open|location\.assign|location\.replace)\(\s*['"]([^'"]+)['"]""",
        r"""(?:window\.)?location(?:\.href)?\s*=\s*['"]([^'"]+)['"]""",
        r"""data-(?:url|href|target|redirect|link|destination)=["']([^"']+)["']""",
        r"""decodeURIComponent\(['"]([^'"]+)['"]\)""",
    ]

    for pat in patterns:
        for match in re.findall(pat, text, re.I):
            if isinstance(match, tuple):
                match = next((x for x in match if x), "")
            if "decodeURIComponent" not in pat:
                candidates.append(match)
            else:
                candidates.append(urllib.parse.unquote(match))

    _, parser_candidates = parse_inputs(text)
    candidates.extend(parser_candidates)

    normalized = []
    for item in candidates:
        item = absolutize_url(item, base_url)
        if item:
            normalized.append(item)

    return dedupe(normalized)

class Resolver:
    def __init__(self):
        self.cj = CookieJar()
        self.verify_ssl = True
        self.ssl_context = self._make_ssl_context(verify=True)
        self._build_opener()

    def _make_ssl_context(self, verify=True):
        if verify:
            try:
                if certifi is not None:
                    return ssl.create_default_context(cafile=certifi.where())
                return ssl.create_default_context()
            except Exception:
                pass

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _build_opener(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ssl_context),
        )

    def _ajax_headers(self, referer):
        parsed = urllib.parse.urlparse(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": origin,
            "Referer": referer,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def request(
        self,
        url,
        data=None,
        headers=None,
        method=None,
        timeout=35,
        allow_redirects=True,
        retries=2,
    ):
        url = clean_url(url)
        headers = dict(headers or {})

        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "close",
        }
        default_headers.update(headers)

        body_data = data
        if isinstance(data, dict):
            body_data = urllib.parse.urlencode(data).encode("utf-8")
            default_headers.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        for attempt in range(retries + 1):
            opener = self.opener
            if not allow_redirects:
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(self.cj),
                    urllib.request.HTTPSHandler(context=self.ssl_context),
                    NoRedirect,
                )

            req = urllib.request.Request(url, data=body_data, headers=default_headers, method=method)

            try:
                with opener.open(req, timeout=timeout) as resp:
                    body = resp.read().decode("utf-8", "ignore")
                    return resp.geturl(), getattr(resp, "status", 200), dict(resp.headers), body
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "ignore")
                return url, exc.code, dict(exc.headers), body
            except (urllib.error.URLError, ssl.SSLError) as exc:
                message = str(exc)
                if self.verify_ssl and "CERTIFICATE_VERIFY_FAILED" in message:
                    self.verify_ssl = False
                    self.ssl_context = self._make_ssl_context(verify=False)
                    self._build_opener()
                    continue

                if attempt < retries:
                    time.sleep(0.8 + attempt)
                    continue
                raise RuntimeError("Ağ isteği başarısız: " + message)

        raise RuntimeError("Ağ isteği başarısız.")

    def find_urls_in_text(self, text, base_url="", from_page=True):
        text = text or ""
        out = []

        def add(value):
            value = absolutize_url(value, base_url)
            if not value or not is_http_url(value):
                return
            if is_noise_url(value, from_page=from_page):
                return
            if value not in out:
                out.append(value)

        for url in URL_RE.findall(text):
            add(url)

        for encoded in re.findall(r"""decodeURIComponent\(['"]([^'"]+)['"]\)""", text, re.I):
            add(urllib.parse.unquote(encoded))

        for encoded in re.findall(r"""atob\(['"]([^'"]+)['"]\)""", text, re.I):
            add(b64_try_decode(encoded))

        return out

    def follow_http_redirects(self, url, max_hops=8):
        current = clean_url(url)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ssl_context),
            NoRedirect,
        )

        for _ in range(max_hops):
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
                ),
                "Accept": "*/*",
                "Range": "bytes=0-0",
                "Connection": "close",
            }
            req = urllib.request.Request(current, headers=headers)

            try:
                with opener.open(req, timeout=15) as resp:
                    return resp.geturl()
            except urllib.error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    loc = exc.headers.get("Location") or exc.headers.get("location")
                    if not loc:
                        return current
                    nxt = clean_url(urllib.parse.urljoin(current, loc))
                    if not nxt or nxt == current:
                        return current
                    current = nxt
                    continue
                return current
            except Exception:
                return current

        return current

    def _guard_depth(self, depth):
        if depth > 6:
            raise RuntimeError("Çok fazla ara yönlendirme var; döngü engellendi.")

    def _resolve_candidate(self, candidate, base_url, depth, from_page=False):
        candidate = absolutize_url(candidate, base_url)
        if not is_http_url(candidate):
            return None

        h = host_of(candidate)

        if h in BILDIRIM_HOSTS:
            return self.resolve_bildirim(candidate, depth=depth + 1)
        if h in TRLINK_HOSTS:
            return self.resolve_trlink(candidate, depth=depth + 1)
        if h in OUO_HOSTS:
            return self.resolve_ouo(candidate, depth=depth + 1)
        if h == "tulink.fun":
            return self.resolve_tulink(candidate, depth=depth + 1)
        if h in GENERIC_REDIRECT_HOSTS:
            return self.resolve_generic_redirect(candidate, depth=depth + 1)
        if is_valid_final_candidate(candidate, from_page=from_page):
            return self.follow_http_redirects(candidate)

        return None

    def resolve_bildirim(self, url, depth=0):
        self._guard_depth(depth)

        page_url, status, headers, body = self.request(url, allow_redirects=True)
        page_host = host_of(page_url)

        if page_host not in SUPPORTED_HOSTS and is_valid_final_candidate(page_url, from_page=False):
            return self.follow_http_redirects(page_url)

        candidates = []

        parsed = urllib.parse.urlparse(page_url)
        last = parsed.path.rstrip("/").split("/")[-1]
        decoded_path = b64_try_decode(last)
        if decoded_path:
            candidates.extend(high_confidence_urls_from_text(decoded_path, page_url))
            candidates.extend(self.find_urls_in_text(decoded_path, page_url, from_page=False))

        candidates.extend(high_confidence_urls_from_text(body, page_url))

        for candidate in dedupe(candidates):
            result = self._resolve_candidate(candidate, page_url, depth, from_page=False)
            if result:
                return result

        raise RuntimeError("bildirim ara sayfasında gerçek final link bulunamadı.")

    def _parse_tk_token(self, tk_body):
        data = parse_json_maybe(tk_body)
        if data is None:
            return ""

        values = []
        if isinstance(data, dict):
            values.extend(
                [
                    data.get("th"),
                    data.get("tkn"),
                    data.get("token"),
                    data.get("visitor_token"),
                    data.get("tk"),
                ]
            )
            for key in ("data", "result", "response"):
                if isinstance(data.get(key), dict):
                    nested = data[key]
                    values.extend(
                        [
                            nested.get("th"),
                            nested.get("tkn"),
                            nested.get("token"),
                            nested.get("visitor_token"),
                            nested.get("tk"),
                        ]
                    )

        for value in values:
            if value:
                return str(value)

        return ""

    def _candidate_from_go_response(self, go_body, base_url, depth):
        data = parse_json_maybe(go_body)

        if data is not None:
            for candidate in json_candidate_values(data):
                result = self._resolve_candidate(candidate, base_url, depth, from_page=False)
                if result:
                    return result

        for candidate in self.find_urls_in_text(go_body, base_url, from_page=False):
            result = self._resolve_candidate(candidate, base_url, depth, from_page=False)
            if result:
                return result

        return None
        
    def resolve_trlink(self, url, depth=0):
        self._guard_depth(depth)

        page_url, status, headers, body = self.request(url, allow_redirects=True)
        page_host = host_of(page_url)

        if page_host not in SUPPORTED_HOSTS and is_valid_final_candidate(page_url, from_page=False):
            return self.follow_http_redirects(page_url)

        if contains_human_challenge(body):
            raise RuntimeError(
                "Bu sayfa CAPTCHA/Turnstile doğrulaması istiyor. "
                "Uygulama rastgele link döndürmeyecek; doğrulama geçmeden gerçek final link alınamaz."
            )

        for candidate in self.find_urls_in_text(body, page_url, from_page=True):
            if host_of(candidate) in BILDIRIM_HOSTS:
                return self.resolve_bildirim(candidate, depth=depth + 1)

        a_val, t_val, d_val = extract_atd_values(body)
        alias = extract_alias(body, page_url)
        csrf = extract_csrf(body)

        if not (a_val and t_val and d_val):
            raise RuntimeError(
                "Aylive/Aylink için gerekli _a, _t, _d değerleri sayfadan çekilemedi. "
                "Site yapısı değişmiş veya doğrulama istiyor olabilir."
            )

        if not alias:
            raise RuntimeError("Aylive/Aylink alias değeri bulunamadı.")

        parsed = urllib.parse.urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        ajax_headers = self._ajax_headers(page_url)

        _, _, _, tk_body = self.request(
            base + "/get/tk",
            data={"_a": a_val, "_t": t_val, "_d": d_val},
            headers=ajax_headers,
            allow_redirects=True,
        )

        tkn = self._parse_tk_token(tk_body)
        if not tkn:
            raise RuntimeError("/get/tk token döndürmedi; gerçek link alınamadı.")

        payloads = [
            compact_dict({"alias": alias, "csrf": csrf, "tkn": tkn}),
            compact_dict({"alias": alias, "csrf": csrf, "token": tkn}),
            compact_dict(
                {
                    "alias": alias,
                    "_csrfToken": csrf,
                    "visitor_token": tkn,
                    "_a": a_val,
                    "_t": t_val,
                    "_d": d_val,
                    "signal": "true",
                }
            ),
        ]

        last_error = ""
        for payload in payloads:
            try:
                _, _, _, go_body = self.request(
                    base + "/links/go2",
                    data=payload,
                    headers=ajax_headers,
                    allow_redirects=True,
                )
                result = self._candidate_from_go_response(go_body, base, depth)
                if result:
                    return result

                data = parse_json_maybe(go_body)
                if isinstance(data, dict) and data.get("message"):
                    last_error = str(data.get("message"))
            except Exception as exc:
                last_error = str(exc)

        if last_error:
            raise RuntimeError("Aylive/Aylink /links/go2 gerçek URL döndürmedi: " + last_error)

        raise RuntimeError("Aylive/Aylink akışı çözülemedi; rastgele dış link döndürülmedi.")

    def resolve_tulink(self, url, depth=0):
        self._guard_depth(depth)
        url = clean_url(url)

        # Tulink süreli ara sayfa. İlk açılışta link hazır olmayabilir.
        # Birkaç kez bekleyip tekrar deniyoruz.
        last_body = ""
        last_page_url = url

        for attempt in range(4):
            page_url, status, headers, body = self.request(url, allow_redirects=True)
            last_body = body
            last_page_url = page_url

            page_host = host_of(page_url)

            # Eğer tulink başka desteklenen domaine yönlendirdiyse çözmeye devam et.
            if page_host in SUPPORTED_HOSTS and page_host != "tulink.fun":
                if page_host in GENERIC_REDIRECT_HOSTS:
                    return self.resolve_generic_redirect(page_url, depth=depth + 1)
                if page_host in TRLINK_HOSTS:
                    return self.resolve_trlink(page_url, depth=depth + 1)
                if page_host in OUO_HOSTS:
                    return self.resolve_ouo(page_url, depth=depth + 1)
                if page_host in BILDIRIM_HOSTS:
                    return self.resolve_bildirim(page_url, depth=depth + 1)

            # Eğer desteklenen domain dışına çıktıysa final say.
            if page_host not in SUPPORTED_HOSTS and is_valid_final_candidate(page_url, from_page=False):
                return self.follow_http_redirects(page_url)

            # Sayfadaki Linke Git / data-url / location / redirect alanlarını ara.
            candidates = []
            candidates.extend(high_confidence_urls_from_text(body, page_url))
            candidates.extend(self.find_urls_in_text(body, page_url, from_page=True))

            for candidate in dedupe(candidates):
                result = self._resolve_candidate(candidate, page_url, depth, from_page=False)
                if result:
                    return result

            # Buton JS ile endpoint çağırıyor olabilir. Metinde özel link endpointleri ara.
            extra_paths = []
            for pat in (
                r"""['"](/[^'"]*(?:go|link|redirect|continue|get|target)[^'"]*)['"]""",
                r"""href=["']([^"']+)["']""",
                r"""data-url=["']([^"']+)["']""",
                r"""data-href=["']([^"']+)["']""",
            ):
                for m in re.findall(pat, body or "", re.I):
                    if isinstance(m, tuple):
                        m = next((x for x in m if x), "")
                    if m:
                        extra_paths.append(m)

            for path in dedupe(extra_paths):
                candidate_url = absolutize_url(path, page_url)
                if not candidate_url:
                    continue

                ch = host_of(candidate_url)

                # Tulink iç endpointiyse onu çek, içinden final link ara.
                if ch == "tulink.fun":
                    try:
                        got_url, st, hdrs, b2 = self.request(
                            candidate_url,
                            headers={"Referer": page_url},
                            allow_redirects=True,
                        )

                        got_host = host_of(got_url)
                        if got_host in SUPPORTED_HOSTS and got_host != "tulink.fun":
                            return self._resolve_candidate(got_url, page_url, depth, from_page=False)

                        if got_host not in SUPPORTED_HOSTS and is_valid_final_candidate(got_url, from_page=False):
                            return self.follow_http_redirects(got_url)

                        for c2 in high_confidence_urls_from_text(b2, got_url):
                            result = self._resolve_candidate(c2, got_url, depth, from_page=False)
                            if result:
                                return result
                    except Exception:
                        pass

                else:
                    result = self._resolve_candidate(candidate_url, page_url, depth, from_page=False)
                    if result:
                        return result

            # Yeşil bar dolsun diye bekle.
            time.sleep(3)

        if contains_human_challenge(last_body):
            raise RuntimeError(
                "tulink.fun bekleme/koruma ekranında kaldı. "
                "Uygulama yanlış link vermedi; tarayıcıda açıp devam edebilirsin."
            )

        raise RuntimeError(
            "tulink.fun üzerinde Linke Git yönlendirmesi bulunamadı. "
            "Sayfa yapısı değişmiş veya buton sadece tarayıcı JavaScript'i ile aktif oluyor olabilir."
        )
    
    def resolve_generic_redirect(self, url, depth=0):
        self._guard_depth(depth)
        url = clean_url(url)

        target = extract_target_from_query(url)
        if target:
            result = self._resolve_candidate(target, url, depth, from_page=False)
            if result:
                return result

        page_url, status, headers, body = self.request(url, allow_redirects=True)
        page_host = host_of(page_url)

        if page_host in SUPPORTED_HOSTS:
            if page_host in BILDIRIM_HOSTS:
                return self.resolve_bildirim(page_url, depth=depth + 1)

            if page_host in TRLINK_HOSTS:
                return self.resolve_trlink(page_url, depth=depth + 1)

            if page_host in OUO_HOSTS:
                return self.resolve_ouo(page_url, depth=depth + 1)

            if page_host in GENERIC_REDIRECT_HOSTS and page_url != url:
                return self.resolve_generic_redirect(page_url, depth=depth + 1)

        if page_host not in SUPPORTED_HOSTS and is_valid_final_candidate(page_url, from_page=False):
            return self.follow_http_redirects(page_url)

        if contains_human_challenge(body):
            raise RuntimeError(
                "Bu kısaltma servisi CAPTCHA/anti-bot doğrulaması istiyor. "
                "Uygulama bunu atlatmayacak; orijinal linki tarayıcıda aç."
            )

        for candidate in high_confidence_urls_from_text(body, page_url):
            result = self._resolve_candidate(candidate, page_url, depth, from_page=False)
            if result:
                return result

        target = extract_target_from_query(page_url)
        if target:
            result = self._resolve_candidate(target, page_url, depth, from_page=False)
            if result:
                return result

        raise RuntimeError(
            "Bu kısaltma servisi normal redirect ile çözülemedi. "
            "CAPTCHA, süre bekleme veya değişmiş sayfa yapısı olabilir."
        )

    def resolve_ouo(self, url, depth=0):
        self._guard_depth(depth)

        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        slug = parsed.path.strip("/").split("/")[-1]

        if not slug:
            raise RuntimeError("OUO slug bulunamadı.")

        body = ""

        checks = [
            url,
            f"{base}/go/{slug}",
            f"{base}/xreallcygo/{slug}",
        ]

        for endpoint in checks:
            got_url, status, headers, body = self.request(endpoint, allow_redirects=False)
            loc = headers.get("Location") or headers.get("location")
            if loc:
                loc = clean_url(urllib.parse.urljoin(endpoint, loc))
                if host_of(loc) not in OUO_HOSTS and is_valid_final_candidate(loc, from_page=False):
                    return self.follow_http_redirects(loc)

        if contains_human_challenge(body):
            raise RuntimeError(
                "OUO sayfası CAPTCHA/anti-bot doğrulaması istiyor. "
                "Doğrulama tokenı olmadan gerçek final link alınamaz."
            )

        page_url, status, headers, body = self.request(url, allow_redirects=True)
        if host_of(page_url) not in SUPPORTED_HOSTS and is_valid_final_candidate(page_url, from_page=False):
            return self.follow_http_redirects(page_url)

        next_urls = [f"{base}/go/{slug}", f"{base}/xreallcygo/{slug}"]
        for next_url in next_urls:
            form_data = extract_form_tokens(body)
            if not form_data:
                break

            got_url, status, headers, body = self.request(
                next_url,
                data=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": page_url,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                allow_redirects=False,
            )

            loc = headers.get("Location") or headers.get("location")
            if loc:
                loc = clean_url(urllib.parse.urljoin(next_url, loc))
                if host_of(loc) not in OUO_HOSTS and is_valid_final_candidate(loc, from_page=False):
                    return self.follow_http_redirects(loc)

            page_url = got_url

        for candidate in high_confidence_urls_from_text(body, page_url):
            result = self._resolve_candidate(candidate, page_url, depth, from_page=False)
            if result:
                return result

        raise RuntimeError("OUO linki çözülemedi; CAPTCHA/anti-bot veya değişmiş sayfa yapısı olabilir.")

    def resolve(self, url):
        url = clean_url(url)
        h = host_of(url)

        if h in BILDIRIM_HOSTS:
            return self.resolve_bildirim(url)
        if h in TRLINK_HOSTS:
            return self.resolve_trlink(url)
        if h in OUO_HOSTS:
            return self.resolve_ouo(url)
        if h in GENERIC_REDIRECT_HOSTS:
            return self.resolve_generic_redirect(url)

        if is_http_url(url):
            return self.resolve_generic_redirect(url)

        raise RuntimeError("Desteklenmeyen domain: " + h)


def resolve_url(url):
    return Resolver().resolve(url)
