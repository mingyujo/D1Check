"""Headless offline HTML QA using an isolated browser profile."""
import json
from pathlib import Path
import re
import subprocess
from tools import d1_triton_study as s


def run():
    source = s.BUNDLE / 'index.html'
    page = source.read_text(encoding='utf8').replace('<meta charset="utf-8">',
        '<meta charset="utf-8"><base href="' + s.BUNDLE.as_uri() + '/">', 1)
    script = '''<script>
const qa={defaultRows:document.querySelector('#rows').children.length,defaultGroups:document.querySelector('#groups').children.length};
policy.value='TRITON_RATE_CAP1_EQUAL_REQUEST_ADAPT_V1';render();qa.serialRows=document.querySelector('#rows').children.length;
qa.partialMarked=document.querySelector('#rows').textContent.includes('(부분)');qa.unavailableAP=document.querySelector('#rows').textContent.includes('계산 불가');
family.value='all';policy.value='all';render();qa.allRows=document.querySelector('#rows').children.length;qa.allGroups=document.querySelector('#groups').children.length;
family.value='low';render();qa.lowRows=document.querySelector('#rows').children.length;
policy.value='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1';render();qa.singlePolicyRows=document.querySelector('#rows').children.length;
qa.selfZero=[...document.querySelector('#rows').children].every(x=>x.children[10].textContent==='0.000');
reference.value='SHARED_EFT';render();qa.referenceSwitch=[...document.querySelector('#rows').children].some(x=>x.children[10].textContent!=='0.000');
qa.passed=qa.defaultRows===156&&qa.defaultGroups===13&&qa.serialRows===12&&qa.partialMarked&&qa.unavailableAP&&qa.allRows===624&&qa.allGroups===52&&qa.lowRows===156&&qa.singlePolicyRows===12&&qa.selfZero&&qa.referenceSwitch;
const proof=document.createElement('pre');proof.id='qa';proof.textContent=JSON.stringify(qa);document.body.append(proof);
family.value='sustained';policy.value='all';render();
</script>'''
    target = s.LOCAL / 'qa_dashboard.html'
    target.write_text(page.replace('</html>', script + '</html>'), encoding='utf8')
    command = ['C:/Program Files/Google/Chrome/Application/chrome.exe', '--headless=new', '--disable-gpu',
        '--disable-background-networking', '--disable-component-update', '--no-first-run',
        '--user-data-dir=' + str(s.LOCAL / 'chrome_qa'), '--allow-file-access-from-files',
        '--virtual-time-budget=1500', '--window-size=1440,1300',
        '--screenshot=' + str(s.LOCAL / 'dashboard.png'), '--dump-dom', target.as_uri()]
    with (s.LOCAL / 'dashboard.dom').open('w', encoding='utf8') as out, (s.LOCAL / 'chrome.log').open('w', encoding='utf8') as err:
        result = subprocess.run(command, stdout=out, stderr=err, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    dom = (s.LOCAL / 'dashboard.dom').read_text(encoding='utf8')
    match = re.search(r'<pre id="qa">([^<]+)</pre>', dom)
    proof = json.loads(match.group(1)) if match else {'passed': False, 'reason': 'no QA script output'}
    proof.update(utc=s.stamp(), source_sha256=s.digest(source), exit_code=result.returncode,
                 environment_runs=0, isolated_profile=True)
    s.write(s.BUNDLE / 'dashboard_verification.json', proof)
    print(json.dumps(proof))
    if not proof['passed'] or result.returncode:
        raise ValueError('offline dashboard QA failed')


if __name__ == '__main__':
    run()
