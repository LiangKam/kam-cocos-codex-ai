"""导出离线 HTML：真实路径、按分钟活动记录、强对照和审计结果。"""
import argparse,json,pathlib,datetime,collections
ROOT=pathlib.Path(__file__).parent
ap=argparse.ArgumentParser();ap.add_argument('--run',default='runs/main');ap.add_argument('--out',default='report.html');args=ap.parse_args();run=ROOT/args.run
status=json.loads((run/'status.json').read_text());replays={}
for h in status['history']:
    replays[str(h['generation'])]=json.loads((run/'champions'/f'g{h["generation"]:03d}-replays.json').read_text())
events=[];activity=collections.defaultdict(lambda:{'evaluated':0,'accepted':0,'rejected':0})
with (run/'events.jsonl').open() as f:
    for line in f:
        try:e=json.loads(line)
        except json.JSONDecodeError:continue
        if e.get('kind')=='candidate' and e['evaluation']<=status['evaluated_candidates']:
            bucket=int(e['at_seconds']//60);activity[bucket]['evaluated']+=1
            activity[bucket]['accepted' if e['accepted'] else 'rejected']+=1
            events.append(e)
holdout=json.loads((run/'holdout.json').read_text()) if (run/'holdout.json').exists() else None
if holdout:
    for v in holdout['versions']:v['metrics'].pop('details',None)
def optional(p):return json.loads(p.read_text()) if p.exists() else None
# 强对照及重复实验不作为主实验的选择输入，报告中明确限定适用范围。
main_only=run.resolve()==(ROOT/'runs/main').resolve()
data={'built_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':status,'replays':replays,'holdout':holdout,'recent_events':events[-24:],'activity':[{'minute':k,**v} for k,v in sorted(activity.items())],'audit':optional(run/'audit.json'),'reference_benchmarks':optional(ROOT/'reference-benchmarks.json') if main_only else None,'repeated_seeds':optional(ROOT/'repeat-seeds-results.json') if main_only else None}
encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
html=(ROOT/'dashboard.template.html').read_text().replace('__EXPERIMENT_DATA__',encoded)
out=pathlib.Path(args.out);out=out if out.is_absolute() else ROOT/out;out.write_text(html)
print(out,len(html.encode()),'bytes',status['elapsed_seconds'],'seconds snapshot',len(status['history']),'versions')
