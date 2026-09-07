export interface SaveableFile{filename:string;blob:Blob;mime:string;description:string;extension:string}
export type SaveResult={status:'saved';method:'picker'|'share'}|{status:'cancelled'}|{status:'fallback-required'}|{status:'error';message:string}

interface WritableHandle{createWritable():Promise<{write(data:Blob):Promise<void>;close():Promise<void>}>}
type SavePicker=(options:{suggestedName:string;types:Array<{description:string;accept:Record<string,string[]>}>})=>Promise<WritableHandle>
function cancelled(error:unknown){return error instanceof Error&&error.name==='AbortError'}

/** Opens an OS-controlled save surface. It never starts a browser download. */
export async function interactiveSave(file:SaveableFile):Promise<SaveResult>{
  const picker=(window as typeof window&{showSaveFilePicker?:SavePicker}).showSaveFilePicker
  if(picker){
    try{const handle=await picker.call(window,{suggestedName:file.filename,types:[{description:file.description,accept:{[file.mime]:[file.extension]}}]}),writable=await handle.createWritable();await writable.write(file.blob);await writable.close();return{status:'saved',method:'picker'}}
    catch(error){return cancelled(error)?{status:'cancelled'}:{status:'error',message:'無法儲存檔案，請稍後再試。'}}
  }
  const sharedFile=new File([file.blob],file.filename,{type:file.mime})
  let canShare=false
  try{canShare=typeof navigator.share==='function'&&typeof navigator.canShare==='function'&&navigator.canShare({files:[sharedFile]})}catch{canShare=false}
  if(canShare){
    try{await navigator.share({files:[sharedFile],title:file.filename});return{status:'saved',method:'share'}}
    catch(error){return cancelled(error)?{status:'cancelled'}:{status:'error',message:'無法交由系統處理檔案，請稍後再試。'}}
  }
  return{status:'fallback-required'}
}

/** Must only be called by an explicit legacy-download button click. */
export function legacyDownload(file:Pick<SaveableFile,'filename'|'blob'>){const url=URL.createObjectURL(file.blob),anchor=document.createElement('a');anchor.href=url;anchor.download=file.filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),60_000)}
