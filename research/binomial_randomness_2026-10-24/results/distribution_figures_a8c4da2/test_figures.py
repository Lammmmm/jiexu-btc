"""Data/finite-law/graphic export checks for this visualization only."""
import unittest,json,subprocess,hashlib,math,itertools
from pathlib import Path
from PIL import Image
import numpy as np
from plot_distributions import ROOT,REPO,BASE,discrete,discrete_interval,moments


def read(name):return json.loads((ROOT/(name+'.json')).read_text('utf-8'))


class FigureTests(unittest.TestCase):
    def test_exact_source_bytes_from_required_commit(self):
        m=read('source_manifest');self.assertEqual(m['base_commit'],BASE)
        for file,meta in m['source_files'].items():
            b=subprocess.check_output(['git','show',f'{BASE}:{file}'],cwd=REPO)
            self.assertEqual(hashlib.sha256(b).hexdigest(),meta['sha256'])

    def test_raw_and_folded_laws_bruteforce(self):
        for mode in ['up','dominant']:
            v,p=discrete(5,4,.5,mode)
            expected={}
            for bits in itertools.product([0,1],repeat=4):
                k=sum(bits);rate=(k if mode=='up' else max(k,4-k))/5
                expected[rate]=expected.get(rate,0)+1/16
            self.assertEqual(list(v),sorted(expected))
            np.testing.assert_allclose(p,[expected[x] for x in v],atol=1e-14)

    def test_histograms_have_sixty_observed_and_expected_groups(self):
        r=read('histogram_frequency_data')
        for b in ['oc','cc']:
            for mode in ['up','dominant']:
                for null in ['iid50','iid_actual']:
                    rr=[x for x in r if (x['basis'],x['mode'],x['null'])==(b,mode,null)]
                    self.assertEqual(sum(x['observed_count'] for x in rr),60)
                    self.assertAlmostEqual(sum(x['expected_count'] for x in rr),60,places=10)
                    self.assertEqual(len(rr),10)

    def test_unique_groups_and_exact_order(self):
        r=read('group_intervals_and_ranks')
        for b in ['oc','cc']:
            for mode in ['up','dominant']:
                rr=[x for x in r if x['basis']==b and x['mode']==mode]
                self.assertEqual(len(rr),60);self.assertEqual(len({x['ganzhi'] for x in rr}),60)
                self.assertEqual([x['rank'] for x in rr],list(range(1,61)))
                self.assertTrue(all(x['observed_rate']>=y['observed_rate']-1e-14 for x,y in zip(rr,rr[1:])))
                for x in rr:self.assertAlmostEqual(x['success']/x['n'],x['observed_rate'],places=13)

    def test_reference_coverage_and_nested_bands(self):
        for r in read('group_intervals_and_ranks'):
            self.assertGreaterEqual(r['pointwise_actual_coverage']+1e-12,.95)
            self.assertGreaterEqual(r['simultaneous_marginal_coverage']+1e-12,1-.05/60)
            self.assertLessEqual(r['simultaneous95_low'],r['pointwise95_low'])
            self.assertGreaterEqual(r['simultaneous95_high'],r['pointwise95_high'])
            self.assertEqual(r['up']+r['down']+r['flat'],r['n'])

    def test_unequal_n_moments_not_average_n(self):
        g=[dict(n=4,binary_n=4),dict(n=8,binary_n=7)]
        mu,sd,rms,hist=moments(g,.5,'up')
        means=np.array([.5,7/16]);var=np.array([.25/4,7*.25/64])
        self.assertAlmostEqual(mu,means.mean())
        self.assertAlmostEqual(sd**2,var.mean()+np.mean((means-means.mean())**2))
        self.assertAlmostEqual(rms**2,var.mean()+np.sum((means-means.mean())**2))

    def test_integer_threshold_discreteness_preserved(self):
        # 36/56 is below65%; display rounding must never count it as>=65%.
        self.assertFalse(100*36>=65*56)
        rows=[x for x in read('thresholds_summary') if x['basis']=='oc' and x['mode']=='dominant' and x['threshold_pct']==65]
        self.assertTrue(all(x['observed_count']==0 for x in rows))

    def test_three_high_definition_pngs(self):
        names=['01_distribution_p50.png','02_distribution_p_actual.png','03_rankings_exact_reference_intervals.png']
        self.assertEqual(sorted(x.name for x in ROOT.glob('*.png')),names)
        for name in names:
            with Image.open(ROOT/name) as im:
                self.assertGreaterEqual(im.width,4800);self.assertGreaterEqual(im.height,3000)
                for dpi in im.info['dpi']:self.assertAlmostEqual(dpi,300,delta=.1)

    def test_no_new_null_selection_or_unadjusted_success_claim(self):
        self.assertEqual(read('source_manifest')['new_MC_runs'],0)
        self.assertTrue(all(r['holm_primary68']>=.05 for r in read('thresholds_summary')))
        self.assertTrue(all(r['histogram_holm']>=.05 for r in read('significance_summary')))


if __name__=='__main__':unittest.main(verbosity=2)
