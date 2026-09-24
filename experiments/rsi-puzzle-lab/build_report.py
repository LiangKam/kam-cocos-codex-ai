"""导出离线 HTML；数据内嵌，不依赖外网、服务器或外部脚本。"""
import argparse,json,pathlib,datetime,collections
ROOT=pathlib.Path(__file__).parent
ap=argparse.ArgumentParser();ap.add_argument('--run',default='runs/main');ap.add_argument('--out',default='report.html');args=ap.parse_args();run=ROOT/args.run
status=json.loads((run/'status.json').read_text());replays={}
for h in status['history']:
    replays[str(h['generation'])]=json.loads((run/'champions'/f'g{h["generation"]:03d}-replays.json').read_text())
events=[]
with (run/'events.jsonl').open() as f:
    for line in collections.deque(f,maxlen=24):
        try:events.append(json.loads(line))
        except json.JSONDecodeError:pass # 运行中只忽略末尾尚未写完的一行，不制造记录。
holdout=json.loads((run/'holdout.json').read_text()) if (run/'holdout.json').exists() else None
if holdout:
    for v in holdout['versions']:v['metrics'].pop('details',None)
data={'built_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'replays':replays,'holdout':holdout,'recent_events':events}
encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
html=(ROOT/'dashboard.template.html').read_text().replace('__EXPERIMENT_DATA__',encoded)
out=pathlib.Path(args.out);out=out if out.is_absolute() else ROOT/out;out.write_text(html)
print(out, len(html.encode()),'bytes',status['elapsed_seconds'],'seconds snapshot',len(status['history']),'versions')
