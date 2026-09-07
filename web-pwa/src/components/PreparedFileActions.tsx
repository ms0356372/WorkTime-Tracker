import {useState} from 'react'
import {interactiveSave,legacyDownload,type SaveableFile} from '../services/fileSaveService'

type State='READY'|'SAVING'|'SAVED'|'HANDED_OFF'|'CANCELLED'|'ERROR'|'FALLBACK'
export function PreparedFileActions({file,saveLabel,downloadLabel,onSaved}:{file:SaveableFile;saveLabel:string;downloadLabel:string;onSaved?:()=>void}){
  const [state,setState]=useState<State>('READY'),[message,setMessage]=useState('')
  async function save(){setState('SAVING');setMessage('');const result=await interactiveSave(file);if(result.status==='cancelled'){setState('CANCELLED');setMessage('已取消儲存。');return}if(result.status==='fallback-required'){setState('FALLBACK');setMessage('此瀏覽器無法直接選擇儲存位置。你仍可以按下下載按鈕，由瀏覽器依目前下載設定儲存。');return}if(result.status==='error'){setState('ERROR');setMessage(result.message);return}setState(result.method==='picker'?'SAVED':'HANDED_OFF');setMessage(result.method==='picker'?'檔案已儲存。':'已交由系統處理檔案。');onSaved?.()}
  function download(){legacyDownload(file);setState('HANDED_OFF');setMessage('已交由瀏覽器下載。');onSaved?.()}
  return <div className="prepared-file"><p role="status"><strong>檔案：</strong>{file.filename}</p><div className="settings-actions">{state==='FALLBACK'?<button type="button" onClick={download}>{downloadLabel}</button>:<button type="button" disabled={state==='SAVING'} aria-busy={state==='SAVING'} onClick={()=>void save()}>{state==='SAVING'?'儲存中…':saveLabel}</button>}</div>{message&&<p className="notice" role={state==='ERROR'?'alert':'status'}>{message}</p>}</div>
}
