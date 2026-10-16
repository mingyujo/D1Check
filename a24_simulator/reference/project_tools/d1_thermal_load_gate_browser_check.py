"""Offline artifact verification in a new, owned headless Chrome profile."""
import base64,json,os,socket,struct,subprocess,time,urllib.request,urllib.parse,uuid,sys
from pathlib import Path
from tools import d1_thermal_load_gate_study as s

target=Path(sys.argv[1]).resolve(); expected_rows=int(sys.argv[2]); expected_band=int(sys.argv[3])
assert target.is_relative_to(s.BUNDLE.resolve())
profile=s.LOCAL/('method_browser_profile_'+uuid.uuid4().hex[:8]);profile.mkdir()
portfile=profile/'DevToolsActivePort'
log=(s.LOCAL/'method_browser_check.log').open('wb')
proc=subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new',
    '--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0',
    '--user-data-dir='+str(profile),'--window-size=1440,1080','about:blank'],
    stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
ws=None
try:
    for _ in range(100):
        if portfile.exists():break
        time.sleep(.1)
    else:raise RuntimeError('browser startup timeout')
    port=int(portfile.read_text().splitlines()[0])
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list') as r:tabs=json.load(r)
    url=urllib.parse.urlsplit(next(x for x in tabs if x['type']=='page')['webSocketDebuggerUrl'])
    ws=socket.create_connection((url.hostname,url.port),timeout=10)
    nonce=base64.b64encode(os.urandom(16)).decode()
    ws.sendall((f'GET {url.path} HTTP/1.1\r\nHost: {url.hostname}:{url.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
    headers=b''
    while not headers.endswith(b'\r\n\r\n'):headers+=ws.recv(1)
    assert headers.split(b'\r\n')[0].split()[1]==b'101',headers
    def readn(n):
        data=b''
        while len(data)<n:
            part=ws.recv(n-len(data))
            if not part:raise RuntimeError('websocket closed')
            data+=part
        return data
    counter=0
    def call(method,params=None):
        global counter
        counter+=1;data=json.dumps(dict(id=counter,method=method,params=params or {})).encode()
        mask=os.urandom(4);n=len(data)
        header=bytes([129,128|n]) if n<126 else bytes([129,254])+struct.pack('!H',n) if n<65536 else bytes([129,255])+struct.pack('!Q',n)
        ws.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
        while True:
            _,size=readn(2);n=size&127
            if n==126:n=struct.unpack('!H',readn(2))[0]
            elif n==127:n=struct.unpack('!Q',readn(8))[0]
            mask=readn(4) if size&128 else None
            data=readn(n)
            if mask:data=bytes(v^mask[i%4] for i,v in enumerate(data))
            result=json.loads(data)
            if result.get('id')==counter:
                if 'error' in result:raise RuntimeError(result['error'])
                return result.get('result',{})
    def evaluate(code):
        return call('Runtime.evaluate',dict(expression=code,returnByValue=True))['result'].get('value')
    call('Page.enable');call('Page.navigate',dict(url=target.as_uri()))
    for _ in range(60):
        if evaluate('document.readyState')=='complete':break
        time.sleep(.1)
    state=evaluate("({rows:document.querySelectorAll('tbody tr').length,images:[...document.images].map(x=>x.complete&&x.naturalWidth>0)})")
    assert state['rows']==expected_rows and len(state['images'])==5 and all(state['images']),state
    filtered=evaluate("(()=>{let x=document.querySelector('#filter');x.value='Band';x.dispatchEvent(new Event('input'));return [...document.querySelectorAll('tbody tr')].filter(r=>!r.hidden).length;})()")
    assert filtered==expected_band,filtered
    reset=evaluate("(()=>{let x=document.querySelector('#filter');x.value='';x.dispatchEvent(new Event('input'));return [...document.querySelectorAll('tbody tr')].filter(r=>!r.hidden).length;})()")
    assert reset==expected_rows
    shot=call('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))['data']
    (s.LOCAL/(target.parent.name+'_dashboard.png')).write_bytes(base64.b64decode(shot))
    result=dict(utc=s.utc(),status='PASS',surface='isolated headless Chrome; offline file page',
        rows=expected_rows,filtered_band_rows=expected_band,reset_rows=expected_rows,images_loaded=5,
        screenshot=(s.LOCAL/(target.parent.name+'_dashboard.png')).relative_to(s.ROOT).as_posix(),
        target=target.relative_to(s.ROOT).as_posix(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),dirty=True,
        checker_sha256=s.sha(__file__),
        consumption=s.used())
    s.write(target.parent/'browser_verification.json',result)
    print(json.dumps(result))
    try:call('Browser.close')
    except (RuntimeError,OSError,json.JSONDecodeError):pass
finally:
    if ws:ws.close()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)
    log.close()
