#!/usr/bin/env python3
"""Normalize audited archive + validated 383 supplement into one canonical XSMN CSV."""
import argparse, json
from pathlib import Path
import pandas as pd

SCHEDULE = {
 'mon': {'Ca Mau','Dong Thap','TP. HCM'},
 'tue': {'Bac Lieu','Ben Tre','Vung Tau'},
 'wed': {'Can Tho','Dong Nai','Soc Trang'},
 'thu': {'An Giang','Binh Thuan','Tay Ninh'},
 'fri': {'Binh Duong','Tra Vinh','Vinh Long'},
 'sat': {'Binh Phuoc','Hau Giang','Long An','TP. HCM'},
 'sun': {'Da Lat','Kien Giang','Tien Giang'},
}
PRIZE_LENGTH = {'DB':6,'G1':5,'G2':5,'G3':5,'G4':5,'G5':4,'G6':4,'G7':3,'G8':2}
REQUIRED = ['date','province','prize','prize_order','number']

def read_source(path, source):
    df=pd.read_csv(path,dtype={'number':str,'last2':str})
    missing=set(REQUIRED)-set(df.columns)
    if missing: raise ValueError(f'{source}: missing columns {sorted(missing)}')
    df=df[REQUIRED].copy()
    df['date']=pd.to_datetime(df['date'],errors='raise').dt.strftime('%Y-%m-%d')
    df['province']=df['province'].astype(str).str.strip()
    df['prize']=df['prize'].astype(str).str.strip().str.upper()
    df['prize_order']=pd.to_numeric(df['prize_order'],errors='raise').astype(int)
    df['number']=df['number'].astype(str).str.strip()
    df['source']=source
    return df

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive',required=True); p.add_argument('--supplement',required=True)
    p.add_argument('--out',default='xsmn_normalized_5y.csv'); p.add_argument('--report',default='xsmn_normalization_report.json')
    a=p.parse_args()
    old=read_source(a.archive,'quarterly_archive')
    new=read_source(a.supplement,'383_supplement')
    df=pd.concat([old,new],ignore_index=True)
    errors=[]
    duplicate_count=int(df.duplicated(['date','province','prize','prize_order']).sum())
    if duplicate_count: errors.append({'type':'duplicate_record_keys','count':duplicate_count})
    if set(df['province']) != set().union(*SCHEDULE.values()):
        errors.append({'type':'province_set_mismatch','actual':sorted(df.province.unique())})
    for prize,length in PRIZE_LENGTH.items():
        vals=df.loc[df.prize.eq(prize),'number']
        if vals.empty or not vals.str.fullmatch(r'\d+').all() or not vals.str.len().eq(length).all():
            errors.append({'type':'number_format','prize':prize,'expected_length':length,'rows':len(vals)})
    if set(df.prize.unique()) != set(PRIZE_LENGTH): errors.append({'type':'prize_set_mismatch','actual':sorted(df.prize.unique())})
    bad_schedule=[]
    for day,g in df.groupby('date'):
        d=pd.Timestamp(day); weekday=('mon','tue','wed','thu','fri','sat','sun')[d.weekday()]
        actual=set(g.province.unique()); expected=SCHEDULE[weekday]
        if actual != expected: bad_schedule.append({'date':day,'missing':sorted(expected-actual),'unexpected':sorted(actual-expected)})
    if bad_schedule: errors.append({'type':'schedule_mismatch','count':len(bad_schedule),'examples':bad_schedule[:30]})
    dates=sorted(df.date.unique())
    expected_dates=pd.date_range(dates[0],dates[-1],freq='D').strftime('%Y-%m-%d').tolist()
    missing_dates=sorted(set(expected_dates)-set(dates))
    if missing_dates: errors.append({'type':'missing_calendar_dates','count':len(missing_dates),'dates':missing_dates[:30]})
    old_end=pd.Timestamp(old.date.max()); new_start=pd.Timestamp(new.date.min())
    gap=(new_start-old_end).days
    if gap != 1: errors.append({'type':'source_boundary','archive_end':str(old_end.date()),'supplement_start':str(new_start.date()),'day_gap':gap})
    df['number_length']=df.number.str.len().astype(int)
    df['last2']=df.number.str[-2:].str.zfill(2)
    df['last2_numeric']=pd.to_numeric(df.last2,errors='raise').astype(int)
    df=df.sort_values(['date','province','prize','prize_order'],kind='stable')
    out=df[['date','province','prize','prize_order','number','number_length','last2','last2_numeric','source']]
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.report).parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(a.out,index=False,encoding='utf-8-sig')
    report={'window_start':dates[0],'window_end':dates[-1],'calendar_days':len(dates),'rows':len(out),
      'archive_rows':len(old),'supplement_rows':len(new),'province_count':out.province.nunique(),
      'prize_count':out.prize.nunique(),'station_day_pairs':int(out[['date','province']].drop_duplicates().shape[0]),
      'missing_calendar_dates':len(missing_dates),'schedule_mismatch_days':len(bad_schedule),
      'duplicate_keys':duplicate_count,'source_boundary_gap_days':gap,'errors':errors,
      'status':'PASS' if not errors else 'FAIL',
      'caveat':'383.im is a third-party source and has not been independently verified; retain the source column.'}
    Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors: raise SystemExit(1)
if __name__=='__main__': main()
