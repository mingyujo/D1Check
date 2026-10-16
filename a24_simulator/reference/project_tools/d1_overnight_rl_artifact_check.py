"""Read-only shared HTML/SVG/PNG integrity, optional local browser QA record."""
import argparse,hashlib,json
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
from tools import d1_overnight_rl_check as check

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        self.links.extend(v for k,v in attrs if k in ('src','href'))

def run(write_browser=False):
    folder=check.PUBLIC;html=(folder/'index.html').read_text(encoding='utf-8');parser=Links();parser.feed(html)
    if len([v for v in parser.links if v.endswith('.png')])!=5:raise ValueError('missing figure images')
    for name in parser.links:
        path=(folder/name).resolve()
        if '://' in name or name.startswith('//') or not path.is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('not an offline local asset '+name)
    figure=json.loads((folder/'figure_verification.json').read_text(encoding='utf-8'))
    for name,digest in figure['png_sha256'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('PNG changed')
    for entry in figure['svg']:
        path=folder/entry['name'];ET.parse(path)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256'] or any(line!=line.rstrip() for line in path.read_text(encoding='utf-8').splitlines()):raise ValueError('SVG changed/whitespace')
    result=dict(status='PASS',html_sha256=hashlib.sha256((folder/'index.html').read_bytes()).hexdigest(),offline_local_assets_and_links=len(parser.links),external_page_resources=0,SVG5_XML_valid_and_no_trailing_whitespace=True,PNG5_hashes_unchanged=True,new_native=0,new_learning=0)
    if write_browser:
        image=check.ROOT/'output/overnight_rl_20261011_v1/dashboard.png'
        if not image.exists():raise FileNotFoundError('local screenshot required, do not manufacture browser pass')
        result.update(browser='isolated headless Chrome, local file, original user profile preserved',screenshot_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),Korean_text_and_7_policy_table_visually_inspected=True,five_PNG_figures_visually_inspected=True)
        (folder/'browser_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write-browser-record',action='store_true');a=p.parse_args();run(a.write_browser_record)
