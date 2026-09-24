"""辅助稳定性检查：预先指定三种子，各跑 90 秒；仅用训练/验证集。"""
import subprocess,sys,pathlib,json,datetime
ROOT=pathlib.Path(__file__).resolve().parent
seeds=[7,42,20260924];results=[]
for seed in seeds:
    name=f'repeat-seed-{seed}';out=ROOT/'runs'/name;out.mkdir(parents=True,exist_ok=True)
    with (out/'console.log').open('w') as log:
        subprocess.run([sys.executable,'-u','evolve.py','--seconds','90','--seed',str(seed),'--out','runs/'+name],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    s=json.loads((out/'status.json').read_text())
    results.append({'seed':seed,'elapsed_seconds':s['elapsed_seconds'],'evaluated_candidates':s['evaluated_candidates'],'accepted_generations':s['accepted_generations'],'validation':s['champion']['validation'],'config':s['champion']['config'],'holdout_used':False})
    (ROOT/'repeat-seeds-results.json').write_text(json.dumps({'seeds_preselected':[7,42,20260924],'seconds_each':90,'selection_of_main_unchanged':True,'results':results},ensure_ascii=False,indent=2))
    print(json.dumps({'seed':seed,'solved':s['champion']['validation']['solved'],'mean_expanded':s['champion']['validation']['mean_expanded']},ensure_ascii=False),flush=True)
