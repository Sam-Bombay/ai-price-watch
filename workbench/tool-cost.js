'use strict';
function toolCost(search, fetch, oldRate, newRate, migration) {
 const values=[search,fetch,oldRate,newRate,migration].map(Number);
 if(values.some(x=>!Number.isFinite(x)||x<0)||!Number.isInteger(values[0])||!Number.isInteger(values[1])) throw Error('Use nonnegative numbers and whole request counts.');
 const [s,f,o,n,m]=values, total=s+f, oldCost=total*o/1000, newCost=total*n/1000;
 return {requests:total,oldCost,newCost,netFirstMonth:oldCost-newCost-m,recurringSaving:oldCost-newCost};
}
if(typeof module!=='undefined') module.exports=toolCost;
