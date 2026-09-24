"""固定验收器：不接受候选自报的正确率，逐步检查实际路径。"""
from __future__ import annotations
import time,json,hashlib,pathlib
from domain import GOAL,valid_board
from strategy import solve
BUDGET=900

def verify(board,result,distance):
    path=result.get('path',[])
    if result.get('status')!='solved':return (not path),'not_solved'
    if not path or tuple(path[0])!=tuple(board) or tuple(path[-1])!=GOAL:return False,'wrong_endpoints'
    for a,b in zip(path,path[1:]):
        if not valid_board(a) or not valid_board(b):return False,'malformed_state'
        z=a.index(0);zz=b.index(0)
        if abs(z//3-zz//3)+abs(z%3-zz%3)!=1:return False,'illegal_step'
        expected=list(a);expected[z],expected[zz]=expected[zz],expected[z]
        if expected!=list(b):return False,'teleport'
    if len(path)-1!=distance:return False,'nonoptimal'
    return True,'ok'

def evaluate(config,rows,features,keep_paths=False):
    t=time.perf_counter();cpu=time.process_time();solved=invalid=nodes=0;details=[];by_depth={}
    for row in rows:
        result=solve(row['board'],config,features,budget=BUDGET,trace=keep_paths)
        valid,reason=verify(row['board'],result,row['distance'])
        win=valid and result['status']=='solved';solved+=int(win);invalid+=int(not valid)
        charged=result['expanded'] if win else BUDGET;nodes+=charged
        depth=str(row['distance']);group=by_depth.setdefault(depth,{'count':0,'solved':0,'nodes':0});group['count']+=1;group['solved']+=int(win);group['nodes']+=charged
        d={'id':row['id'],'distance':row['distance'],'status':result['status'],'valid':valid,'reason':reason,'expanded':result['expanded'],'charged':charged,'steps':len(result['path'])-1 if result['path'] else None}
        if keep_paths:d.update(board=row['board'],path=result['path'],trace=result.get('trace',[]))
        details.append(d)
    return {'count':len(rows),'solved':solved,'invalid':invalid,'mean_expanded':nodes/len(rows),'total_expanded':nodes,'wall_seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-cpu,'by_depth':by_depth,'details':details}

def score(result):return (-result['invalid'],result['solved'],-result['total_expanded'])

def frozen_hashes(root):
    files=['domain.py','strategy.py','evaluator.py','datasets/train.json','datasets/validation.json','datasets/holdout.json','datasets/manifest.json']
    return {f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files}

def assert_frozen(root):
    expected=json.loads((root/'frozen.json').read_text())
    current=frozen_hashes(root)
    if expected!=current:raise RuntimeError('冻结文件被改动；拒绝继续评分')
