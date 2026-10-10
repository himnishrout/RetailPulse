"""RetailPulse: auditable analytics and temporally separated repeat-purchase evaluation."""
import argparse, hashlib, json, math, os, time, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.calibration import calibration_curve
import joblib

ROOT = Path(__file__).resolve().parent
FEATURES = ['recency_days','tenure_days','orders','spend','aov','products','orders_30','orders_90','spend_90','return_lines']

def load(path):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as z:
            candidates = [n for n in z.namelist() if n.lower().endswith('.xlsx')]
            if len(candidates) != 1: raise ValueError('ZIP must contain exactly one XLSX workbook')
            with z.open(candidates[0]) as f: sheets = pd.read_excel(f, sheet_name=None)
    elif path.suffix.lower() == '.xlsx': sheets = pd.read_excel(path, sheet_name=None)
    else: sheets = {'csv': pd.read_csv(path, dtype={'Invoice':str,'StockCode':str})}
    frames = []
    for name, d in sheets.items():
        d = d.rename(columns={'Invoice':'invoice','InvoiceNo':'invoice','StockCode':'product_id','Description':'description','Quantity':'quantity','InvoiceDate':'invoice_date','Price':'unit_price','UnitPrice':'unit_price','Customer ID':'customer_id','CustomerID':'customer_id','Country':'country'})
        required = ['invoice','product_id','description','quantity','invoice_date','unit_price','customer_id','country']
        if not set(required).issubset(d.columns): raise ValueError(f'{name}: missing columns {set(required)-set(d.columns)}')
        d = d[required].copy(); d['source_sheet']=name; d['source_row']=np.arange(2,len(d)+2)
        frames.append(d)
    return pd.concat(frames,ignore_index=True)

def clean(raw):
    d=raw.copy(); business = list(raw.columns[:8])
    for c in ['invoice','product_id','country']:
        d[c]=d[c].astype('string').str.strip().replace('',pd.NA)
    d['invoice_date']=pd.to_datetime(d.invoice_date,errors='coerce')
    for c in ['quantity','unit_price','customer_id']: d[c]=pd.to_numeric(d[c],errors='coerce')
    invalid_customer = d.customer_id.notna() & ((d.customer_id % 1 != 0) | (d.customer_id <= 0))
    missing = d.customer_id.isna() | invalid_customer
    duplicate=d.duplicated(business,keep='first')
    invalid=(d.invoice.isna()|d.product_id.isna()|d.invoice_date.isna()|d.quantity.isna()|d.unit_price.isna()|(d.unit_price<=0)|(d.quantity==0)|(d.quantity%1!=0)|~np.isfinite(d.quantity)|~np.isfinite(d.unit_price))
    cancellation=d.invoice.str.upper().str.startswith('C',na=False)
    mismatch=cancellation & (d.quantity>0)
    d['exclusion_reason']=np.select([duplicate,invalid,mismatch],['exact_duplicate','invalid_core_fields','positive_cancellation'],default='retained')
    d['missing_customer']=missing
    d.loc[missing,'customer_id']=pd.NA
    d['customer_id']=d.customer_id.astype('Int64')
    audit=d[d.exclusion_reason!='retained'].copy()
    f=d[d.exclusion_reason=='retained'].copy().reset_index(drop=True)
    f['line_id']=np.arange(1,len(f)+1)
    f['is_sale']=f.quantity>0
    f['is_return']=f.quantity<0
    f['is_cancellation_invoice']=f.invoice.str.upper().str.startswith('C',na=False)
    f['line_revenue']=(f.quantity*f.unit_price).round(2)
    f['date']=f.invoice_date.dt.normalize()
    # An invoice may have unknown customer lines; preserve invoices without making up identities.
    identified=f[f.customer_id.notna()]
    conflicts=identified.groupby('invoice').customer_id.nunique()
    if (conflicts>1).any(): raise ValueError('Invoice mapped to multiple customers; investigate before proceeding')
    q={'raw_rows':len(raw),'clean_rows':len(f),'excluded_rows':len(audit),'exact_duplicate_rows':int(duplicate.sum()),'invalid_core_rows':int(invalid.sum()),'positive_cancellation_rows':int(mismatch.sum()),'missing_or_invalid_customer_raw_rows':int(missing.sum()),'anonymous_clean_rows':int(f.customer_id.isna().sum()),'return_lines':int(f.is_return.sum()),'date_min':str(f.invoice_date.min()),'date_max':str(f.invoice_date.max()),'exclusion_counts':d.exclusion_reason.value_counts().to_dict()}
    assert len(f)+len(audit)==len(raw)
    return f,audit,q

def features(f,cutoff,label=True):
    cutoff=pd.Timestamp(cutoff)
    h=f[(f.invoice_date<cutoff)&f.customer_id.notna()]
    s=h[h.is_sale]
    x=s.groupby('customer_id').agg(last=('invoice_date','max'),first=('invoice_date','min'),orders=('invoice','nunique'),spend=('line_revenue','sum'),products=('product_id','nunique'))
    x['recency_days']=(cutoff-x['last']).dt.total_seconds()/86400
    x['tenure_days']=(cutoff-x['first']).dt.total_seconds()/86400
    x['aov']=x.spend/x.orders
    for days in [30,90]:
        w=s[s.invoice_date>=cutoff-pd.Timedelta(days=days)].groupby('customer_id')
        x[f'orders_{days}']=w.invoice.nunique()
        if days==90: x['spend_90']=w.line_revenue.sum()
    x['return_lines']=h[h.is_return].groupby('customer_id').size()
    x=x[FEATURES].fillna(0)
    if label:
        future=f[(f.invoice_date>=cutoff)&(f.invoice_date<cutoff+pd.Timedelta(days=90))&f.is_sale&f.customer_id.notna()]
        x['target']=x.index.isin(future.customer_id.unique()).astype(int)
    x['snapshot_date']=cutoff
    return x.reset_index()

def analytics(f):
    out={}
    out['fct_transactions']=f.drop(columns=['exclusion_reason','missing_customer'])
    sales=f[f.is_sale]; known=sales[sales.customer_id.notna()]
    customers=known.sort_values('invoice_date').groupby('customer_id').agg(first_purchase=('invoice_date','min'),last_purchase=('invoice_date','max'),country=('country','last'),orders=('invoice','nunique'),spend=('line_revenue','sum')).reset_index()
    asof=f.invoice_date.max().normalize()+pd.Timedelta(days=1)
    customers['recency_days']=(asof-customers.last_purchase).dt.days
    for col,asc,tag in [('recency_days',False,'r'),('orders',True,'f'),('spend',True,'m')]:
        # Percentile ranks give equal values equal scores; do not break ties by customer ID.
        customers[tag+'_score']=np.ceil(customers[col].rank(pct=True,ascending=asc)*5).clip(1,5).astype(int)
    customers['segment']=np.select([(customers.r_score>=4)&(customers.f_score>=4)&(customers.m_score>=4),(customers.r_score<=2)&(customers.f_score>=3),(customers.f_score<=2)&(customers.r_score>=4)],['Champions','At risk','Recent low frequency'],default='Other')
    customers['snapshot_date']=asof
    out['dim_customers']=customers
    out['dim_products']=f.sort_values('invoice_date').groupby('product_id',dropna=False).description.last().reset_index()
    dates=pd.DataFrame({'date':pd.date_range(f.date.min(),f.date.max())}); dates['year']=dates.date.dt.year; dates['month']=dates.date.dt.to_period('M').astype(str)
    out['dim_dates']=dates
    monthly=f.assign(month=f.date.dt.to_period('M').astype(str),gross_sales=np.where(f.is_sale,f.line_revenue,0),return_value=np.where(f.is_return,-f.line_revenue,0)).groupby('month').agg(gross_sales=('gross_sales','sum'),return_value=('return_value','sum'),net_revenue=('line_revenue','sum')).reset_index()
    monthly['orders']=sales.assign(month=sales.date.dt.to_period('M').astype(str)).groupby('month').invoice.nunique().reindex(monthly.month).to_numpy()
    monthly['aov']=monthly.gross_sales/monthly.orders
    monthly['net_revenue_mom']=monthly.net_revenue.pct_change()
    monthly['partial_month']=monthly.month.isin([str(f.date.min().to_period('M')),str(f.date.max().to_period('M'))])
    out['monthly_sales']=monthly
    activity=known[['customer_id','invoice_date']].copy(); activity['month']=activity.invoice_date.dt.to_period('M')
    first=activity.groupby('customer_id').month.min(); activity['cohort']=activity.customer_id.map(first)
    activity['month_index']=activity.month.astype('int64')-activity.cohort.astype('int64')
    counts=activity.groupby(['cohort','month_index']).customer_id.nunique()
    rows=[]; last_month=f.date.max().to_period('M')
    for cohort,size in first.value_counts().sort_index().items():
        for age in range(last_month.ordinal-cohort.ordinal+1):
            month=cohort+age; observed=month<last_month  # final observed month is conservatively censored
            active=int(counts.get((cohort,age),0)) if observed else None
            rows.append({'cohort':str(cohort),'month_index':age,'cohort_size':int(size),'active_customers':active,'retention':active/size if observed else None,'fully_observed':observed})
    out['cohort_retention']=pd.DataFrame(rows)
    out['product_performance']=f.assign(gross_sales=np.where(f.is_sale,f.line_revenue,0),return_value=np.where(f.is_return,-f.line_revenue,0),sale_units=np.where(f.is_sale,f.quantity,0),return_units=np.where(f.is_return,-f.quantity,0)).groupby('product_id').agg(gross_sales=('gross_sales','sum'),return_value=('return_value','sum'),sale_units=('sale_units','sum'),return_units=('return_units','sum')).reset_index()
    out['product_performance']['return_value_ratio']=out['product_performance'].return_value/out['product_performance'].gross_sales.replace(0,np.nan)
    return out

def metrics(y,p):
    k=max(1,math.ceil(len(y)*.1)); top=np.argsort(-p,kind='stable')[:k]; rate=float(np.mean(y)); pred=p>=.5
    return {'n':len(y),'positive_rate':rate,'average_precision':float(average_precision_score(y,p)),'roc_auc':float(roc_auc_score(y,p)),'brier':float(brier_score_loss(y,p)),'precision_at_10pct':float(np.mean(np.asarray(y)[top])),'lift_at_10pct':float(np.mean(np.asarray(y)[top])/rate),'precision_0_5':float(precision_score(y,pred,zero_division=0)),'recall_0_5':float(recall_score(y,pred,zero_division=0)),'f1_0_5':float(f1_score(y,pred,zero_division=0)),'confusion_matrix_0_5':confusion_matrix(y,pred).tolist()}

def evaluate(f,outdir):
    start=f.invoice_date.min().normalize(); end=f.invoice_date.max()
    # Last fully observed 90-day horizon; prior snapshots 91 days apart purge label overlap.
    test_date=end.normalize()-pd.Timedelta(days=90)
    valid_date=test_date-pd.Timedelta(days=91); train_date=valid_date-pd.Timedelta(days=91)
    if train_date-start<pd.Timedelta(days=180): raise ValueError('Need >=180 days of history before training plus three separated 90-day horizons')
    frames=[features(f,d) for d in [train_date,valid_date,test_date]]
    for frame in frames:
        if frame.target.nunique()!=2 or len(frame)<100: raise ValueError('Insufficient eligible customers/classes')
    train,valid,test=frames; models={'logistic':make_pipeline(StandardScaler(),LogisticRegression(max_iter=1000,random_state=42)), 'gradient_boosting':HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=15,l2_regularization=10,random_state=42)}
    val={}; timing={}
    for name,model in models.items():
        t=time.perf_counter(); model.fit(train[FEATURES],train.target); timing[name]=time.perf_counter()-t
        val[name]=metrics(valid.target,model.predict_proba(valid[FEATURES])[:,1])
    selected=max(val,key=lambda name:val[name]['average_precision']); model=models[selected]
    # Keep model trained only on train snapshot; do not refit after seeing test.
    scores={'constant':np.full(len(test),train.target.mean()),'recency_rule':np.exp(-test.recency_days.to_numpy()/90)}
    for name,m in models.items(): scores[name]=m.predict_proba(test[FEATURES])[:,1]
    results={n:metrics(test.target,p) for n,p in scores.items()}
    # Paired bootstrap over unique customers at the single test snapshot.
    rng=np.random.default_rng(42); diff=[]; p=scores[selected]; baseline=scores['recency_rule']; y=test.target.to_numpy()
    for _ in range(500):
        ix=rng.integers(0,len(y),len(y))
        if len(np.unique(y[ix]))==2: diff.append(average_precision_score(y[ix],p[ix])-average_precision_score(y[ix],baseline[ix]))
    prob_true,prob_pred=calibration_curve(y,p,n_bins=10,strategy='quantile')
    pd.DataFrame({'mean_predicted_probability':prob_pred,'observed_repeat_rate':prob_true}).to_csv(outdir/'calibration.csv',index=False)
    test.assign(probability=p).to_csv(outdir/'test_predictions.csv',index=False)
    report={'target':'positive valid purchase in [snapshot,snapshot+90 days)','train_snapshot':str(train_date),'validation_snapshot':str(valid_date),'test_snapshot':str(test_date),'features':FEATURES,'selected_by_validation_average_precision':selected,'validation':val,'test':results,'training_seconds':timing,'paired_bootstrap_AP_difference_vs_recency_95pct':np.quantile(diff,[.025,.975]).tolist(),'test_unique_customers':len(test),'customer_overlap_allowed':True,'limitations':['Customers may appear across periods: estimates existing-customer future performance, not unseen-customer generalization.','One final temporal holdout; bootstrap does not measure seasonal or future-market variation.','Recency rule probabilities are heuristic; its ranking is the primary comparison.','Observed repeat purchases are not campaign response or causal uplift.']}
    joblib.dump(model,outdir/'repeat_purchase_model.joblib')
    latest=f.invoice_date.max().normalize()+pd.Timedelta(days=1); current=features(f,latest,label=False)
    current['repeat_probability']=model.predict_proba(current[FEATURES])[:,1]; current['model']=selected
    current.to_csv(outdir/'customer_scores.csv',index=False)
    return report,current

def database(raw,tables,url):
    from sqlalchemy import create_engine,text
    engine=create_engine(url)
    with engine.begin() as conn:
        conn.execute(text((ROOT/'sql/schema.sql').read_text()))
        names=['stg_transactions','dim_customers','dim_products','dim_dates','fct_transactions','monthly_sales','cohort_retention','product_performance','customer_scores']
        # Reload this project's tables atomically; no DROP/REPLACE of dimensional constraints.
        conn.execute(text('TRUNCATE '+', '.join('retailpulse.'+n for n in names)+' RESTART IDENTITY CASCADE'))
        raw.to_sql('stg_transactions',conn,schema='retailpulse',if_exists='append',index=False,chunksize=3000,method='multi')
        for name in ['dim_customers','dim_products','dim_dates','fct_transactions']:
            tables[name].to_sql(name,conn,schema='retailpulse',if_exists='append',index=False,chunksize=1000,method='multi')
        for name,d in tables.items():
            if name not in ['dim_customers','dim_products','dim_dates','fct_transactions']:
                d.to_sql(name,conn,schema='retailpulse',if_exists='append',index=False,chunksize=1000,method='multi')
    engine.dispose()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',required=True); ap.add_argument('--database-url',default=os.getenv('DATABASE_URL')); ap.add_argument('--analytics-only',action='store_true'); a=ap.parse_args()
    o=ROOT/'outputs'; o.mkdir(exist_ok=True)
    # Remove previous generated outputs so analytics-only cannot expose old scores.
    for old in o.glob('*'):
        if old.is_file() and old.name!='.gitkeep': old.unlink()
    raw=load(a.input); f,audit,q=clean(raw); tables=analytics(f)
    audit.to_csv(o/'excluded_rows.csv',index=False)
    q['identified_customers']=len(tables['dim_customers']); q['repeat_customer_share']=float((tables['dim_customers'].orders>1).mean()); q['identified_clean_row_share']=float(f.customer_id.notna().mean()); q['input_sha256']=hashlib.sha256(Path(a.input).read_bytes()).hexdigest()
    report=None
    if not a.analytics_only:
        report,scores=evaluate(f,o); tables['customer_scores']=scores
        (o/'evaluation.json').write_text(json.dumps(report,indent=2))
    for name,d in tables.items(): d.to_csv(o/(name+'.csv'),index=False)
    flat=f.merge(tables['dim_customers'][['customer_id','segment']],on='customer_id',how='left',validate='many_to_one')
    flat['segment']=flat.segment.fillna('Anonymous / no qualifying purchase')
    flat['gross_sales']=np.where(flat.is_sale,flat.line_revenue,0)
    flat['return_credit']=np.where(flat.is_return,-flat.line_revenue,0)
    flat['purchase_invoice']=flat.invoice.where(flat.is_sale)
    flat=flat[['date','country','product_id','description','customer_id','segment','gross_sales','return_credit','line_revenue','purchase_invoice','quantity']]
    flat.to_csv(o/'sales_explorer.csv',index=False)
    (o/'data_quality.json').write_text(json.dumps(q,indent=2))
    pd.DataFrame([{'check':k,'value':v} for k,v in q.items() if isinstance(v,(int,float))]).to_csv(o/'data_quality.csv',index=False)
    if a.database_url: database(raw,tables,a.database_url)
    summary=f'# RetailPulse measured run\n\nInput SHA256: {q["input_sha256"]}\n\nProcessed {len(raw):,} raw lines; retained {len(f):,}; identified {q["identified_customers"]:,} purchasing customers. Repeat-customer share over the complete historical window: {q["repeat_customer_share"]:.1%}.\n'
    if report:
        selected=report['selected_by_validation_average_precision']; m=report['test'][selected]; b=report['test']['recency_rule']
        summary+=f'\nSelected {selected} on validation AP. Test: {m["n"]:,} customers; positive rate {m["positive_rate"]:.1%}; AP {m["average_precision"]:.3f} versus recency AP {b["average_precision"]:.3f}; ROC-AUC {m["roc_auc"]:.3f}; Brier {m["brier"]:.3f}; precision@top10% {m["precision_at_10pct"]:.1%}; lift@top10% {m["lift_at_10pct"]:.2f}x.\n\nResume candidate (use only after reviewing evaluation): Built a retail analytics pipeline over '+f'{len(raw):,} transaction lines and evaluated 90-day repeat-purchase predictions on {m["n"]:,} temporally held-out customers, achieving AP {m["average_precision"]:.3f} versus a recency baseline of {b["average_precision"]:.3f}.\n'
    summary+='\nPower BI report must be assembled separately. No campaign revenue improvement was measured. See docs/EVALUATION.md for scope and limitations.\n'
    (o/'RESULTS.md').write_text(summary); print(summary)

if __name__=='__main__': main()
