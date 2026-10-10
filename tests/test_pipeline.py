import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from pipeline import clean, features, analytics

class PipelineTests(unittest.TestCase):
    def fixture(self):
        rows=[['1','A','item',2,'2010-01-01',10,1,'UK'],['1','A','item',2,'2010-01-01',10,1,'UK'],['C2','A','item',-1,'2010-01-02',10,1,'UK'],['3','A','item',1,'2010-01-03',10,None,'UK'],['C4','A','item',1,'2010-01-04',10,1,'UK'],['5','B','item',1,'2010-01-05',0,1,'UK'],['6','A','item',1,'2010-04-01',10,1,'UK'],['7','A','item',1,'2010-07-01',10,1,'UK']]
        d=pd.DataFrame(rows,columns=['invoice','product_id','description','quantity','invoice_date','unit_price','customer_id','country']);d['source_sheet']='test';d['source_row']=range(len(d));return d
    def test_accounting_and_identity(self):
        f,a,q=clean(self.fixture());self.assertEqual(len(f),5);self.assertEqual(len(a),3)
        self.assertEqual(f.line_revenue.sum(),40);self.assertEqual(f.customer_id.isna().sum(),1)
        self.assertEqual(int(f.is_return.sum()),1)
    def test_future_cannot_change_features(self):
        f,_,_=clean(self.fixture());a=features(f,'2010-02-01');b=features(f[f.invoice_date<'2010-02-01'],'2010-02-01')
        pd.testing.assert_frame_equal(a.drop(columns='target'),b.drop(columns='target'))
        self.assertEqual(a.target.iloc[0],1);self.assertEqual(b.target.iloc[0],0)
        self.assertEqual(a.orders.iloc[0],1);self.assertEqual(a.spend.iloc[0],20)
    def test_horizon_end_exclusive(self):
        f,_,_=clean(self.fixture());cut=pd.Timestamp('2010-02-01');f.loc[f.invoice=='6','invoice_date']=cut+pd.Timedelta(days=90)
        self.assertEqual(features(f,cut).target.iloc[0],0)
    def test_cohort_zero_and_censoring(self):
        f,_,_=clean(self.fixture());c=analytics(f)['cohort_retention']
        self.assertEqual(c.loc[c.month_index==1,'retention'].iloc[0],0)
        self.assertTrue(c.loc[c.month_index==6,'retention'].isna().all())
    def test_no_customer_imputation(self):
        f,_,_=clean(self.fixture());self.assertEqual(len(analytics(f)['dim_customers']),1)

if __name__=='__main__':unittest.main()
