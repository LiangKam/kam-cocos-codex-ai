"""独立检查实验事件、父代继承、接管条件，并抽样重跑以验证结果指纹。

运行中的快照只审计 status 已声明完成的事件；不会读取保留集。
此脚本的产物不反馈给自改进器，也不修改任何候选或评分规则。
"""
from __future__ import annotations
import argparse,collections,hashlib,json,pathlib,random,statistics,time
from domain import Features
from strategy import config_id,source_for
from evolve import is_certified,write_json
from evaluator import evaluate,score,assert_frozen
ROOT=pathlib.Path(__file__).resolve().parent

def audit(run:pathlib.Path,recheck:int):
    assert_frozen(ROOT);started=time.perf_counter()
    status=json.loads((run/'status.json').read_text());limit=status['evaluated_candidates']
    events=[]
    for line in (run/'events.jsonl').read_text().splitlines():
        try:e=json.loads(line)
        except json.JSONDecodeError:continue
        if e.get('kind')=='candidate' and e['evaluation']<=limit:events.append(e)
    history=status['history'];seen={history[0]['id']};last=history[0];accepted=[];bins=collections.defaultdict(lambda:{'evaluated':0,'accepted':0,'rejected':0});endpoints=[]
    for i,e in enumerate(events,1):
        assert e['evaluation']==i,('missing_evaluation',i)
        assert e['id']==config_id(e['config']),('wrong_id',i)
        assert e['source_sha256']==hashlib.sha256(source_for(e['config']).encode()).hexdigest(),('wrong_source_hash',i)
        assert e['id'] not in seen,('duplicate_evaluation',i)
        assert e['parent'] in seen,('unknown_parent',i)
        assert is_certified(e['config']['expression']),('uncertified_expression',i)
        seen.add(e['id']);bucket=int(e['at_seconds']//60);bins[bucket]['evaluated']+=1
        bins[bucket]['accepted' if e['accepted'] else 'rejected']+=1;endpoints.append(e['at_seconds'])
        if e['accepted']:
            assert e['validation'] is not None
            assert e['train']['invalid']==0 and e['validation']['invalid']==0
            assert score(e['train'])>=score(last['train']) and score(e['validation'])>score(last['validation']),('bad_promotion',i)
            accepted.append(e);last=history[len(accepted)]
            assert last['id']==e['id'] and last['config']==e['config'],('history_mismatch',i)
    assert len(events)==limit and len(accepted)==status['accepted_generations']
    for h in history:
        name=f'g{h["generation"]:03d}.py';source=(run/'champions'/name).read_text()
        assert source==source_for(h['config']);compile(source,name,'exec')
        assert hashlib.sha256(source.encode()).hexdigest()==h['source_sha256']
    train=json.loads((ROOT/'datasets/train.json').read_text());val=json.loads((ROOT/'datasets/validation.json').read_text());features=Features()
    # 固定抽样种子，不根据候选结果挑选容易重现的记录；获准接管的记录全部复核。
    chosen={e['evaluation']:e for e in accepted}
    for e in random.Random(9262026).sample(events,min(recheck,len(events))):chosen[e['evaluation']]=e
    matched=[]
    for e in chosen.values():
        tr=evaluate(e['config'],train,features);vr=evaluate(e['config'],val,features) if e['validation'] else None
        digest=hashlib.sha256(json.dumps([tr['details'],vr['details'] if vr else None],sort_keys=True).encode()).hexdigest()
        assert digest==e['result_sha256'],('nonreproducible_results',e['evaluation'])
        matched.append(e['evaluation'])
    gaps=[b-a for a,b in zip(endpoints,endpoints[1:])]
    elapsed=status['elapsed_seconds'];last_accept=history[-1]['at_seconds']
    result={'state_audited':status['state'],'status_elapsed_seconds':elapsed,'events_checked':len(events),'unique_candidate_ids':len(events),'all_parents_known':True,'all_promotions_obey_frozen_rule':True,'all_champion_sources_match':True,'all_candidates_certified':True,'sampled_results_reexecuted':len(matched),'all_sampled_result_fingerprints_match':True,'sampled_evaluation_ids':sorted(matched),'holdout_read_by_audit':False,'candidate_completion_gap_max_seconds':max(gaps,default=0),'candidate_completion_gap_median_seconds':statistics.median(gaps) if gaps else 0,'sum_candidate_evaluation_wall_seconds':sum(e['elapsed_seconds'] for e in events),'cpu_to_wall_ratio':status['process_cpu_seconds']/elapsed,'last_promotion_seconds':last_accept,'plateau_seconds_at_snapshot':elapsed-last_accept,'minute_buckets':[{'minute':k,**v} for k,v in sorted(bins.items())],'audit_wall_seconds':time.perf_counter()-started,'limits':'Hashes detect accidental change, not a malicious host. This audits bounded search and local replay, not open-ended RSI or a production sandbox.'}
    write_json(run/'audit.json',result);return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='runs/main');ap.add_argument('--recheck',type=int,default=24);args=ap.parse_args()
    if not 0<=args.recheck<=200:ap.error('--recheck 必须在 0–200 之间')
    result=audit(ROOT/args.run,args.recheck)
    print(json.dumps({k:v for k,v in result.items() if k not in ('minute_buckets','sampled_evaluation_ids')},ensure_ascii=False,indent=2))
