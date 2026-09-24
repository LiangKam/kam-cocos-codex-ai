"""实际浏览器验收。可选依赖：pip install playwright && playwright install chromium。

本次环境的 agent-browser 获取超时后，实际使用本地 Chromium + Playwright。
交付主程序和 HTML 不依赖 Playwright；只有此 UI 验收脚本需要它。
"""
from __future__ import annotations
import argparse,datetime,json,pathlib,shutil
from playwright.sync_api import sync_playwright

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--html',default='report.html');ap.add_argument('--out',default='browser-evidence');ap.add_argument('--chromium',default=shutil.which('chromium'));args=ap.parse_args()
    path=pathlib.Path(args.html).resolve();out=pathlib.Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    if not path.is_file():ap.error('HTML 文件不存在')
    checks=[];errors=[]
    def check(name,passed):checks.append({'test':name,'passed':bool(passed)})
    with sync_playwright() as p:
        opts={'headless':True}
        if args.chromium:opts['executable_path']=args.chromium
        browser=p.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':1280,'height':980},device_scale_factor=1)
        page.set_default_timeout(5000);page.on('pageerror',lambda error:errors.append(str(error)))
        # 本环境禁止 file:// 导航，直接装载我们生成的离线 HTML；不伪造截图。
        page.set_content(path.read_text(),wait_until='domcontentloaded');page.wait_for_selector('#candidate-board .tile')
        data=json.loads(page.locator('#experiment-data').text_content())
        check('page_load',page.title()=='RSI Puzzle Lab · 自改进实验台')
        check('two_boards_18_tiles',page.locator('.board .tile').count()==18)
        check('real_generation_rows',page.locator('#history tr').count()==len(data['status']['history']))
        page.locator('#next').click();check('next_step','第 1 /' in page.locator('#steps').inner_text())
        page.locator('#prev').click();check('previous_step','第 0 /' in page.locator('#steps').inner_text())
        page.locator('#play').click();page.wait_for_function("document.getElementById('steps').textContent.startsWith('第 2 /')")
        page.locator('#play').click();check('animation_plays_and_pauses','播放通关' in page.locator('#play').inner_text())
        page.locator('#reset').click();check('reset_step','第 0 /' in page.locator('#steps').inner_text())
        page.locator('#puzzle').select_option('4');check('puzzle_selection','28' in page.locator('#candidate-info').inner_text())
        page.locator('#version').select_option('0');check('failed_baseline_no_fake_path',page.locator('#play').is_disabled())
        last=str(page.locator('#version option').count()-1);page.locator('#version').select_option(last)
        for _ in range(8):page.locator('#next').click()
        check('replayed_states_differ_from_initial',page.locator('#baseline-board').inner_text()!=page.locator('#candidate-board').inner_text())
        check('activity_bars_match_log_minutes',page.locator('#activity-chart rect').count()==len(data.get('activity',[])))
        check('plateau_explicit','未发现更优候选' in page.locator('#plateau-note').inner_text())
        check('snapshot_elapsed_does_not_fake_advance',page.locator('#elapsed').inner_text()==f"{int(data['status']['elapsed_seconds']//60)}分{int(data['status']['elapsed_seconds']%60):02d}秒")
        page.screenshot(path=str(out/'desktop.png'),full_page=True)
        check('desktop_no_horizontal_overflow',page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(out/'mobile.png'),full_page=True)
        check('mobile_no_horizontal_overflow',page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        check('no_javascript_error',not errors);version=browser.version;browser.close()
    result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'html':path.name,'browser':'Chromium via Playwright','browser_version':version,'checks':checks,'errors':errors,'all_passed':all(c['passed'] for c in checks)}
    (out/'browser-tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['all_passed']:raise SystemExit(1)
if __name__=='__main__':main()
