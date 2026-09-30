def apply(core):
    import urllib.parse, html

    old_get=core._AdGateHandler.do_GET
    def get(h):
        path=urllib.parse.urlparse(h.path).path
        if path.startswith("/dashboard/") and not path.endswith("/avatar"):
            bid=path.split("/",2)[2] if len(path.split("/",2))>2 else ""
            original=h._send
            def send(code,body,ctype="text/html; charset=utf-8"):
                if code==200 and isinstance(body,str) and "QuickDL Dashboard" in body:
                    avatar="/dashboard/"+bid+"/avatar"
                    badge='<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px"><img src="'+avatar+'" style="width:56px;height:56px;border-radius:18px;object-fit:cover;border:1px solid #ffffff22" onerror="this.style.display=\\'none\\'"><span style="opacity:.7">Telegram profile</span></div>'
                    body=body.replace('<div id="login"',badge+'<div id="login"',1)
                return original(code,body,ctype)
            h._send=send
            try: return old_get(h)
            finally: h._send=original
        return old_get(h)
    core._AdGateHandler.do_GET=get
    return core
