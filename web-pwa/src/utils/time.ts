export function timeToMinutes(value:string):number {if(!/^([01]\d|2[0-3]):[0-5]\d$/.test(value))throw new Error('時間必須為 HH:MM');const [h,m]=value.split(':').map(Number);return h*60+m}
export function minutesToTime(minutes:number):string {const normalized=((Math.trunc(minutes)%1440)+1440)%1440;return `${String(Math.floor(normalized/60)).padStart(2,'0')}:${String(normalized%60).padStart(2,'0')}`}
export function formatMinutes(value:number):string {const minutes=Math.max(Math.trunc(value),0);return `${Math.floor(minutes/60)} 小時 ${minutes%60} 分`}
