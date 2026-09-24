"""遍历交付面板的全部版本和展示关卡，逐步核对 DOM 与实测路径。"""
from __future__ import annotations
import argparse,datetime,json,pathlib,shutil,time
from playwright.sync_api import sync_playwright

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--html',required=True);ap.add_argument('--out',default='browser-replay-coverage.json');args=ap.parse_args()
    path=pathlib.Path(args.html);start=time.perf_counter();scenarios=states=failed_without_fake_path=0;errors=[]
    with sync_playwright() as p:
        opts={'headless':True}
        if shutil.which('chromium'):opts['executable_path']=shutil.which('chromium')
        browser=p.chromium.launch(**opts);page=browser.new_page(viewport={'width':1100,'height':980});page.set_default_timeout(4000)
        page.on('pageerror',lambda err:errors.append(str(err)));page.set_content(path.read_text(),wait_until='domcontentloaded')
        data=json.loads(page.locator('#experiment-data').text_content())
        for gi,h in enumerate(data['status']['history']):
            for pi,r in enumerate(data['replays'][str(h['generation'])]['details']):
                scenarios+=1;page.locator('#version').select_option(str(gi));page.locator('#puzzle').select_option(str(pi))
                pathstates=r.get('path',[])
                if not pathstates:
                    assert page.locator('#play').is_disabled();failed_without_fake_path+=1
                    actual=page.locator('#candidate-board .tile').evaluate_all('(ts)=>ts.map(t=>Number(t.textContent||0))')
                    assert actual==r['board'];continue
                for index,expected in enumerate(pathstates):
                    actual=page.locator('#candidate-board .tile').evaluate_all('(ts)=>ts.map(t=>Number(t.textContent||0))')
                    assert actual==expected,(h['generation'],pi,index,actual,expected);states+=1
                    if index<len(pathstates)-1:page.locator('#next').click()
                assert page.locator('#next').is_disabled()
        assert not errors;browser.close()
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'html':path.name,'scenarios_checked':scenarios,'path_states_checked':states,'failed_scenarios_without_fake_path':failed_without_fake_path,'all_passed':True,'javascript_errors':errors,'wall_seconds':time.perf_counter()-start,'scope':'All displayed version/puzzle combinations; DOM was checked against saved measured solution paths.'}
    pathlib.Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
