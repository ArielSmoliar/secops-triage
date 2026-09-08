"""Assemble the reviewed narration and actual UI clips. No network calls."""
import argparse,json,subprocess,math,re,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
FONT='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(p)]))['format']['duration']
def split(text):
 words=text.split();chunks=[];current=[]
 for word in words:
  if len(' '.join(current+[word]))>85 or len(current)>=15:
   chunks.append(' '.join(current));current=[]
  current.append(word)
 if current:chunks.append(' '.join(current))
 return chunks

def caption(text,path):
 im=Image.new('RGBA',(1920,1080),(0,0,0,0));d=ImageDraw.Draw(im);f=ImageFont.truetype(FONT,30)
 words=text.split();lines=['']
 for word in words:
  candidate=(lines[-1]+' '+word).strip()
  if d.textlength(candidate,font=f)>1450:lines.append(word)
  else:lines[-1]=candidate
 if len(lines)>2:raise ValueError('caption overflow')
 for n,line in enumerate(lines):
  width=d.textlength(line,font=f);d.text(((1920-width)/2,950+n*38),line,fill='#f5f3eb',font=f)
 im.save(path)
def srt_time(t):
 ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
 return f'{h:02}:{m:02}:{s:02},{ms:03}'
def main():
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--capture',type=Path,required=True);p.add_argument('--narration',type=Path,required=True);p.add_argument('--artwork',type=Path,required=True);p.add_argument('--captions',action='store_true');p.add_argument('--timing',type=Path);a=p.parse_args();a.root.mkdir(parents=True,exist_ok=False)
 story=json.loads(Path('ops/demo_video/story.json').read_text());overrides=json.loads(Path('ops/demo_video/caption_overrides.json').read_text());scenes=story['scenes'];durations=[float(probe(a.narration/(s['id']+'.wav'))) for s in scenes]
 if sum(durations)>116:raise ValueError('Narration too long; preserve audio and review pacing before editing')
 padding=(120-sum(durations))/8;frames=[round((d+padding)*30) for d in durations];frames[-1]=3600-sum(frames[:-1]);srt=[];timeline=[];offset=0;index=1
 if a.timing:
  previous=json.loads(a.timing.read_text())['scenes']
  if [x['id'] for x in previous]!=[x['id'] for x in scenes]:raise ValueError('timing scene mismatch')
  frames=[round(x['seconds']*30) for x in previous]
  if sum(frames)!=3600 or any(d+.30>n/30 for d,n in zip(durations,frames)):raise ValueError('audio exceeds preserved scene timing')
 for s,raw_duration,count in zip(scenes,durations,frames):
  sid=s['id'];duration=count/30;is_screen=sid.startswith(('02','03','04','05','06'))
  source=a.capture/(sid+'.webm') if is_screen else a.artwork/(sid+'.png')
  cmd=['ffmpeg','-hide_banner','-loglevel','error','-n']
  if is_screen:cmd+=['-ss','0.3','-i',str(source)]
  else:cmd+=['-loop','1','-framerate','30','-i',str(source)]
  cmd+=['-loop','1','-framerate','30','-i',str(a.artwork/(sid+'-overlay.png')),'-i',str(a.narration/(sid+'.wav'))]
  chunks=split(overrides.get(sid,s['narration']));weight=sum(len(x) for x in chunks);elapsed=0;captions=[]
  for n,text in enumerate(chunks if a.captions else []):
   begin=.30+elapsed;elapsed+=raw_duration*len(text)/weight;end=.30+elapsed
   file=a.root/f'{sid}-caption-{n}.png';caption(text,file);cmd+=['-loop','1','-framerate','30','-i',str(file)]
   captions.append((begin,end));srt.extend([str(index),f'{srt_time(offset+begin)} --> {srt_time(offset+end)}',text,'']);index+=1
  filters=[f'[0:v]scale=1536:780:flags=lanczos,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=30,trim=duration={duration},setpts=PTS-STARTPTS,pad=1920:1080:192:140:color=0x10232b[base]',f'[base][1:v]overlay=0:0:shortest=1[v0]']
  for n,(begin,end) in enumerate(captions):filters.append(f"[v{n}][{n+3}:v]overlay=0:0:enable='between(t,{begin:.6f},{end:.6f})':shortest=1[v{n+1}]")
  filters.append(f'[2:a]adelay=300:all=1,apad,atrim=duration={duration},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]')
  cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map',f'[v{len(captions)}]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-r','30','-frames:v',str(count),'-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t',str(duration),'-movflags','+faststart',str(a.root/(sid+'.mp4'))]
  r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(a.root/(sid+'-render.log')).write_text(r.stdout)
  if r.returncode:raise RuntimeError('render failed: '+sid)
  timeline.append({'id':sid,'start':offset,'seconds':duration,'audio_seconds':raw_duration,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'audio_sha256':hashlib.sha256((a.narration/(sid+'.wav')).read_bytes()).hexdigest(),'screen_speed':'original; first 0.3 seconds trimmed, final frame held when needed' if is_screen else 'original graphic'})
  offset+=duration;print(sid+' assembled',flush=True)
 if a.captions:(a.root/'secops-triage-demo.srt').write_text('\n'.join(srt))
 (a.root/'concat.txt').write_text(''.join("file '"+s['id']+".mp4'\n" for s in scenes))
 final=a.root/'secops-triage-demo-2min.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-n','-f','concat','-safe','0','-i',str(a.root/'concat.txt'),'-c','copy','-t','119.95','-movflags','+faststart',str(final)],check=True)
 (a.root/'timeline.json').write_text(json.dumps({'burned_in_captions':a.captions,'target_seconds':120,'frames':sum(frames),'narration':'OpenAI Cedar; AI-generated','scenes':timeline,'final_sha256':hashlib.sha256(final.read_bytes()).hexdigest()},indent=2))
 print('FINAL '+str(final),flush=True)
if __name__=='__main__':main()
