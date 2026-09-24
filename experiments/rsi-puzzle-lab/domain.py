"""八数码领域：候选只能调用这些固定工具，不能读取评估答案。"""
from __future__ import annotations
from collections import deque
from functools import lru_cache
import itertools

GOAL = (1,2,3,4,5,6,7,8,0)
NEIGHBORS = tuple(tuple(j for j in range(9) if abs(i//3-j//3)+abs(i%3-j%3)==1) for i in range(9))
DIST = tuple(tuple(0 if t==0 else abs(i//3-(t-1)//3)+abs(i%3-(t-1)%3) for i in range(9)) for t in range(9))

def valid_board(board):
    return isinstance(board, (list,tuple)) and len(board)==9 and all(type(x) is int for x in board) and sorted(board)==list(range(9))

def solvable(board):
    a=[x for x in board if x]
    return sum(a[i]>a[j] for i in range(8) for j in range(i+1,8))%2==0

def adjacent(board):
    z=board.index(0)
    for j in NEIGHBORS[z]:
        b=list(board);b[z],b[j]=b[j],b[z]
        yield tuple(b)

def make_oracle():
    """独立反向 BFS，穷举真实最优距离。仅构建数据和验收使用。"""
    distance={GOAL:0}; q=deque([GOAL])
    while q:
        b=q.popleft();n=distance[b]+1
        for c in adjacent(b):
            if c not in distance:distance[c]=n;q.append(c)
    return distance

def pattern_database(tiles):
    """代价分割的 0-1 BFS 模式库。只记录部分数字位置，不记录完整棋盘答案。"""
    tiles=tuple(tiles);start=(8,)+tuple(t-1 for t in tiles)
    d={start:0};q=deque([start])
    while q:
        p=q.popleft();base=d[p];z=p[0]
        for j in NEIGHBORS[z]:
            n=list(p);n[0]=j;cost=0
            if j in p[1:]:n[p.index(j)]=z;cost=1
            n=tuple(n);value=base+cost
            if value<d.get(n,10**9):
                d[n]=value
                if cost:q.append(n)
                else:q.appendleft(n)
    return d

PARTITIONS=((1,2,3,4),(1,3,5,7),(1,2,4,5))
class Features:
    """每个评估工作进程只生成一次模式库；构建耗时另计。"""
    def __init__(self):
        self.tables=[]
        for a in PARTITIONS:
            b=tuple(t for t in range(1,9) if t not in a)
            self.tables.append((a,b,pattern_database(a),pattern_database(b)))
    def get(self,board,names):
        out={}; pos=None
        if 'm' in names or 'lc' in names:
            m=sum(DIST[t][i] for i,t in enumerate(board));out['m']=m
        if 'mis' in names:out['mis']=sum(t!=0 and t!=GOAL[i] for i,t in enumerate(board))
        if 'lc' in names:
            # 同一数字不重复计冲突：取冲突图的最大匹配，避免高估导致非最优路径。
            edges=[]
            for i,t in enumerate(board):
                if not t:continue
                for j in range(i+1,9):
                    u=board[j]
                    if not u:continue
                    row=i//3==j//3==(t-1)//3==(u-1)//3 and t>u
                    col=i%3==j%3==(t-1)%3==(u-1)%3 and t>u
                    if row or col:edges.append((1<<(t-1),1<<(u-1)))
            def matching(k,mask):
                if k==len(edges):return 0
                a,b=edges[k];best=matching(k+1,mask)
                if not mask&(a|b):best=max(best,1+matching(k+1,mask|a|b))
                return best
            out['lc']=m+2*matching(0,0)
        for ix,key in enumerate(('p0','p1','p2')):
            if key in names:
                if pos is None:
                    pos=[0]*9
                    for i,t in enumerate(board):pos[t]=i
                a,b,da,db=self.tables[ix]
                out[key]=da[(pos[0],)+tuple(pos[t] for t in a)]+db[(pos[0],)+tuple(pos[t] for t in b)]
        return out
