"""只在搜索结束后执行一次的保留集审计；只报告，不根据测试集改选冠军。"""
import argparse,json,pathlib,time
from domain import Features
from evaluator import evaluate,assert_frozen
from evolve import write_json
root=pathlib.Path(__file__).parent
ap=argparse.ArgumentParser();ap.add_argument('--run',default='runs/main');args=ap.parse_args();run=root/args.run
assert_frozen(root)
status=json.loads((run/'status.json').read_text())
if status['state']=='running':raise SystemExit('搜索尚未结束；不能提前读取保留集')
if (run/'holdout.json').exists():raise SystemExit('保留集已经使用；拒绝二次选优')
rows=json.loads((root/'datasets/holdout.json').read_text());features=Features();results=[]
for champion in status['history']:
    r=evaluate(champion['config'],rows,features)
    results.append({'generation':champion['generation'],'id':champion['id'],'config':champion['config'],'metrics':r})
result={'selection_already_frozen':True,'selected_generation':status['champion']['generation'],'count':len(rows),'versions':results,'used_to_select':False,'final_passed':results[-1]['metrics']['invalid']==0}
write_json(run/'holdout.json',result);status['holdout_used']=True;status['holdout_selected_new_winner']=False;write_json(run/'status.json',status)
print(json.dumps([{k:r[k] for k in ('generation','config')}|{'solved':r['metrics']['solved'],'invalid':r['metrics']['invalid'],'mean_expanded':r['metrics']['mean_expanded']} for r in results],ensure_ascii=False,indent=2))
