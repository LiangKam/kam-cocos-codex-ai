"""一次性产生分层关卡与冻结哈希。不得在实验中重抽。"""
import json,random,pathlib,time,hashlib
from domain import make_oracle
from evaluator import frozen_hashes
root=pathlib.Path(__file__).parent
if (root/'frozen.json').exists():raise SystemExit('已有冻结数据；拒绝覆盖')
t=time.perf_counter();oracle=make_oracle();rng=random.Random(20260924);buckets={}
for board,d in oracle.items():
    if d>=6:buckets.setdefault(d,[]).append(board)
for arr in buckets.values():rng.shuffle(arr)
# 保留极难关卡但避免稀有的 31 步关卡被重复分配；所有 split 全局去重。
used=set();splits={};depths=list(range(6,32))
for name,count in [('train',128),('validation',256),('holdout',512)]:
    rows=[]
    for i in range(count):
        d=depths[i%len(depths)]
        while not buckets.get(d):d=depths[rng.randrange(len(depths))]
        board=buckets[d].pop();assert board not in used;used.add(board)
        rows.append({'id':f'{name}-{i:04d}','board':list(board),'distance':d})
    splits[name]=rows
(root/'datasets').mkdir(exist_ok=True)
for name,rows in splits.items():(root/'datasets'/f'{name}.json').write_text(json.dumps(rows,separators=(',',':')))
manifest={'seed':20260924,'oracle_states':len(oracle),'oracle_max_distance':max(oracle.values()),'split_counts':{k:len(v) for k,v in splits.items()},'budget':900,'generation_seconds':time.perf_counter()-t,'disjoint':True}
(root/'datasets'/'manifest.json').write_text(json.dumps(manifest,indent=2))
(root/'frozen.json').write_text(json.dumps(frozen_hashes(root),indent=2))
print(json.dumps(manifest,indent=2))
