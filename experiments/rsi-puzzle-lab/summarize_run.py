"""从已结束的运行与一次性保留集审计生成最终摘要，拒绝提前生成完成声明。"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,platform
from evaluator import assert_frozen
ROOT=pathlib.Path(__file__).resolve().parent

def summary(run:pathlib.Path):
    assert_frozen(ROOT);status=json.loads((run/'status.json').read_text())
    if status['state']!='duration_completed':raise RuntimeError('实验没有完成，不能生成完成报告')
    holdout=json.loads((run/'holdout.json').read_text())
    if not holdout['selection_already_frozen'] or holdout['used_to_select']:raise RuntimeError('保留集选择约束不满足')
    audit=json.loads((run/'audit.json').read_text())
    if audit['events_checked']!=status['evaluated_candidates']:raise RuntimeError('审计不是最终完整日志')
    def metrics(r):return {k:r[k] for k in ('count','solved','invalid','mean_expanded','total_expanded')}
    history=[]
    for h,v in zip(status['history'],holdout['versions']):
        assert h['generation']==v['generation'] and h['id']==v['id']
        history.append({'generation':h['generation'],'at_seconds':h['at_seconds'],'id':h['id'],'source_sha256':h['source_sha256'],'parent':h['parent'],'config':h['config'],'operator':h['operator'],'train':metrics(h['train']),'validation':metrics(h['validation']),'holdout':metrics(v['metrics'])})
    final={k:status[k] for k in ('state','started_at_utc','ended_at_utc','target_seconds','elapsed_seconds','process_cpu_seconds','controller_sha256','feature_setup_seconds','evaluated_candidates','accepted_generations','rejected_candidates','skipped_duplicate_or_guard','seed')}
    final.update(experiment='RSI Puzzle Lab / bounded self-improvement',runtime=platform.python_version(),external_llm_calls_inside_evolution_loop=0,baseline=history[0],champion=history[-1],history=history,holdout_used_to_select=False,audit={k:audit[k] for k in ('events_checked','all_parents_known','all_promotions_obey_frozen_rule','sampled_results_reexecuted','all_sampled_result_fingerprints_match','candidate_completion_gap_max_seconds','last_promotion_seconds','plateau_seconds_at_snapshot')},files_sha256={'events.jsonl':hashlib.sha256((run/'events.jsonl').read_bytes()).hexdigest(),'holdout.json':hashlib.sha256((run/'holdout.json').read_bytes()).hexdigest(),'frozen.json':hashlib.sha256((ROOT/'frozen.json').read_bytes()).hexdigest()})
    (run/'summary.json').write_text(json.dumps(final,ensure_ascii=False,indent=2));return final
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='runs/main');args=ap.parse_args();d=summary(ROOT/args.run)
    print(json.dumps({k:v for k,v in d.items() if k not in ('history','baseline','champion')},ensure_ascii=False,indent=2))
