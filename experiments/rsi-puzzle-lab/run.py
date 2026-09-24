"""单命令复现。仅标准库，默认连续运行 31 分钟。

python run.py --seconds 1860 --name replay-01
生成 runs/replay-01 和 report-replay-01.html；不覆盖已有证据。
"""
from __future__ import annotations
import argparse,pathlib,re,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser(description='复现 RSI Puzzle Lab 受限自改进实验')
    ap.add_argument('--seconds',type=float,default=1860,help='有效实验预算秒数，默认 31 分钟')
    ap.add_argument('--name',default='replay-01',help='只含英文字母、数字、下划线或短横线的运行名称')
    ap.add_argument('--seed',type=int,default=240927)
    args=ap.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}',args.name):ap.error('不安全的运行名称')
    if not 1<=args.seconds<=7200:ap.error('--seconds 必须在 1–7200 之间')
    if (ROOT/'runs'/args.name).exists():ap.error('该运行名称已经存在；请换名，避免覆盖证据')
    def execute(*command):subprocess.run([sys.executable,*command],cwd=ROOT,check=True)
    if not (ROOT/'frozen.json').exists():execute('prepare.py')
    execute('-m','unittest','tests','-v')
    execute('evolve.py','--seconds',str(args.seconds),'--seed',str(args.seed),'--out','runs/'+args.name)
    execute('holdout.py','--run','runs/'+args.name)
    execute('build_report.py','--run','runs/'+args.name,'--out','report-'+args.name+'.html')
    print('完成：',ROOT/('report-'+args.name+'.html'))
if __name__=='__main__':main()
