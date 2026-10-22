'use strict';
const fs=require('fs'),path=require('path'),p=path.resolve(__dirname,'../S26-D1Check/s26_simulator/experiments/route_event_learning_v1/report.py');let s=fs.readFileSync(p,'utf8');s=s.replace("'各条件の説明。',",'').replace("'\\n'.join(l for l in lines if l!='各条件の説明。')","'\\n'.join(lines)");fs.writeFileSync(p,s);console.log('EVENT_REPORT_KOREAN_CLEAN');
