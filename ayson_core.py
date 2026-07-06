import base64
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

try:
    import certifi
except Exception:
    certifi = None


VERSION = "V1.3-app-force-ssl-bypass"


def make_unverified_context(*args, **kwargs):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# Android APK içinde Python bazen CA sertifika zincirini bulamıyor.
# Bu yüzden bu araçta SSL doğrulamasını global olarak kapatıyoruz.
ssl._create_default_https_context = ssl._create_unverified_context
ssl.create_default_context = make_unverified_context


SUPPORTED_HOSTS = {
    "ay.live",
    "aylink.co",
    "cpmlink.pro",
    "bildirim.online",
    "bildirim.vip",
    "ouo.io",
    "ouo.press",
}

TRLINK_HOSTS = {"ay.live", "aylink.co", "cpmlink.pro"}
BILDIRIM_HOSTS = {"bildirim.online", "bildirim.vip"}
OUO_HOSTS = {"ouo.io", "ouo.press"}

URL_RE = re.compile(r"https?://[^\s'\"<>`]+", re.I)


def clean_url(u):
    return html.unescape(str(u)).strip().strip(".,;)'\"`]")


def host_of(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        host = host.split("@")[-1].split(":")[0]

        if host.startswith("www."):
            host = host[4:]

        return host
    except Exception:
        return ""


def b64_try_decode(s):
    s = str(s).strip()
    s += "=" * (-len(s) % 4)

    try:
        return base64.b64decode(s).decode("utf-8", "ignore")
    except Exception:
        return ""


class Resolver:
    def __init__(self):
        self.cj = CookieJar()

        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ssl_context),
        )

        urllib.request.install_opener(self.opener)

    def request(self, url, data=None, headers=None, method=None, timeout=35, allow_redirects=True):
        if headers is None:
            headers = {}

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

        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=default_headers, method=method)

        if allow_redirects:
            with self.opener.open(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "ignore")
                return r.geturl(), getattr(r, "status", 200), dict(r.headers), body

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                return None

        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ssl_context),
            NoRedirect,
        )

        try:
            with opener.open(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "ignore")
                return r.geturl(), getattr(r, "status", 200), dict(r.headers), body
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            return url, e.code, dict(e.headers), body

    def find_urls_in_text(self, text):
        text = text or ""
        out = []

        for u in URL_RE.findall(text):
            u = clean_url(u)

            if u not in out:
                out.append(u)

        for m in re.findall(r"decodeURIComponent\(['\"]([^'\"]+)['\"]\)", text, re.I):
            try:
                u = clean_url(urllib.parse.unquote(m))

                if u.startswith("http") and u not in out:
                    out.append(u)
            except Exception:
                pass

        for m in re.findall(r"atob\(['\"]([^'\"]+)['\"]\)", text, re.I):
            u = clean_url(b64_try_decode(m))

            if u.startswith("http") and u not in out:
                out.append(u)

        return out

        def resolve_bildirim(self, url):
        final_url, status, headers, body = self.request(url)

        candidates = []

        parsed = urllib.parse.urlparse(url)
        last = parsed.path.rstrip("/").split("/")[-1]
        decoded_path = b64_try_decode(last)

        if decoded_path:
            candidates.extend(self.find_urls_in_text(decoded_path))

        candidates.extend(self.find_urls_in_text(body))

        patterns = [
            r"""data-url=["']([^"']+)["']""",
            r"""data-href=["']([^"']+)["']""",
            r"""(?:go_url|uri_full|target|destination|redirect|real_url|realUrl|url)\s*[:=]\s*["']([^"']+)["']""",
            r"""window\.open\(["']([^"']+)["']""",
            r"""location(?:\.href)?\s*=\s*["']([^"']+)["']""",
            r"""href=["']([^"']+)["']""",
        ]

        for pat in patterns:
            for m in re.findall(pat, body or "", re.I):
                m = clean_url(m)

                if m.startswith("//"):
                    m = "https:" + m

                if m.startswith("http") and m not in candidates:
                    candidates.append(m)

        def is_bad_candidate(candidate):
            h = host_of(candidate)
            p = urllib.parse.urlparse(candidate).path.lower()

            bad_hosts = {
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
            }

            bad_exts = (
                ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map"
            )

            if h in bad_hosts:
                return True

            if p.endswith(bad_exts):
                return True

            if "bootstrap" in candidate.lower():
                return True

            if "jquery" in candidate.lower():
                return True

            return False

        cleaned = []
        for c in candidates:
            c = clean_url(c)

            if not c.startswith("http"):
                continue

            if c in cleaned:
                continue

            if is_bad_candidate(c):
                continue

            cleaned.append(c)

        # Önce desteklenen ara domain olmayan gerçek hedefleri seç.
        for c in cleaned:
            h = host_of(c)

            if h not in SUPPORTED_HOSTS:
                return c

        # Eğer sadece desteklenen ara linkler kaldıysa sonuncuyu dön.
        if cleaned:
            return cleaned[-1]

        raise RuntimeError("bildirim ara sayfasında gerçek link bulunamadı.")
        
    def resolve_ouo(self, url):
        parsed = urllib.parse.urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        slug = parsed.path.strip("/")

        if not slug:
            raise RuntimeError("OUO slug bulunamadı.")

        checks = [
            url,
            f"{base}/go/{slug}",
            f"{base}/xreallcygo/{slug}",
        ]

        for u in checks:
            got_url, status, headers, body = self.request(u, allow_redirects=False)

            loc = headers.get("Location") or headers.get("location")

            if loc:
                loc = clean_url(urllib.parse.urljoin(u, loc))

                if host_of(loc) not in OUO_HOSTS:
                    return loc

            for candidate in self.find_urls_in_text(body):
                if host_of(candidate) not in OUO_HOSTS:
                    return candidate

        raise RuntimeError("OUO linki çözülemedi. CAPTCHA veya anti-bot olabilir.")

    def resolve_trlink(self, url):
        page_url, status, headers, body = self.request(url)

        for u in self.find_urls_in_text(body):
            if host_of(u) in BILDIRIM_HOSTS:
                return self.resolve_bildirim(u)

        def find_one(patterns):
            for p in patterns:
                m = re.search(p, body or "", re.I)

                if m:
                    return html.unescape(m.group(1))

            return ""

        alias = find_one([
            r"""alias\s*[:=]\s*["']([^"']+)["']""",
            r"""['"]alias['"]\s*:\s*['"]([^'"]+)['"]""",
            r"""data-alias=["']([^"']+)["']""",
        ])

        csrf = find_one([
            r"""csrfToken\s*[:=]\s*["']([^"']+)["']""",
            r"""csrf_token\s*[:=]\s*["']([^"']+)["']""",
            r"""name=["']csrf-token["']\s+content=["']([^"']+)["']""",
            r"""content=["']([^"']+)["']\s+name=["']csrf-token["']""",
        ])

        a_val = find_one([
            r"""_a\s*=\s*["']([^"']+)["']""",
            r"""name=["']_a["']\s+value=["']([^"']+)["']""",
        ])

        t_val = find_one([
            r"""_t\s*=\s*["']([^"']+)["']""",
            r"""name=["']_t["']\s+value=["']([^"']+)["']""",
        ])

        d_val = find_one([
            r"""_d\s*=\s*["']([^"']+)["']""",
            r"""name=["']_d["']\s+value=["']([^"']+)["']""",
        ])

        parsed = urllib.parse.urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        visitor_token = ""

        try:
            tk_payload = {}

            if alias:
                tk_payload["alias"] = alias

            if csrf:
                tk_payload["_csrfToken"] = csrf

            _, _, _, tk_body = self.request(
                base + "/get/tk",
                data=tk_payload,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": page_url,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
            )

            try:
                j = json.loads(tk_body)
                visitor_token = str(
                    j.get("visitor_token")
                    or j.get("token")
                    or j.get("tk")
                    or ""
                )
            except Exception:
                visitor_token = ""

        except Exception:
            pass

        go_payload = {}

        if alias:
            go_payload["alias"] = alias

        if csrf:
            go_payload["_csrfToken"] = csrf

        if visitor_token:
            go_payload["visitor_token"] = visitor_token

        if a_val:
            go_payload["_a"] = a_val

        if t_val:
            go_payload["_t"] = t_val

        if d_val:
            go_payload["_d"] = d_val

        go_payload["signal"] = "true"

        try:
            _, _, _, go_body = self.request(
                base + "/links/go2",
                data=go_payload,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": page_url,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                },
            )

            try:
                j = json.loads(go_body)
                candidate = (
                    j.get("url")
                    or j.get("redirect")
                    or j.get("location")
                    or j.get("href")
                )

                if candidate:
                    candidate = clean_url(candidate)

                    if host_of(candidate) in BILDIRIM_HOSTS:
                        return self.resolve_bildirim(candidate)

                    return candidate

            except Exception:
                pass

            for u in self.find_urls_in_text(go_body):
                if host_of(u) in BILDIRIM_HOSTS:
                    return self.resolve_bildirim(u)

                if host_of(u) not in SUPPORTED_HOSTS:
                    return u

        except Exception:
            pass

        for u in self.find_urls_in_text(body):
            if host_of(u) not in SUPPORTED_HOSTS:
                return u

        raise RuntimeError("Aylive/Aylink akışı çözülemedi.")

    def resolve(self, url):
        url = clean_url(url)
        h = host_of(url)

        if h in BILDIRIM_HOSTS:
            return self.resolve_bildirim(url)

        if h in OUO_HOSTS:
            return self.resolve_ouo(url)

        if h in TRLINK_HOSTS:
            return self.resolve_trlink(url)

        raise RuntimeError("Desteklenmeyen domain: " + h)


def resolve_url(url):
    return Resolver().resolve(url)
