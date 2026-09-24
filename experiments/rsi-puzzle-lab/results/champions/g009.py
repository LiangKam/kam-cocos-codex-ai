# 自动生成的策略；评估规则不在此文件中。
# 下一代从已验收的本代 CONFIG 继续变异，不从零重置。
CONFIG = {'expression': 'max(max(max(max(0.875 * max(p2, lc) + 0.125 * p0, p1), p2), p1), p0)', 'tie': 'mis'}

def heuristic(m=0, mis=0, lc=0, p0=0, p1=0, p2=0):
    """估计剩余步数；独立最优路径验证器负责拦截高估错误。"""
    return max(max(max(max(0.875 * max(p2, lc) + 0.125 * p0, p1), p2), p1), p0)
