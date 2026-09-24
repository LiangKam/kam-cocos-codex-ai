"""中文验收测试：领域、最优性、预算、非法代码、谱系与固定数据。"""
from __future__ import annotations
import unittest,json,pathlib,random,ast,hashlib
from domain import GOAL,valid_board,solvable,adjacent,make_oracle,Features
from strategy import solve,source_for,validate_expression,config_id
from evaluator import verify,evaluate,assert_frozen,BUDGET,score
from evolve import is_certified,propose,OPS,choose_op
ROOT=pathlib.Path(__file__).parent

class DomainTests(unittest.TestCase):
    def test_goal_is_valid(self):self.assertTrue(valid_board(GOAL))
    def test_wrong_size(self):self.assertFalse(valid_board(list(range(8))))
    def test_bool_rejected(self):self.assertFalse(valid_board([False,1,2,3,4,5,6,7,8]))
    def test_duplicate_rejected(self):self.assertFalse(valid_board([1]*9))
    def test_float_rejected(self):self.assertFalse(valid_board([0.0,1,2,3,4,5,6,7,8]))
    def test_solvable(self):self.assertTrue(solvable(GOAL))
    def test_unsolvable(self):self.assertFalse(solvable((2,1,3,4,5,6,7,8,0)))
    def test_neighbor_counts(self):
        self.assertEqual(len(list(adjacent(GOAL))),2)
        self.assertEqual(len(list(adjacent((1,2,3,4,0,5,6,7,8)))),4)
    def test_move_reversible(self):
        for nxt in adjacent(GOAL):self.assertIn(GOAL,list(adjacent(nxt)))

class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.features=Features();cls.oracle=make_oracle()
    def test_oracle_size(self):self.assertEqual(len(self.oracle),181440)
    def test_oracle_diameter(self):self.assertEqual(max(self.oracle.values()),31)
    def test_goal_zero_budget(self):
        r=solve(GOAL,{'expression':'0','tie':'fifo'},self.features,0)
        self.assertEqual(r['status'],'solved');self.assertEqual(r['expanded'],0)
    def test_zero_budget_not_goal(self):
        r=solve((1,2,3,4,5,6,7,0,8),{'expression':'m','tie':'deep'},self.features,0)
        self.assertEqual(r['status'],'budget');self.assertEqual(r['expanded'],0)
    def test_one_step_budget(self):
        r=solve((1,2,3,4,5,6,7,0,8),{'expression':'m','tie':'deep'},self.features,1)
        self.assertEqual(len(r['path'])-1,1)
    def test_negative_budget(self):
        with self.assertRaises(ValueError):solve(GOAL,{'expression':'m','tie':'deep'},self.features,-1)
    def test_unsolvable_without_search(self):
        r=solve((2,1,3,4,5,6,7,8,0),{'expression':'m','tie':'deep'},self.features)
        self.assertEqual(r['status'],'unsolvable');self.assertEqual(r['expanded'],0)
    def test_invalid_board(self):
        with self.assertRaises(ValueError):solve((1,)*9,{'expression':'m','tie':'deep'},self.features)
    def test_budget_cap(self):
        r=solve((8,6,7,2,5,4,3,0,1),{'expression':'0','tie':'fifo'},self.features,17)
        self.assertLessEqual(r['expanded'],17)
    def test_features_goal_zero(self):
        self.assertTrue(all(x==0 for x in self.features.get(GOAL,{'m','mis','lc','p0','p1','p2'}).values()))
    def test_pattern_table_cardinality(self):
        for a,b,da,db in self.features.tables:self.assertEqual(len(da),15120);self.assertEqual(len(db),15120)
    def test_sample_lower_bounds(self):
        # 与正式评估 split 无关的工具性质测试；不会读取保留集关卡。
        boards=random.Random(811).sample(list(self.oracle),300)
        for board in boards:
            for name,value in self.features.get(board,{'m','mis','lc','p0','p1','p2'}).items():
                self.assertLessEqual(value,self.oracle[board],(name,board,value))
    def test_random_optimality_all_ties(self):
        boards=random.Random(29).sample(list(self.oracle),16)
        for tie in ('fifo','deep','shallow','mis'):
            config={'expression':'max(p0,p1,p2)','tie':tie}
            for board in boards:
                r=solve(board,config,self.features,900)
                self.assertTrue(verify(board,r,self.oracle[board])[0])
                if r['status']=='solved':self.assertEqual(len(r['path'])-1,self.oracle[board])
    def test_determinism(self):
        board=(8,6,7,2,5,4,3,0,1);cfg={'expression':'max(p0,p1)','tie':'deep'}
        self.assertEqual(solve(board,cfg,self.features),solve(board,cfg,self.features))
    def test_generated_source_compiles(self):
        config={'expression':'max(0.5*m+0.5*lc,p0)','tie':'deep'}
        compile(source_for(config),'agent.py','exec')
        self.assertEqual(config_id(config),config_id(dict(config)))

class SecurityTests(unittest.TestCase):
    def test_import_blocked(self):
        with self.assertRaises(ValueError):validate_expression("__import__('os')")
    def test_attribute_blocked(self):
        with self.assertRaises(ValueError):validate_expression('m.__class__')
    def test_comprehension_blocked(self):
        with self.assertRaises(ValueError):validate_expression('[x for x in m]')
    def test_file_access_blocked(self):
        with self.assertRaises(ValueError):validate_expression("open('frozen.json')")
    def test_exponential_blocked(self):
        with self.assertRaises(ValueError):validate_expression('m**m')
    def test_keyword_call_blocked(self):
        with self.assertRaises(ValueError):validate_expression('max(m,key=p0)')
    def test_unknown_name_blocked(self):
        with self.assertRaises(ValueError):validate_expression('oracle')
    def test_negative_constant_blocked(self):
        with self.assertRaises(ValueError):validate_expression('-1')
    def test_large_constant_blocked(self):
        with self.assertRaises(ValueError):validate_expression('100*m')
    def test_string_constant_blocked(self):
        with self.assertRaises(ValueError):validate_expression("'abc'")
    def test_admissible_certificate(self):
        for e in ('0','m','max(lc,p0,p1)','0.25*m+0.75*p0','min(p0,p1)'):self.assertTrue(is_certified(e))
    def test_overestimate_certificate(self):
        for e in ('2*m','m+p0','1','1.5*lc','m*lc'):self.assertFalse(is_certified(e))
    def test_oversize_expression(self):
        with self.assertRaises(ValueError):validate_expression('m+'*150+'m')

class EvaluationTests(unittest.TestCase):
    def test_valid_solution(self):
        start=(1,2,3,4,5,6,7,0,8)
        self.assertEqual(verify(start,{'status':'solved','path':[start,GOAL]},1),(True,'ok'))
    def test_teleport_blocked(self):
        start=(8,6,7,2,5,4,3,0,1)
        self.assertFalse(verify(start,{'status':'solved','path':[start,GOAL]},1)[0])
    def test_wrong_endpoints(self):self.assertFalse(verify(GOAL,{'status':'solved','path':[]},0)[0])
    def test_nonoptimal_blocked(self):
        neighbor=next(adjacent(GOAL));r={'status':'solved','path':[GOAL,neighbor,GOAL]}
        self.assertEqual(verify(GOAL,r,0),(False,'nonoptimal'))
    def test_failure_cannot_claim_path(self):self.assertFalse(verify(GOAL,{'status':'budget','path':[GOAL]},0)[0])
    def test_failure_no_path_allowed(self):self.assertTrue(verify(GOAL,{'status':'budget','path':[]},0)[0])
    def test_score_priority(self):
        def r(s,n,i=0):return {'solved':s,'total_expanded':n,'invalid':i}
        self.assertGreater(score(r(2,1000)),score(r(1,1)))
        self.assertGreater(score(r(2,100)),score(r(2,200)))
        self.assertGreater(score(r(1,100)),score(r(10,1,1)))
    def test_fixed_budget(self):self.assertEqual(BUDGET,900)
    def test_frozen_files(self):assert_frozen(ROOT)
    def test_split_manifest_counts(self):
        m=json.loads((ROOT/'datasets/manifest.json').read_text())
        self.assertEqual(m['split_counts'],{'train':128,'validation':256,'holdout':512})
    def test_train_validation_disjoint(self):
        # 此处不打开保留集，保持最终审计前盲测。
        train=json.loads((ROOT/'datasets/train.json').read_text());val=json.loads((ROOT/'datasets/validation.json').read_text())
        self.assertFalse({tuple(r['board']) for r in train}&{tuple(r['board']) for r in val})

class EvolutionTests(unittest.TestCase):
    def test_proposer_determinism(self):
        cfg={'expression':'m','tie':'fifo'};archive=[{'config':cfg}]
        for op in OPS:self.assertEqual(propose(cfg,op,random.Random(4),archive),propose(cfg,op,random.Random(4),archive))
    def test_parent_not_mutated(self):
        cfg={'expression':'m','tie':'fifo'};expected=dict(cfg)
        for op in OPS:propose(cfg,op,random.Random(5),[{'config':cfg}]);self.assertEqual(cfg,expected)
    def test_explore_untried(self):
        stats={o:{'trials':1,'reward':0,'accepts':0} for o in OPS};stats['prune']['trials']=0
        self.assertEqual(choose_op(random.Random(1),stats,1),'prune')
    def test_exhausted_operator_does_not_starve_others(self):
        # 此回归测试对应实际出现的控制器 v1 空转故障。
        stats={o:{'attempts':3,'trials':2,'duplicates':1,'reward':0,'accepts':0} for o in OPS}
        stats['prune']={'attempts':500,'trials':0,'duplicates':500,'reward':0,'accepts':0}
        choices=[choose_op(random.Random(i),stats,520) for i in range(30)]
        self.assertTrue(any(o!='prune' for o in choices))
        self.assertLess(choices.count('prune'),15)
    def test_smoke_lineage(self):
        path=ROOT/'runs/smoke/status.json'
        if not path.exists():self.skipTest('没有附带 smoke 结果')
        status=json.loads(path.read_text());ids=set()
        for g in status['history']:
            if g['parent']:self.assertIn(g['parent'],ids)
            self.assertEqual(g['id'],config_id(g['config']));ids.add(g['id'])

if __name__=='__main__':unittest.main(verbosity=2)
