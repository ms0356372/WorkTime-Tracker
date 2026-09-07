export function annualLeaveMinutesToHours(minutes:number):number{
  return minutes/60
}

export function annualLeaveHoursToMinutes(hours:number):number{
  const minutes=hours*60
  if(!Number.isFinite(hours)||hours<0||!Number.isInteger(minutes))throw new Error('特休額度必須是非負數，且換算後需為完整分鐘。')
  return minutes
}
