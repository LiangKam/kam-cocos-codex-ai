"""受限源码合成与 A* 执行器；不接受任意 Python 代码执行。"""
from __future__ import annotations
import ast,heapq,hashlib,json,itertools
from domain import GOAL,NEIGHBORS,valid_board,solvable
FEATURE_NAMES={'m','mis','lc','p0','p1','p2'}
ALLOWED=(ast.Expression,ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.Add,ast.Mult,ast.Call)

def validate_expression(expression):
    if not isinstance(expression,str) or len(expression)>240:raise ValueError('表达式过长或类型错误')
    tree=ast.parse(expression,mode='eval');nodes=list(ast.walk(tree))
    if len(nodes)>65:raise ValueError('表达式节点过多')
    for n in nodes:
        if not isinstance(n,ALLOWED):raise ValueError(f'禁止语法 {type(n).__name__}')
        if isinstance(n,ast.Name) and n.id not in FEATURE_NAMES|{'max','min'}:raise ValueError('非法变量')
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in {'max','min'} or len(n.args)<2 or len(n.args)>6 or n.keywords):raise ValueError('非法函数')
        if isinstance(n,ast.Constant) and (type(n.value) not in (int,float) or not 0<=n.value<=3):raise ValueError('非法常量')
    return tree,{n.id for n in nodes if isinstance(n,ast.Name) and n.id in FEATURE_NAMES}

def source_for(config):
    """将当前策略生成为可阅读、可编译、可继承的 Python 模块。"""
    expr=config['expression'];validate_expression(expr)
    if config['tie'] not in ('fifo','deep','shallow','mis'):raise ValueError('非法 tie')
    return ('# 自动生成的策略；评估规则不在此文件中。\n'
            '# 下一代从已验收的本代 CONFIG 继续变异，不从零重置。\n'
            'CONFIG = '+repr(config)+'\n\n'
            'def heuristic(m=0, mis=0, lc=0, p0=0, p1=0, p2=0):\n'
            '    """估计剩余步数；独立最优路径验证器负责拦截高估错误。"""\n'
            '    return '+expr+'\n')

def make_heuristic(config,features):
    tree,names=validate_expression(config['expression'])
    code=compile(tree,'<safe-heuristic>','eval')
    if config['tie']=='mis':names.add('mis')
    def fn(board):
        values=features.get(board,names)
        return eval(code,{'__builtins__':{},'max':max,'min':min},values),values.get('mis',0)
    return fn

def solve(board,config,features,budget=900,trace=False):
    """固定预算内 A*，重开更优节点；输出路径由另一个模块重新验证。"""
    if not valid_board(board):raise ValueError('棋盘须为 0–8 的排列')
    if type(budget) is not int or budget<0:raise ValueError('搜索预算必须非负整数')
    board=tuple(board)
    if not solvable(board):return {'status':'unsolvable','path':[],'expanded':0}
    if board==GOAL:return {'status':'solved','path':[board],'expanded':0}
    heuristic=make_heuristic(config,features);counter=itertools.count();h,mis=heuristic(board)
    heap=[(h,0,next(counter),0,board)];best={board:0};parent={};expanded=0;visited=[]
    while heap:
        _,_,_,g,b=heapq.heappop(heap)
        if best.get(b)!=g:continue
        if b==GOAL:
            path=[b]
            while path[-1]!=board:path.append(parent[path[-1]])
            path.reverse()
            return {'status':'solved','path':path,'expanded':expanded,'trace':visited}
        if expanded>=budget:break
        expanded+=1
        if trace and len(visited)<100:visited.append(b)
        z=b.index(0)
        for j in NEIGHBORS[z]:
            nb=list(b);nb[z],nb[j]=nb[j],nb[z];nb=tuple(nb);ng=g+1
            if ng>=best.get(nb,10**9):continue
            best[nb]=ng;parent[nb]=b;nh,nmis=heuristic(nb)
            tie=-ng if config['tie']=='deep' else ng if config['tie']=='shallow' else nmis if config['tie']=='mis' else 0
            heapq.heappush(heap,(ng+nh,tie,next(counter),ng,nb))
    return {'status':'budget','path':[],'expanded':expanded,'trace':visited}

def config_id(config):
    return hashlib.sha256(source_for(config).encode()).hexdigest()[:16]
