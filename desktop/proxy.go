package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
)

const proxyPort = 8767

// navInject is injected into every HTML page the proxy serves.
// It adds a floating Back button (visible when history.length > 1 and not at root)
// and keyboard shortcuts (Alt+Left / Cmd+[ for back, Alt+Right / Cmd+] for forward).
const navInject = `<script>
(function(){
  document.addEventListener('keydown',function(e){
    if((e.altKey||e.metaKey)&&e.key==='ArrowLeft'){e.preventDefault();history.back();}
    if((e.altKey||e.metaKey)&&e.key==='ArrowRight'){e.preventDefault();history.forward();}
  });
  function makeBtn(){
    var b=document.createElement('button');
    b.id='__nav_back';
    b.textContent='← Back';
    b.style.cssText=[
      'position:fixed','bottom:20px','left:20px',
      'z-index:2147483647',
      'background:rgba(17,24,39,0.88)',
      'color:#f9fafb',
      'border:1px solid rgba(255,255,255,0.12)',
      'padding:7px 18px',
      'border-radius:20px',
      'cursor:pointer',
      'font-size:13px',
      'font-family:inherit',
      'box-shadow:0 2px 10px rgba(0,0,0,0.5)',
      'backdrop-filter:blur(6px)',
      'display:none',
      'transition:opacity 0.15s',
    ].join(';');
    b.onmouseenter=function(){this.style.background='rgba(59,130,246,0.9)';};
    b.onmouseleave=function(){this.style.background='rgba(17,24,39,0.88)';};
    b.onclick=function(){history.back();};
    document.body.appendChild(b);
    return b;
  }
  function sync(b){
    b.style.display=(history.length>1&&location.pathname!=='/')?'block':'none';
  }
  document.addEventListener('DOMContentLoaded',function(){
    var b=document.getElementById('__nav_back')||makeBtn();
    sync(b);
    var ps=history.pushState;
    history.pushState=function(){ps.apply(this,arguments);setTimeout(function(){sync(b);},80);};
    var rs=history.replaceState;
    history.replaceState=function(){rs.apply(this,arguments);setTimeout(function(){sync(b);},80);};
    window.addEventListener('popstate',function(){sync(b);});
  });
})();
</script>`

// startProxy launches a reverse proxy that forwards to pypsa-app and injects
// the navigation script into every HTML response. It runs for the lifetime of
// the app; errors are non-fatal (worst case the user points at the direct URL).
func startProxy(appPort, pxPort int) {
	target, _ := url.Parse(fmt.Sprintf("http://127.0.0.1:%d", appPort))

	proxy := httputil.NewSingleHostReverseProxy(target)

	// Disable compression so ModifyResponse can work on plain text.
	origDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		origDirector(req)
		req.Header.Set("Accept-Encoding", "identity")
	}

	proxy.ModifyResponse = func(resp *http.Response) error {
		if !strings.Contains(resp.Header.Get("Content-Type"), "text/html") {
			return nil
		}
		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			return err
		}
		// Inject before </head> so it runs early; fall back to appending.
		out := bytes.Replace(body, []byte("</head>"), []byte(navInject+"</head>"), 1)
		if bytes.Equal(out, body) {
			out = append(body, []byte(navInject)...)
		}
		resp.Body = io.NopCloser(bytes.NewReader(out))
		resp.ContentLength = int64(len(out))
		resp.Header.Set("Content-Length", fmt.Sprintf("%d", len(out)))
		resp.Header.Del("Content-Encoding")
		return nil
	}

	go http.ListenAndServe(fmt.Sprintf("127.0.0.1:%d", pxPort), proxy) //nolint:errcheck
}
