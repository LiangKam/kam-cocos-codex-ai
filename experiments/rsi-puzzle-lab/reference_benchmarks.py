"""已知强策略对照：防止只挑一个过弱基线制造夸张改进结论。

只读固定验证集，不读取保留集；不把此结果反馈进正在运行的主实验。
所有策略使用同样的域工具与 900 节点预算。每项重复 3 次，报告实测耗时。
"""
from __future__ import annotations
import json,pathlib,statistics,time
from domain import Features
from evaluator import evaluate,assert_frozen
ROOT=pathlib.Path(__file__).parent

def main():
    assert_frozen(ROOT)
    current=json.loads((ROOT/'runs/main/status.json').read_text())['champion']
    cases=[
        ('uniform_cost',{'expression':'0','tie':'fifo'}),
        ('manhattan',{'expression':'m','tie':'deep'}),
        ('linear_conflict',{'expression':'lc','tie':'deep'}),
        ('single_pattern_database',{'expression':'p0','tie':'deep'}),
        ('expert_supplied_tools_combination',{'expression':'max(lc,p0,p1,p2)','tie':'deep'}),
        ('frozen_evolved_champion',current['config']),
    ]
    rows=json.loads((ROOT/'datasets/validation.json').read_text());t=time.perf_counter();features=Features();setup=time.perf_counter()-t
    results=[]
    for name,config in cases:
        measured=[evaluate(config,rows,features) for _ in range(3)]
        r=measured[0]
        assert all(m['details']==r['details'] for m in measured),'同一策略重复执行结果不一致'
        results.append({'name':name,'config':config,'count':r['count'],'solved':r['solved'],'invalid':r['invalid'],'mean_charged_expansions':r['mean_expanded'],'median_wall_seconds':statistics.median(m['wall_seconds'] for m in measured),'median_cpu_seconds':statistics.median(m['cpu_seconds'] for m in measured),'wall_seconds_each':[m['wall_seconds'] for m in measured],'repeat_cases_identical':True})
    data={'benchmark':'validation_only','holdout_used':False,'used_for_main_selection':False,'selected_champion_id':current['id'],'repetitions_each':3,'budget':900,'pattern_database_setup_seconds':setup,'results':results,'interpretation':'This bounded search selects from supplied tools; matching an expert combination is not inventing a new search algorithm. Expansion reductions are not wall-clock speedup claims.'}
    (ROOT/'reference-benchmarks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
