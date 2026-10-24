import unittest,itertools,math
from core import *
from integer_audit import integer_count_tail,weights
from simulate import Sampler

class ExactTests(unittest.TestCase):
    def test_binomial_against_rational_enumeration(self):
        for m in range(1,9):
            for k in range(m+1):
                w=[math.comb(m,j) for j in range(m+1)]
                expected=sum(x for x in w if x<=w[k])/2**m
                self.assertAlmostEqual(exact_normal(k,m,.5)[0],expected,places=12)

    def test_poisson_binomial_bruteforce(self):
        q=[.1,.2,.5,.8];expected=np.zeros(5)
        for mask in itertools.product([0,1],repeat=4):
            expected[sum(mask)]+=np.prod([p if x else 1-p for p,x in zip(q,mask)])
        np.testing.assert_allclose(pb_pmf(q),expected,atol=1e-14)

    def test_integer_poisson_binomial(self):
        num,den=integer_count_tail([(1,4),(2,3),(1,2)],2)
        self.assertEqual(Fraction(num,den),Fraction(11,24))

    def test_maximum_with_flats_bruteforce(self):
        n=np.array([3,4]);m=np.array([3,3]);r=Fraction(2,3);count=0
        for bits in itertools.product([0,1],repeat=6):
            u=[sum(bits[:3]),sum(bits[3:])]
            count+=max(Fraction(max(k,3-k),nn) for k,nn in zip(u,n))>=r
        with np.errstate(divide='ignore'):
            self.assertAlmostEqual(max_tail(n,m,.5,r),count/64)

    def test_conditional_maximum_enumeration(self):
        n=np.array([3,4]);m=np.array([3,4]);up=np.array([2,1]);r=Fraction(3,4);yes=alln=0
        for bits in itertools.product([0,1],repeat=7):
            if sum(bits)!=3:continue
            alln+=1;u=[sum(bits[:3]),sum(bits[3:])]
            yes+=max(Fraction(max(k,mm-k),nn) for k,mm,nn in zip(u,m,n))>=r
        self.assertAlmostEqual(conditioned_max_tail(n,m,up,r,3/7),yes/alln)

    def test_same_direction_joint_not_rechoosing_validation(self):
        # One train/validation pair of three observations each, both >=2/3.
        count=0
        for bits in itertools.product([0,1],repeat=6):
            a=sum(bits[:3]);b=sum(bits[3:]);count+=(a>=2 and b>=2) or (a<=1 and b<=1)
        self.assertEqual(count/64,.5)
        self.assertAlmostEqual(2*binom.sf(1,3,.5)**2,.5)

    def test_threshold_discreteness(self):
        self.assertEqual(int(critical(32,60)),20)
        self.assertEqual(int(critical(23,60)),14)
        self.assertEqual(int(critical(33,55)),19)

    def test_expected_sd_formula(self):
        n=np.array([2,3]);p=.4;expected=0
        for a in range(3):
            for b in range(4):expected+=np.var([a/2,b/3],ddof=1)*binom.pmf(a,2,p)*binom.pmf(b,3,p)
        self.assertAlmostEqual(expected,np.mean(p*(1-p)/n))

    def test_normal_cc_correct_tail_boundary(self):
        event=np.arange(33)>=20
        self.assertAlmostEqual(normal_event(32,.5,event),norm.sf((19.5-16)/math.sqrt(8)))

    def test_global_phase_only_relabels(self):
        u=np.arange(60)%11+20;n=np.full(60,55)
        for shift in [1,7,23]:
            self.assertEqual(int((u*100>=55*n).sum()),int((np.roll(u,shift)*100>=55*n).sum()))

class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows,_=data()

    def test_disjoint_stages_reconcile(self):
        for basis in P['bases']:
            a=prepared(self.rows,basis)
            np.testing.assert_array_equal(a['n'][0],a['n'][1]+a['n'][2])
            np.testing.assert_array_equal(a['m'][0],a['m'][1]+a['m'][2])
            np.testing.assert_array_equal(a['up'][0],a['up'][1]+a['up'][2])

    def test_all_structural_mappings_valid_and_reproducible(self):
        a=prepared(self.rows,'oc')
        for method in P['structured_nulls']:
            s=Sampler(a,method,123);maps=s.mapping(32);s.audit(maps)
            np.testing.assert_array_equal(maps,Sampler(a,method,123).mapping(32))
            assert np.all(s.counts(maps).sum(2)==a['up'].sum(1))

    def test_data_boundaries_and_previous_close(self):
        by={r['date']:r for r in self.rows}
        self.assertEqual(by['2026-10-24']['oc_reason'],'unclosed')
        for d in ['2018-02-09','2020-02-20','2020-12-22']:
            self.assertEqual(by[d]['cc_reason'],'invalid_previous_close')
            self.assertFalse(by[d]['oc_reason'])

    def test_train_reselection_uses_no_validation(self):
        a=prepared(self.rows,'oc');one=stats(a['up'],dict(a));changed=a['up'].copy();changed[2]=0;changed[0]=changed[1]
        two=stats(changed,dict(a))
        for h in TH:np.testing.assert_array_equal(one[f'train_selected{h}'],two[f'train_selected{h}'])

    def test_tied_train_direction_not_a_fake_zero_validation_rate(self):
        a=prepared(self.rows,'oc');g=int(np.flatnonzero(a['m'][1]%2==0)[0]);u=a['up'].copy();u[1,g]=a['m'][1,g]//2
        u[2,g]=0;u[0]=u[1]+u[2];one=stats(u,dict(a))['corr_frozen_pearson']
        u[2,g]=a['m'][2,g];u[0]=u[1]+u[2];two=stats(u,dict(a))['corr_frozen_pearson']
        np.testing.assert_allclose(one,two,atol=1e-14)

if __name__=='__main__':unittest.main(verbosity=2)
