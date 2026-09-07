export interface CalendarEditOrigin{year:number;month:number;scrollY?:number}

export type EditCompletion={page:'records'}|{page:'calendar';view:CalendarEditOrigin}

export function completeRecordEdit(origin?:CalendarEditOrigin):EditCompletion{
  return origin?{page:'calendar',view:origin}:{page:'records'}
}
