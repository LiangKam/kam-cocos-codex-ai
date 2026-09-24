"""受约束的自改进运行器：提案→编译→独立验收→继承→继续。

注意：这里是本地程序合成，不是偷偷调用外部大模型。没有 sleep；持续时间内
每次循环都在产生新候选、评估或保存证据。不可写入评估器或测试集。
"""
from __future__ import annotations
import argparse,ast,datetime,hashlib,json,math,os,pathlib,random,time,traceback
from domain import Features
from strategy import source_for,config_id,validate_expression
from evaluator import evaluate,score,assert_frozen
ROOT=pathlib.Path(__file__).resolve().parent
OPS=['replace_leaf','max_feature','convex_mix','scale_down','tie_break','crossover','prune']
FEATURES=['0','mis','m','lc','p0','p1','p2']

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def compact(r):return {k:v for k,v in r.items() if k!='details'}
def write_json(p,value):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));os.replace(tmp,p)

def bound(node):
    """结构性下界证书：只允许已知下界的 max/min、缩放和凸组合。
    不使用任何保留集答案。加权系数和不得大于 1。
    """
    if isinstance(node,ast.Expression):return bound(node.body)
    if isinstance(node,ast.Name):return 1.0
    if isinstance(node,ast.Constant):return 0.0 if node.value==0 else float('inf')
    if isinstance(node,ast.Call):return max(bound(a) for a in node.args)
    if isinstance(node,ast.BinOp):
        if isinstance(node.op,ast.Add):return bound(node.left)+bound(node.right)
        if isinstance(node.op,ast.Mult):
            if isinstance(node.left,ast.Constant):return node.left.value*bound(node.right)
            if isinstance(node.right,ast.Constant):return node.right.value*bound(node.left)
    return float('inf')

def is_certified(expr):
    try:return bound(validate_expression(expr)[0])<=1.00000001
    except (ValueError,SyntaxError,RecursionError):return False

def choose_op(rng,stats,iteration):
    """反馈驱动的改进器：保留探索，优先尝试产生收益的变异方式。"""
    untried=[o for o in OPS if stats[o].get('attempts',stats[o]['trials'])==0]
    if untried:return rng.choice(untried)
    if rng.random()<0.20:return rng.choice(OPS)
    values={o:(stats[o]['reward']-0.002*stats[o].get('duplicates',0))/max(1,stats[o].get('attempts',stats[o]['trials']))+0.5*math.sqrt(math.log(iteration+2)/max(1,stats[o].get('attempts',stats[o]['trials']))) for o in OPS}
    return max(OPS,key=lambda o:values[o]+rng.random()*0.015)

def propose(config,op,rng,archive):
    expr=config['expression'];tie=config['tie'];feature=rng.choice(FEATURES)
    if op=='replace_leaf':
        tree=ast.parse(expr,mode='eval');leaves=[n for n in ast.walk(tree) if isinstance(n,ast.Name) and n.id not in ('max','min') or isinstance(n,ast.Constant)]
        if not leaves:expr=feature
        else:
            target=rng.choice(leaves)
            class Replace(ast.NodeTransformer):
                def visit(self,node):
                    if node is target:return ast.parse(feature,mode='eval').body
                    return super().visit(node)
            expr=ast.unparse(Replace().visit(tree))
    elif op=='max_feature':expr=f'max({expr},{feature})'
    elif op=='convex_mix':
        weight=rng.choice([0.125,0.25,0.375,0.5,0.625,0.75,0.875])
        expr=f'({weight}*({expr})+{1-weight}*{feature})'
    elif op=='scale_down':expr=f'{rng.choice([0.25,0.5,0.75,1.0])}*({expr})'
    elif op=='tie_break':tie=rng.choice(['fifo','deep','shallow','mis'])
    elif op=='crossover':expr=f'max({expr},{rng.choice(archive)["config"]["expression"]})'
    elif op=='prune':
        tree=ast.parse(expr,mode='eval');nodes=[n for n in ast.walk(tree) if isinstance(n,(ast.Name,ast.BinOp,ast.Call,ast.Constant)) and not isinstance(n,ast.Name) or isinstance(n,ast.Name) and n.id not in ('max','min')]
        expr=ast.unparse(rng.choice(nodes)) if nodes else feature
    return {'expression':expr,'tie':tie}

def load_champion(out):
    """下轮实际从已验收文件加载；拒绝子代不会污染当前策略。"""
    text=(out/'champion.py').read_text();module={};exec(compile(text,'champion.py','exec'),{'__builtins__':{}},module)
    return module['CONFIG']

def run(seconds,seed,out):
    assert_frozen(ROOT)
    if out.exists() and (out/'events.jsonl').exists():raise ValueError('输出目录已有实验；禁止覆盖证据')
    out.mkdir(parents=True,exist_ok=True);(out/'champions').mkdir(exist_ok=True)
    t0=time.monotonic();cpu0=time.process_time();started=utc();controller_hash=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest();features=Features();setup=time.monotonic()-t0
    train=json.loads((ROOT/'datasets/train.json').read_text());validation=json.loads((ROOT/'datasets/validation.json').read_text())
    rng=random.Random(seed);stats={o:{'attempts':0,'trials':0,'duplicates':0,'reward':0.0,'accepts':0} for o in OPS};seen=set();archive=[];iteration=0;evals=0;rejected=0;skipped=0;history=[]
    baseline={'expression':'0','tie':'fifo'}
    baseline_train=evaluate(baseline,train,features);baseline_val=evaluate(baseline,validation,features)
    champion={'generation':0,'config':baseline,'id':config_id(baseline),'parent':None,'at_seconds':time.monotonic()-t0,'train':compact(baseline_train),'validation':compact(baseline_val),'operator':'baseline','source_sha256':hashlib.sha256(source_for(baseline).encode()).hexdigest()}
    champion_train=baseline_train;champion_val=baseline_val;archive.append(champion);seen.add(champion['id']);history.append(champion)
    (out/'champion.py').write_text(source_for(baseline));(out/'champions/g000.py').write_text(source_for(baseline));write_json(out/'champions/g000.json',champion)
    previews=[]
    # 固定展示关卡来自验证集，包含不同难度，不挑选最漂亮的个案。
    for depth in (8,14,20,24,28):
        row=next((r for r in validation if r['distance']==depth),None)
        if row:previews.append(row)
    write_json(out/'champions/g000-replays.json',evaluate(baseline,previews,features,True))
    log=open(out/'events.jsonl','w',buffering=1);log.write(json.dumps({'kind':'start','at':started,'seconds':seconds,'seed':seed,'controller_sha256':controller_hash,'baseline':champion},ensure_ascii=False)+'\n')
    print(json.dumps({'event':'baseline','validation_solved':champion_val['solved'],'count':len(validation),'seconds':time.monotonic()-t0}),flush=True)
    last_status=0;last_evaluated=0;stopped='duration_completed';archive_limit=200
    try:
        while time.monotonic()-t0<seconds:
            if (out/'STOP').exists():stopped='user_stop_file';break
            assert_frozen(ROOT);iteration+=1
            current=load_champion(out)
            op=choose_op(rng,stats,iteration)
            stats[op]['attempts']+=1
            # 部分探索从历史祖先分支；其余从本代继续。记录真实父代。
            parent=champion if rng.random()<0.60 else rng.choice(archive)
            candidate=propose(current if parent is champion else parent['config'],op,rng,archive)
            # 若邻域长时间无新候选，扩大受限语法内的探索，而非空转。
            if time.monotonic()-t0-last_evaluated>5:
                a,b,c=rng.sample(FEATURES,3);w=rng.randrange(1,1000)/1000
                candidate={'expression':f'max({w}*{a}+{1-w}*{b},{c})','tie':rng.choice(['fifo','deep','shallow','mis'])}
                op='convex_mix'
            proposal_start=time.monotonic()
            try:
                source=source_for(candidate);compile(source,'candidate.py','exec');ident=config_id(candidate)
                if not is_certified(candidate['expression']):raise ValueError('no_admissibility_certificate')
            except (ValueError,SyntaxError,RecursionError) as exc:
                skipped+=1
                if skipped<30:log.write(json.dumps({'kind':'guard_reject','iteration':iteration,'reason':str(exc)},ensure_ascii=False)+'\n')
                continue
            if ident in seen:
                skipped+=1;stats[op]['duplicates']+=1
                # 重复不重新测量、不冒充一轮新实验；策略记忆阻止重复付费。
                continue
            seen.add(ident);stats[op]['trials']+=1;evals+=1
            tr=evaluate(candidate,train,features)
            vr=None;accept=False;reason='training_not_better'
            if tr['invalid']!=0:reason='invalid_training_path'
            elif score(tr)>score(champion_train) or rng.random()<0.06:
                vr=evaluate(candidate,validation,features)
                if vr['invalid']!=0:reason='invalid_validation_path'
                elif score(vr)>score(champion_val) and score(tr)>=score(champion_train):accept=True;reason='strict_improvement'
                else:reason='no_joint_improvement'
            reward=0
            if accept:
                reward=(vr['solved']-champion_val['solved'])/len(validation)+(champion_val['total_expanded']-vr['total_expanded'])/(len(validation)*900)
                stats[op]['reward']+=max(reward,0)+0.05;stats[op]['accepts']+=1
                generation=champion['generation']+1
                champion={'generation':generation,'config':candidate,'id':ident,'parent':parent['id'],'previous_incumbent':champion['id'],'at_seconds':time.monotonic()-t0,'train':compact(tr),'validation':compact(vr),'operator':op,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'iteration':iteration,'operator_memory':json.loads(json.dumps(stats))}
                champion_train=tr;champion_val=vr;history.append(champion);archive.append(champion)
                # 同时保存可执行后继源码和逐关证据，原子替换冠军。
                tmp=out/'champion.py.tmp';tmp.write_text(source);os.replace(tmp,out/'champion.py')
                prefix=f'g{generation:03d}'
                (out/'champions'/f'{prefix}.py').write_text(source);write_json(out/'champions'/f'{prefix}.json',champion)
                write_json(out/'champions'/f'{prefix}-validation.json',vr)
                write_json(out/'champions'/f'{prefix}-replays.json',evaluate(candidate,previews,features,True))
                print(json.dumps({'event':'accepted','generation':generation,'config':candidate,'solved':vr['solved'],'mean_expanded':vr['mean_expanded'],'seconds':time.monotonic()-t0},ensure_ascii=False),flush=True)
            else:
                rejected+=1
                # 有效非冠军也可成为后续的垫脚石，避免只能进行一跳爬山。
                if tr['invalid']==0 and tr['solved']>=max(1,champion_train['solved']*0.50):
                    stone={'id':ident,'config':candidate,'parent':parent['id'],'generation':None}
                    if len(archive)<archive_limit:archive.append(stone)
                    elif rng.random()<0.3:
                        ix=rng.randrange(1,len(archive))
                        if archive[ix]['id']!=champion['id']:archive[ix]=stone
            last_evaluated=time.monotonic()-t0
            event={'kind':'candidate','iteration':iteration,'evaluation':evals,'at_seconds':time.monotonic()-t0,'id':ident,'parent':parent['id'],'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'config':candidate,'operator':op,'accepted':accept,'reason':reason,'train':{k:tr[k] for k in ('count','solved','invalid','total_expanded','wall_seconds','cpu_seconds')},'validation':{k:vr[k] for k in ('count','solved','invalid','total_expanded','wall_seconds','cpu_seconds')} if vr else None,'result_sha256':hashlib.sha256(json.dumps([tr['details'],vr['details'] if vr else None],sort_keys=True).encode()).hexdigest(),'elapsed_seconds':time.monotonic()-proposal_start}
            log.write(json.dumps(event,ensure_ascii=False,separators=(',',':'))+'\n')
            elapsed=time.monotonic()-t0
            if elapsed-last_status>=8 or accept:
                status={'state':'running','controller_sha256':controller_hash,'started_at_utc':started,'target_seconds':seconds,'elapsed_seconds':elapsed,'process_cpu_seconds':time.process_time()-cpu0,'feature_setup_seconds':setup,'iterations':iteration,'evaluated_candidates':evals,'archive_size':len(archive),'rejected_candidates':rejected,'skipped_duplicate_or_guard':skipped,'accepted_generations':len(history)-1,'champion':champion,'history':history,'operator_memory':stats,'holdout_used':False,'controller':'v3 novelty archive + attempt-aware UCB + watchdog exploration','agent_kind':'bounded program-synthesis; no external LLM calls','seed':seed}
                write_json(out/'status.json',status);last_status=elapsed
                print(json.dumps({'event':'heartbeat','seconds':round(elapsed,1),'evaluated':evals,'accepted':len(history)-1,'cpu_seconds':round(time.process_time()-cpu0,1)}),flush=True)
    except BaseException as exc:
        stopped='error';log.write(json.dumps({'kind':'error','at':utc(),'error':repr(exc),'traceback':traceback.format_exc()})+'\n');raise
    finally:
        elapsed=time.monotonic()-t0
        final={'state':stopped,'controller_sha256':controller_hash,'started_at_utc':started,'ended_at_utc':utc(),'target_seconds':seconds,'elapsed_seconds':elapsed,'process_cpu_seconds':time.process_time()-cpu0,'feature_setup_seconds':setup,'iterations':iteration,'evaluated_candidates':evals,'archive_size':len(archive),'rejected_candidates':rejected,'skipped_duplicate_or_guard':skipped,'accepted_generations':len(history)-1,'champion':champion,'history':history,'operator_memory':stats,'holdout_used':False,'seed':seed,'agent_kind':'bounded program-synthesis; no external LLM calls'}
        write_json(out/'status.json',final);log.write(json.dumps({'kind':'end',**{k:v for k,v in final.items() if k not in ('champion','history','operator_memory')}},ensure_ascii=False)+'\n');log.close()
        print(json.dumps({'event':'finished','seconds':elapsed,'evaluated':evals,'accepted':len(history)-1}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=1860);ap.add_argument('--seed',type=int,default=240926);ap.add_argument('--out',default='runs/main');args=ap.parse_args()
    if not 1<=args.seconds<=7200:ap.error('--seconds 必须在 1–7200 秒')
    run(args.seconds,args.seed,ROOT/args.out)
