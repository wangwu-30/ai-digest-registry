# Independent implementation from SKILL.md §4.4 (round-3 text) only.
import hashlib, re, idna
from urllib.parse import urlsplit, unquote_plus, quote
DROP=set("utm_source utm_medium utm_campaign utm_term utm_content utm_id utm_name fbclid gclid dclid msclkid igshid mc_cid mc_eid ref ref_src ref_url si spm".split())
UNRES=set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
def _path_pct(path):
    def f(m):
        ch=chr(int(m.group(1),16))
        return ch if ch in UNRES else "%"+m.group(1).upper()
    return re.sub(r"%([0-9A-Fa-f]{2})",f,path)
def canonical(u):
    p=urlsplit(u.strip())
    scheme=p.scheme.lower()
    if scheme not in("http","https"): raise ValueError("reject scheme")
    netloc=p.netloc.rsplit("@",1)[-1]
    if netloc.startswith("["): raise ValueError("ipv6 not handled")
    host,_,port=netloc.partition(":")
    host=host.lower().rstrip(".")
    if not host: raise ValueError("no host")
    host=".".join(idna.encode(l,uts46=True,transitional=False).decode("ascii") if any(ord(c)>127 for c in l) else l for l in host.split("."))
    for pre in("www.","m.","mobile."):
        if host.startswith(pre) and host.count(".")>=2: host=host[len(pre):]; break
    if host=="twitter.com": host="x.com"
    if port and not ((scheme=="http" and port=="80") or (scheme=="https" and port=="443")): host=f"{host}:{port}"
    path=p.path or "/"
    path=re.sub(r"/+","/",path)
    path=_path_pct(path)
    if path!="/": path=path.rstrip("/")
    if host=="x.com":
        m=re.match(r"^/([^/]+|i/web)/status(es)?/(\d+)",path,re.I)
        if m: return "x.com/i/status/"+m.group(3)
        return host+path.lower()
    pairs=[]
    for part in p.query.split("&"):
        if not part: continue
        k,_,v=part.partition("=")
        k=unquote_plus(k); v=unquote_plus(v)
        if k.lower() in DROP: continue
        pairs.append((k,v))
    pairs.sort()
    q="&".join(quote(k,safe="-._~")+"="+quote(v,safe="-._~") for k,v in pairs)
    return host+path+("?"+q if q else "")
def item_id(u,entry=None):
    return hashlib.sha256((canonical(u)+("#"+entry if entry else "")).encode("utf-8")).hexdigest()[:16]
